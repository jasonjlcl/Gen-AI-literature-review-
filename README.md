# Automated Literature Review Pipeline

This project provides an end-to-end, production-oriented Python pipeline for automated literature review workflows.

## Overview

1. Ingests OpenAlex exports (`.csv` or `.json`)
2. Cleans and filters records
3. Resolves DOIs asynchronously with retries
4. Extracts 23 structured insight fields from abstracts via LLM
5. Persists per-record LLM outputs for recovery
6. Supports failed-row recovery and merge
7. Writes final dataset to CSV and Parquet with processing metadata

## Documentation

- User guide: `docs/USER_GUIDE.md`
- Technical documentation: `docs/TECHNICAL_DOCUMENTATION.md`
- Publication methods draft: `docs/PUBLICATION_METHODS_DRAFT.md`

## Quick Start

```powershell
py -3 -m venv .venv
.venv\Scripts\activate
py -3 -m pip install -e .[dev]
copy .env.example .env
```

Set your LLM credentials in `.env`.

For Gemini:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-2.5-flash
```

Run:

```powershell
py -3 scripts/run_pipeline.py --input "C:\path\to\openalex_export.csv" --output-dir output
```

## Recovery

If some LLM rows fail:

```powershell
py -3 scripts/recover_failures.py --input "C:\path\to\openalex_export.csv" --output-dir output
```

## Optional GUI

```powershell
py -3 scripts/run_gui.py
```

## Key Output Files

- `output/final_dataset_<run_id>.csv`
- `output/final_dataset_<run_id>.parquet`
- `output/logs/failed_doi_log.json`
- `output/logs/failed_llm_log.json`
- `output/logs/run_metadata_<run_id>.json`
- `output/llm_responses/<record_id>.json`

## Notes

- `OPENALEX_API_KEY` is stored in `.env.example` for future API-based ingestion, but the current pipeline ingests only exported `.csv/.json` files.
- Keep `.env` private and rotate keys if exposed.
