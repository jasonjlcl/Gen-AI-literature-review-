# User Guide

## Who This Is For

This guide is for researchers and analysts who want to run the pipeline without modifying code.

## What You Need

1. Windows PowerShell (examples below use PowerShell).
2. Python 3.10+ (`py -3 --version`).
3. One OpenAlex export file in `.csv` or `.json`.
4. At least one LLM API key (`GEMINI_API_KEY` for Gemini or `OPENAI_API_KEY` for OpenAI).

## 1. Setup

From the project root:

```powershell
py -3 -m venv .venv
.venv\Scripts\activate
py -3 -m pip install -e .[dev]
copy .env.example .env
```

## 2. Configure `.env`

Open `.env` and set your provider and key.

Gemini example:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_real_key
GEMINI_MODEL=gemini-2.5-flash
```

OpenAI example:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_real_key
OPENAI_MODEL=gpt-4o-mini
```

Important:
1. Do not wrap keys in quotes.
2. Keep `.env` private.
3. `OPENALEX_API_KEY` is optional in current version (ingestion is from exports, not direct API pull).

## 3. Prepare Input

Place your OpenAlex export in a known path, for example:

- `C:\Users\User\OneDrive\Documents\Automated Literature review\works-csv-abc123.csv`

Expected important fields include:

- `id`, `title`, `abstract`, `doi`, `publication_year`, `type`

If OpenAlex provides `abstract_inverted_index`, the pipeline converts it to plain text.

## 4. Run The Pipeline (CLI)

```powershell
py -3 scripts/run_pipeline.py --input "C:\path\to\openalex_export.csv" --output-dir output
```

Optional overrides:

```powershell
py -3 scripts/run_pipeline.py --input "C:\path\to\openalex_export.csv" --llm-provider openai --env-file ".env"
```

What the run does:
1. Loads input.
2. Removes records without abstracts.
3. Adds `has_abstract` and `manufacturing_context`.
4. Resolves DOI metadata asynchronously.
5. Extracts 23 structured LLM fields.
6. Writes CSV + Parquet + logs.

## 5. Run The Pipeline (GUI)

```powershell
py -3 scripts/run_gui.py
```

In GUI:
1. Select input file.
2. Select output folder.
3. Choose LLM provider.
4. Optional: choose `Save CSV output as`.
5. Click `Run Pipeline`.

## 6. Recovery Workflow

If LLM rows fail due to malformed JSON, transient API errors, or timeouts:

```powershell
py -3 scripts/recover_failures.py --input "C:\path\to\openalex_export.csv" --output-dir output
```

This script:
1. Reads `output/logs/failed_llm_log.json`.
2. Retries failed rows.
3. Merges successful recoveries into the latest dataset.
4. Writes `final_dataset_<timestamp>_recovered.csv` and `.parquet`.

## 7. Outputs

Main artifacts:

1. `output/final_dataset_<run_id>.csv`
2. `output/final_dataset_<run_id>.parquet`
3. `output/logs/run_metadata_<run_id>.json`
4. `output/logs/failed_doi_log.json`
5. `output/logs/failed_llm_log.json`
6. `output/llm_responses/<record_id>.json`

## 8. Interpreting Common Fields

Operational fields:

1. `record_id`: unique deterministic row identifier.
2. `has_abstract`: `1` if abstract exists.
3. `manufacturing_context`: `1` if heuristic keywords match.
4. `doi_resolved`: `1` if DOI metadata retrieval succeeded.
5. `llm_extraction_error`: populated if LLM parsing/extraction failed.

LLM structured fields include:

1. `use_cases`
2. `opportunities`
3. `challenges`
4. `ai_category`
5. `business_function`
6. `technical_complexity`
7. `roi_impact`
8. `time_horizon`
9. plus additional implementation and risk fields (23 total).

## 9. Troubleshooting

`404 ... models/...:generateContent`:
1. Model name is unavailable for your key.
2. Use a currently available model, e.g. `GEMINI_MODEL=gemini-2.5-flash`.

`No module named pytest`:
1. Install dependencies: `py -3 -m pip install -e .[dev]`.

Run takes long:
1. Large datasets can take significant time with LLM extraction.
2. Progress is recoverable due to per-row JSON caching in `output/llm_responses`.

Many DOI failures:
1. This may be expected for missing/invalid DOI values in source exports.
2. Check `output/logs/failed_doi_log.json`.

## 10. Recommended Operating Pattern

1. Run initial full pipeline.
2. Inspect `failed_llm_log.json`.
3. Run recovery script.
4. Use latest recovered output for analysis.
5. Archive output folder per run for reproducibility.
