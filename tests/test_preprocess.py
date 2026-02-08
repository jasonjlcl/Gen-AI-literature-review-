from __future__ import annotations

import pandas as pd

from lit_review_pipeline.llm_extractor import attach_record_ids
from lit_review_pipeline.preprocess import normalize_text, preprocess_records


def test_normalize_text_collapses_whitespace() -> None:
    assert normalize_text("  a\tb\n c  ") == "a b c"


def test_preprocess_filters_missing_abstract_and_flags_context() -> None:
    df = pd.DataFrame(
        [
            {
                "id": "A",
                "title": "AI for manufacturing quality control",
                "abstract": "We optimize factory operations.",
                "doi": "10.1/abc",
                "publication_year": 2024,
                "type": "article",
            },
            {
                "id": "B",
                "title": "No abstract record",
                "abstract": "",
                "doi": None,
                "publication_year": 2023,
                "type": "article",
            },
        ]
    )

    processed = preprocess_records(df)
    assert len(processed) == 1
    row = processed.iloc[0]
    assert row["id"] == "A"
    assert row["has_abstract"] == 1
    assert row["manufacturing_context"] == 1


def test_attach_record_ids_is_deterministic() -> None:
    df = pd.DataFrame(
        [
            {"id": "A", "title": "t1", "abstract": "a1", "publication_year": 2022, "type": "article"},
            {"id": "B", "title": "t2", "abstract": "a2", "publication_year": 2023, "type": "article"},
        ]
    )
    first = attach_record_ids(df)["record_id"].tolist()
    second = attach_record_ids(df)["record_id"].tolist()
    assert first == second
