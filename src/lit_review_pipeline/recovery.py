"""Failure recovery utilities for LLM extraction."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .config import Settings
from .constants import STRUCTURED_FIELDS
from .ingestion import load_openalex_data
from .llm_extractor import attach_record_ids, extract_structured_fields
from .logging_utils import configure_logging
from .preprocess import preprocess_records

LOGGER = logging.getLogger(__name__)


def _latest_final_csv(output_dir: Path) -> Path:
    candidates = sorted(output_dir.glob("final_dataset_*.csv"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"No final dataset CSV files found in {output_dir}")
    return candidates[-1]


def _load_failed_record_ids(failed_log_path: Path) -> list[str]:
    if not failed_log_path.exists():
        return []
    with failed_log_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    ids = [item.get("record_id", "") for item in payload if isinstance(item, dict)]
    return [record_id for record_id in ids if record_id]


def recover_failed_rows(
    input_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    env_file: str | Path | None = None,
    llm_provider: str | None = None,
) -> dict[str, Any]:
    """
    Re-run failed LLM rows and merge recovered values into the latest final dataset.
    """
    settings = Settings.from_env(env_file=env_file)
    if output_dir is not None:
        settings.output_dir = Path(output_dir)
    if llm_provider is not None:
        settings.llm_provider = llm_provider.strip().lower()
    settings.ensure_directories()

    configure_logging(level=settings.log_level, log_file=settings.logs_dir / "pipeline.log")

    failed_ids = _load_failed_record_ids(settings.failed_llm_log_path)
    if not failed_ids:
        LOGGER.info("No failed LLM rows to recover.")
        return {"recovered_rows": 0, "message": "No failed rows found."}

    source = attach_record_ids(preprocess_records(load_openalex_data(input_path)))
    latest_csv = _latest_final_csv(settings.output_dir)
    latest_df = pd.read_csv(latest_csv)

    if "record_id" not in latest_df.columns:
        raise ValueError("Latest output file does not contain `record_id` column.")

    recover_subset = source[source["record_id"].isin(failed_ids)].copy()

    # If record IDs are unavailable on the source subset, fall back to latest dataset rows.
    if recover_subset.empty:
        recover_subset = latest_df[latest_df["record_id"].isin(failed_ids)][
            [c for c in ("record_id", "id", "title", "abstract", "publication_year", "type") if c in latest_df.columns]
        ].copy()

    if recover_subset.empty:
        LOGGER.info("No matching failed rows found in source data.")
        return {"recovered_rows": 0, "message": "No matching failed rows."}

    original_overwrite = settings.overwrite_existing_responses
    settings.overwrite_existing_responses = True
    recovered = extract_structured_fields(recover_subset, settings=settings)
    settings.overwrite_existing_responses = original_overwrite

    recovered_success = (
        recovered[recovered["llm_extraction_error"].isna()].copy()
        if "llm_extraction_error" in recovered.columns
        else recovered.copy()
    )
    recovered_cols = ["record_id", *STRUCTURED_FIELDS, "llm_provider", "llm_model", "llm_extraction_error"]
    recovered_cols = [c for c in recovered_cols if c in recovered_success.columns]
    recovered_patch = (
        recovered_success[recovered_cols].drop_duplicates(subset=["record_id"]).set_index("record_id")
    )

    merged = latest_df.set_index("record_id")
    merged.update(recovered_patch)
    merged = merged.reset_index()
    recovered_record_ids = set(recovered_patch.index.tolist())
    if recovered_record_ids and "llm_extraction_error" in merged.columns:
        merged.loc[
            merged["record_id"].isin(recovered_record_ids),
            "llm_extraction_error",
        ] = None
    merged["recovery_applied_at_utc"] = datetime.now(timezone.utc).isoformat()

    for col in merged.columns:
        if merged[col].apply(lambda v: isinstance(v, (dict, list))).any():
            merged[col] = merged[col].apply(
                lambda v: json.dumps(v, ensure_ascii=True, sort_keys=True)
                if isinstance(v, (dict, list))
                else v
            )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    recovered_csv = settings.output_dir / f"final_dataset_{stamp}_recovered.csv"
    recovered_parquet = settings.output_dir / f"final_dataset_{stamp}_recovered.parquet"
    merged.to_csv(recovered_csv, index=False)
    merged.to_parquet(recovered_parquet, index=False)

    report = {
        "failed_rows_requested": int(len(failed_ids)),
        "rows_retried": int(len(recover_subset)),
        "recovered_rows": int(len(recovered_patch)),
        "source_latest_csv": str(latest_csv),
        "output_csv": str(recovered_csv),
        "output_parquet": str(recovered_parquet),
    }
    report_path = settings.logs_dir / f"recovery_report_{stamp}.json"
    with report_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=True)

    LOGGER.info("Recovered %s rows. Output: %s", len(recovered_patch), recovered_csv)
    return report
