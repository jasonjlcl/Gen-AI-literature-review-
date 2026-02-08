"""Input loading for OpenAlex exports."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from .constants import REQUIRED_COLUMNS

LOGGER = logging.getLogger(__name__)


def _inverted_index_to_text(inverted_index: dict[str, list[int]]) -> str:
    """
    Convert OpenAlex abstract inverted index to plain text.

    OpenAlex may provide `abstract_inverted_index` where keys are terms and values
    are token positions.
    """
    if not inverted_index:
        return ""

    positions: dict[int, str] = {}
    for token, indexes in inverted_index.items():
        for idx in indexes:
            positions[idx] = token
    return " ".join(token for _, token in sorted(positions.items(), key=lambda x: x[0]))


def _normalize_openalex_schema(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize source columns to expected pipeline schema."""
    df = frame.copy()

    if "abstract" not in df.columns and "abstract_inverted_index" in df.columns:
        df["abstract"] = df["abstract_inverted_index"].apply(
            lambda x: _inverted_index_to_text(x) if isinstance(x, dict) else ""
        )

    for column in REQUIRED_COLUMNS:
        if column not in df.columns:
            df[column] = None

    # Normalize DOI string format.
    df["doi"] = (
        df["doi"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.replace(r"^https?://doi\.org/", "", regex=True, case=False)
        .str.replace(r"^doi:\s*", "", regex=True, case=False)
        .str.strip()
    )
    df.loc[df["doi"] == "", "doi"] = None

    return df


def _load_json(path: Path) -> pd.DataFrame:
    with path.open("r", encoding="utf-8") as handle:
        payload: Any = json.load(handle)

    if isinstance(payload, dict):
        if "results" in payload and isinstance(payload["results"], list):
            return pd.json_normalize(payload["results"])
        return pd.json_normalize(payload)

    if isinstance(payload, list):
        return pd.json_normalize(payload)

    raise ValueError(f"Unsupported JSON structure in {path}.")


def load_openalex_data(input_path: str | Path) -> pd.DataFrame:
    """Load OpenAlex export from CSV or JSON into a DataFrame."""
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file does not exist: {path}")

    suffix = path.suffix.lower()
    if suffix == ".csv":
        raw_df = pd.read_csv(path)
    elif suffix == ".json":
        raw_df = _load_json(path)
    else:
        raise ValueError("Input file must be .csv or .json")

    LOGGER.info("Loaded %s records from %s", len(raw_df), path)
    normalized = _normalize_openalex_schema(raw_df)
    return normalized
