"""Data cleaning and heuristic enrichment."""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

from .constants import MANUFACTURING_KEYWORDS

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(value: str | None) -> str:
    """Normalize textual values to stable, whitespace-collapsed strings."""
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(value)).strip()
    return _WHITESPACE_RE.sub(" ", normalized)


def has_manufacturing_context(title: str, abstract: str) -> int:
    """Simple keyword heuristic for manufacturing relevance."""
    combined = f"{title} {abstract}".lower()
    return int(any(keyword in combined for keyword in MANUFACTURING_KEYWORDS))


def preprocess_records(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and enrich records.

    - Normalizes text fields
    - Adds `has_abstract` and `manufacturing_context` binary flags
    - Drops rows without abstracts
    - Sorts records deterministically
    """
    records = df.copy()

    for col in ("title", "abstract", "type", "id"):
        if col not in records.columns:
            records[col] = ""
        records[col] = records[col].apply(normalize_text)

    records["has_abstract"] = records["abstract"].apply(lambda x: int(bool(x.strip())))
    records = records[records["has_abstract"] == 1].copy()

    records["manufacturing_context"] = records.apply(
        lambda row: has_manufacturing_context(
            title=row.get("title", ""),
            abstract=row.get("abstract", ""),
        ),
        axis=1,
    )

    if "publication_year" in records.columns:
        records["publication_year"] = pd.to_numeric(
            records["publication_year"],
            errors="coerce",
        ).astype("Int64")

    sort_columns = [col for col in ("id", "publication_year", "title") if col in records.columns]
    records = records.sort_values(by=sort_columns, kind="mergesort").reset_index(drop=True)
    return records
