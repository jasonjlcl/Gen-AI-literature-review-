"""LLM-driven abstract structuring with row-level persistence and recovery support."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from .clients import BaseLLMClient, GeminiClient, OpenAIClient
from .config import Settings
from .constants import STRUCTURED_FIELDS

LOGGER = logging.getLogger(__name__)
_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def create_llm_client(settings: Settings) -> BaseLLMClient:
    """Instantiate configured provider client."""
    provider = settings.llm_provider.strip().lower()
    if provider == "gemini":
        return GeminiClient(settings)
    if provider == "openai":
        return OpenAIClient(settings)
    raise ValueError(f"Unsupported llm provider: {settings.llm_provider}")


def _default_value(field_name: str) -> Any:
    list_fields = {
        "use_cases",
        "opportunities",
        "challenges",
        "data_requirements",
        "risk_factors",
        "compliance_considerations",
        "kpis",
        "stakeholders",
    }
    if field_name in list_fields:
        return []
    if field_name == "confidence_score":
        return None
    return None


def _safe_record_id(value: str) -> str:
    if not value:
        return ""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def _row_record_id_base(row: dict[str, Any], row_index: int) -> str:
    existing_record_id = str(row.get("record_id", "") or "").strip()
    if existing_record_id:
        safe_existing = _safe_record_id(existing_record_id)
        if safe_existing:
            return safe_existing

    source_id = str(row.get("id", "") or "").strip()
    if source_id:
        safe = _safe_record_id(source_id)
        if safe:
            return safe

    fingerprint = "|".join(
        [
            str(row.get("title", "") or ""),
            str(row.get("publication_year", "") or ""),
            str(row.get("type", "") or ""),
            str(row_index),
        ]
    )
    short_hash = hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:16]
    return f"record_{short_hash}"


def _generate_unique_record_ids(rows: list[dict[str, Any]]) -> list[str]:
    """
    Build deterministic, unique record IDs.

    If a base ID appears multiple times, every occurrence gets an ordinal suffix:
    `<base>__1`, `<base>__2`, ...
    """
    base_ids = [_row_record_id_base(row=row, row_index=idx) for idx, row in enumerate(rows)]
    total_counts: dict[str, int] = {}
    for base in base_ids:
        total_counts[base] = total_counts.get(base, 0) + 1

    seen: dict[str, int] = {}
    unique_ids: list[str] = []
    for base in base_ids:
        seen[base] = seen.get(base, 0) + 1
        if total_counts[base] == 1:
            unique_ids.append(base)
        else:
            unique_ids.append(f"{base}__{seen[base]}")
    return unique_ids


def attach_record_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Attach deterministic `record_id` column used for persistence/recovery."""
    records = df.copy()
    row_dicts = records.to_dict(orient="records")
    records["record_id"] = _generate_unique_record_ids(row_dicts)
    return records


def _clean_json_text(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        text = _CODE_FENCE_RE.sub("", text).strip()
    return text


def _normalize_structured_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for field in STRUCTURED_FIELDS:
        value = payload.get(field, _default_value(field))
        if isinstance(value, str):
            value = value.strip()
        normalized[field] = value
    return normalized


@dataclass(slots=True)
class ExtractionResult:
    record_id: str
    structured: dict[str, Any] | None
    error: str | None
    skipped_existing: bool


class AbstractStructuringExtractor:
    """Threaded LLM extraction with persistence and skip-on-existing semantics."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = create_llm_client(settings)
        self.prompt_template = Path(settings.prompt_template_path).read_text(encoding="utf-8")

    def extract_dataframe(
        self,
        df: pd.DataFrame,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> pd.DataFrame:
        records = df.copy()
        row_dicts = records.to_dict(orient="records")
        record_ids = _generate_unique_record_ids(row_dicts)

        if records.empty:
            records["record_id"] = []
            for field in STRUCTURED_FIELDS:
                records[field] = None
            records["llm_provider"] = self.client.provider
            records["llm_model"] = self.client.model
            records["llm_extraction_error"] = None
            self._write_failed_llm_log([])
            return records

        failures: list[dict[str, Any]] = []
        extraction_rows: list[dict[str, Any]] = []

        with ThreadPoolExecutor(max_workers=self.settings.llm_max_workers) as executor:
            futures = {
                executor.submit(
                    self._extract_one,
                    row=row,
                    row_index=idx,
                    record_id=record_ids[idx],
                ): idx
                for idx, row in enumerate(row_dicts)
            }

            completed = 0
            total = len(futures)
            for future in as_completed(futures):
                idx = futures[future]
                row = row_dicts[idx]
                record_id = record_ids[idx]
                completed += 1
                if on_progress is not None:
                    on_progress(completed, total)

                try:
                    result = future.result()
                except Exception as exc:  # pragma: no cover - defensive guard.
                    LOGGER.exception("Unhandled extraction error for %s", record_id)
                    failures.append(
                        {
                            "record_id": record_id,
                            "source_id": row.get("id"),
                            "error": f"Unhandled exception: {exc}",
                            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    extraction_rows.append(
                        {
                            "_row_index": idx,
                            "record_id": record_id,
                            **self._blank_payload(),
                            "llm_extraction_error": f"Unhandled exception: {exc}",
                        }
                    )
                    continue

                if result.error:
                    failures.append(
                        {
                            "record_id": record_id,
                            "source_id": row.get("id"),
                            "error": result.error,
                            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    extraction_rows.append(
                        {
                            "_row_index": idx,
                            "record_id": record_id,
                            **self._blank_payload(),
                            "llm_extraction_error": result.error,
                        }
                    )
                else:
                    extraction_rows.append(
                        {
                            "_row_index": idx,
                            "record_id": record_id,
                            **(result.structured or self._blank_payload()),
                            "llm_extraction_error": None,
                        }
                    )

        self._write_failed_llm_log(failures)
        extraction_df = pd.DataFrame(extraction_rows)
        if extraction_df.empty:
            extraction_df = pd.DataFrame(
                columns=["_row_index", "record_id", *STRUCTURED_FIELDS, "llm_extraction_error"]
            )

        records["record_id"] = record_ids
        records["_row_index"] = list(range(len(records)))
        merged = records.merge(extraction_df, on=["_row_index", "record_id"], how="left", sort=False)
        merged = merged.drop(columns=["_row_index"])
        merged["llm_provider"] = self.client.provider
        merged["llm_model"] = self.client.model
        return merged

    def _extract_one(
        self,
        row: dict[str, Any],
        row_index: int,
        record_id: str,
    ) -> ExtractionResult:
        response_path = self.settings.llm_responses_dir / f"{record_id}.json"

        if response_path.exists() and not self.settings.overwrite_existing_responses:
            cached = self._load_response_file(response_path)
            if cached is not None:
                return ExtractionResult(
                    record_id=record_id,
                    structured=cached,
                    error=None,
                    skipped_existing=True,
                )

        prompt = self._build_prompt(row)
        try:
            raw_response = self.client.generate(prompt)
            cleaned = _clean_json_text(raw_response)
            parsed = json.loads(cleaned)
            if not isinstance(parsed, dict):
                raise ValueError("LLM output JSON was not an object.")
            structured = _normalize_structured_payload(parsed)
            self._write_response_file(
                path=response_path,
                row=row,
                record_id=record_id,
                structured=structured,
                raw_response=raw_response,
            )
            return ExtractionResult(
                record_id=record_id,
                structured=structured,
                error=None,
                skipped_existing=False,
            )
        except Exception as exc:
            return ExtractionResult(
                record_id=record_id,
                structured=None,
                error=str(exc),
                skipped_existing=False,
            )

    def _build_prompt(self, row: dict[str, Any]) -> str:
        prompt = self.prompt_template
        replacements = {
            "{title}": str(row.get("title", "") or ""),
            "{publication_year}": str(row.get("publication_year", "") or ""),
            "{publication_type}": str(row.get("type", "") or ""),
            "{abstract}": str(row.get("abstract", "") or ""),
        }
        for token, value in replacements.items():
            prompt = prompt.replace(token, value)
        return prompt

    def _write_response_file(
        self,
        path: Path,
        row: dict[str, Any],
        record_id: str,
        structured: dict[str, Any],
        raw_response: str,
    ) -> None:
        payload = {
            "record_id": record_id,
            "source_id": row.get("id"),
            "provider": self.client.provider,
            "model": self.client.model,
            "processed_at_utc": datetime.now(timezone.utc).isoformat(),
            "structured": structured,
            "raw_response": raw_response,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=True)

    def _load_response_file(self, path: Path) -> dict[str, Any] | None:
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            structured = payload.get("structured")
            if not isinstance(structured, dict):
                return None
            return _normalize_structured_payload(structured)
        except Exception:
            return None

    def _blank_payload(self) -> dict[str, Any]:
        return {field: _default_value(field) for field in STRUCTURED_FIELDS}

    def _write_failed_llm_log(self, failures: list[dict[str, Any]]) -> None:
        path = self.settings.failed_llm_log_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(failures, handle, indent=2, ensure_ascii=True)


def extract_structured_fields(
    df: pd.DataFrame,
    settings: Settings,
    on_progress: Callable[[int, int], None] | None = None,
) -> pd.DataFrame:
    """Convenience wrapper for extracting structured fields from abstracts."""
    extractor = AbstractStructuringExtractor(settings=settings)
    return extractor.extract_dataframe(df=df, on_progress=on_progress)
