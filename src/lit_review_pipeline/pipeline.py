"""End-to-end pipeline orchestration."""

from __future__ import annotations

import asyncio
import json
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from .config import Settings
from .doi_resolver import AsyncDOIResolver
from .ingestion import load_openalex_data
from .llm_extractor import extract_structured_fields
from .logging_utils import configure_logging
from .preprocess import preprocess_records

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class PipelineResult:
    run_id: str
    final_dataframe: pd.DataFrame
    output_csv: Path
    output_parquet: Path
    run_metadata: Path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_serializable(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    return value


def _serialize_complex_columns(df: pd.DataFrame) -> pd.DataFrame:
    serializable = df.copy()
    for col in serializable.columns:
        if serializable[col].apply(lambda v: isinstance(v, (dict, list))).any():
            serializable[col] = serializable[col].apply(_ensure_serializable)
    return serializable


def _run_async(coro: Any) -> Any:
    try:
        return asyncio.run(coro)
    except RuntimeError as exc:
        # Supports environments where an event loop is already active.
        if "asyncio.run() cannot be called from a running event loop" not in str(exc):
            raise
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def run_pipeline(
    input_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    llm_provider: str | None = None,
    env_file: str | Path | None = None,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> PipelineResult:
    """
    Execute the full literature review pipeline.

    Parameters
    ----------
    input_path:
        Path to OpenAlex input export (.csv/.json).
    output_dir:
        Optional output override.
    llm_provider:
        Optional provider override (`gemini` or `openai`).
    env_file:
        Optional .env location.
    progress_callback:
        Callback receiving `(stage, completed, total)`.
    """
    settings = Settings.from_env(env_file=env_file)
    if output_dir is not None:
        settings.output_dir = Path(output_dir)
    if llm_provider is not None:
        settings.llm_provider = llm_provider.strip().lower()
    settings.ensure_directories()

    configure_logging(
        level=settings.log_level,
        log_file=settings.logs_dir / "pipeline.log",
    )
    random.seed(settings.seed)

    started_at = _utc_now_iso()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    LOGGER.info("Pipeline run started: %s", run_id)

    if progress_callback:
        progress_callback("ingestion", 0, 1)
    ingested = load_openalex_data(input_path)
    if progress_callback:
        progress_callback("ingestion", 1, 1)

    if progress_callback:
        progress_callback("preprocess", 0, 1)
    cleaned = preprocess_records(ingested)
    if progress_callback:
        progress_callback("preprocess", 1, 1)

    resolver = AsyncDOIResolver(settings=settings)
    doi_total = int(cleaned["doi"].fillna("").astype(str).str.strip().replace("", pd.NA).dropna().nunique())
    if progress_callback:
        progress_callback("doi", 0, max(1, doi_total))

    enriched = _run_async(
        resolver.resolve_dataframe(
            cleaned,
            on_progress=(
                (lambda c, t: progress_callback("doi", c, t))
                if progress_callback
                else None
            ),
        )
    )

    llm_enriched = extract_structured_fields(
        enriched,
        settings=settings,
        on_progress=(lambda c, t: progress_callback("llm", c, t)) if progress_callback else None,
    )

    completed_at = _utc_now_iso()
    llm_enriched["run_id"] = run_id
    llm_enriched["processed_at_utc"] = completed_at
    llm_enriched["pipeline_started_at_utc"] = started_at
    llm_enriched["pipeline_completed_at_utc"] = completed_at
    llm_enriched["pipeline_seed"] = settings.seed

    write_df = _serialize_complex_columns(llm_enriched)
    output_csv = settings.output_dir / f"final_dataset_{run_id}.csv"
    output_parquet = settings.output_dir / f"final_dataset_{run_id}.parquet"
    write_df.to_csv(output_csv, index=False)
    write_df.to_parquet(output_parquet, index=False)

    metadata = {
        "run_id": run_id,
        "input_path": str(input_path),
        "output_csv": str(output_csv),
        "output_parquet": str(output_parquet),
        "started_at_utc": started_at,
        "completed_at_utc": completed_at,
        "llm_provider": settings.llm_provider,
        "llm_temperature": settings.llm_temperature,
        "row_counts": {
            "ingested": int(len(ingested)),
            "after_preprocess": int(len(cleaned)),
            "final": int(len(llm_enriched)),
        },
        "failure_logs": {
            "doi": str(settings.failed_doi_log_path),
            "llm": str(settings.failed_llm_log_path),
        },
    }
    run_metadata_path = settings.logs_dir / f"run_metadata_{run_id}.json"
    with run_metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, ensure_ascii=True)

    LOGGER.info("Pipeline completed: csv=%s parquet=%s", output_csv, output_parquet)
    return PipelineResult(
        run_id=run_id,
        final_dataframe=llm_enriched,
        output_csv=output_csv,
        output_parquet=output_parquet,
        run_metadata=run_metadata_path,
    )
