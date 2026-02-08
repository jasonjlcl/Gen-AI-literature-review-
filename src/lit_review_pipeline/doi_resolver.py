"""Asynchronous DOI resolution with retry and persistent failure logs."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import aiohttp
import pandas as pd

from .config import Settings

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DOIResolutionResult:
    doi: str
    resolved: bool
    metadata: dict[str, Any] | None
    error: str | None
    status_code: int | None
    attempts: int


class AsyncDOIResolver:
    """Resolve DOI metadata via Crossref using asynchronous HTTP calls."""

    BASE_URL = "https://api.crossref.org/works/"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def resolve_dataframe(
        self,
        df: pd.DataFrame,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> pd.DataFrame:
        """Resolve all unique DOIs in a DataFrame and append metadata columns."""
        records = df.copy()
        records["doi"] = records.get("doi", "").fillna("").astype(str).str.strip()

        dois = sorted({doi for doi in records["doi"] if doi})
        if not dois:
            records["doi_resolved"] = 0
            records["doi_resolution_error"] = None
            records["doi_metadata"] = None
            self._write_failures([])
            return records

        timeout = aiohttp.ClientTimeout(total=self.settings.doi_timeout_seconds)
        semaphore = asyncio.Semaphore(self.settings.doi_concurrency)

        metadata_by_doi: dict[str, dict[str, Any]] = {}
        errors_by_doi: dict[str, str] = {}
        failures: list[dict[str, Any]] = []

        processed = 0
        async with aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "User-Agent": "automated-literature-review/0.1 (research-automation)",
            },
        ) as session:
            tasks = [self._resolve_with_retry(session, semaphore, doi) for doi in dois]
            for future in asyncio.as_completed(tasks):
                result = await future
                processed += 1
                if on_progress is not None:
                    on_progress(processed, len(dois))

                if result.resolved and result.metadata is not None:
                    metadata_by_doi[result.doi] = result.metadata
                else:
                    error_text = result.error or "Unknown error"
                    errors_by_doi[result.doi] = error_text
                    failures.append(
                        {
                            "doi": result.doi,
                            "error": error_text,
                            "status_code": result.status_code,
                            "attempts": result.attempts,
                            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        }
                    )

        self._write_failures(failures)
        LOGGER.info(
            "DOI resolution finished: %s resolved, %s failed",
            len(metadata_by_doi),
            len(failures),
        )

        records["doi_resolved"] = records["doi"].map(lambda d: int(bool(d and d in metadata_by_doi)))
        records["doi_resolution_error"] = records["doi"].map(
            lambda d: errors_by_doi.get(d) if d else None
        )
        records["doi_metadata"] = records["doi"].map(lambda d: metadata_by_doi.get(d) if d else None)
        return records

    async def _resolve_with_retry(
        self,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        doi: str,
    ) -> DOIResolutionResult:
        status_code: int | None = None
        last_error: str | None = None

        for attempt in range(1, self.settings.doi_max_retries + 1):
            try:
                async with semaphore:
                    url = f"{self.BASE_URL}{quote(doi, safe='')}"
                    async with session.get(url) as response:
                        status_code = response.status
                        if response.status == 200:
                            payload = await response.json()
                            metadata = payload.get("message", payload)
                            return DOIResolutionResult(
                                doi=doi,
                                resolved=True,
                                metadata=metadata,
                                error=None,
                                status_code=200,
                                attempts=attempt,
                            )

                        text = await response.text()
                        last_error = f"HTTP {response.status}: {text[:300]}"

                        if response.status in {400, 404}:
                            # Client-side DOI issues are not retried.
                            break

            except asyncio.TimeoutError:
                last_error = f"Timeout after {self.settings.doi_timeout_seconds}s"
            except aiohttp.ClientError as exc:
                last_error = f"ClientError: {exc}"
            except Exception as exc:  # pragma: no cover - defensive guard.
                last_error = f"UnexpectedError: {exc}"

            if attempt < self.settings.doi_max_retries:
                delay = self.settings.doi_retry_base_delay * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

        return DOIResolutionResult(
            doi=doi,
            resolved=False,
            metadata=None,
            error=last_error,
            status_code=status_code,
            attempts=self.settings.doi_max_retries,
        )

    def _write_failures(self, failures: list[dict[str, Any]]) -> None:
        path: Path = self.settings.failed_doi_log_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(failures, handle, indent=2, ensure_ascii=True)
