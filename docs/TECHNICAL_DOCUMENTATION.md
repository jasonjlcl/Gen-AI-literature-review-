# Technical Documentation

## Purpose

This document describes architecture, modules, data flow, configuration, and extension points for maintainers.

## Architecture

The pipeline is organized as a modular package in `src/lit_review_pipeline`.

Core flow:

1. `ingestion.py` loads OpenAlex export (`.csv`/`.json`) into DataFrame.
2. `preprocess.py` normalizes text, filters missing abstracts, adds heuristic flags.
3. `doi_resolver.py` resolves DOI metadata via async `aiohttp` with retries/backoff.
4. `llm_extractor.py` runs threaded LLM extraction and persists one JSON per record.
5. `pipeline.py` orchestrates end-to-end flow and writes final outputs + run metadata.
6. `recovery.py` retries failed LLM rows and merges recovered structured fields.

## Key Design Decisions

### Deterministic Record IDs

- `record_id` is deterministic and unique per row.
- If source IDs repeat, ordinal suffixes are added:
  - `base_id__1`, `base_id__2`, ...
- This prevents collisions in `output/llm_responses`.

### Recovery-First Persistence

- Every successful LLM extraction is persisted to `output/llm_responses/<record_id>.json`.
- Future runs skip already processed records unless `OVERWRITE_EXISTING_RESPONSES=true`.
- Recovery uses `failed_llm_log.json` as retry source of truth.

### Reproducibility

1. Preprocessing sorts records deterministically.
2. Seed is configurable via `PIPELINE_SEED`.
3. LLM temperature defaults to `0.0`.

## Module Reference

`config.py`:
- Loads `.env` and computes output/log paths.

`constants.py`:
- Required source columns, manufacturing keyword list, structured LLM fields.

`ingestion.py`:
- Supports CSV and JSON input.
- Converts `abstract_inverted_index` to plain text when needed.
- Normalizes DOI strings.

`preprocess.py`:
- Normalizes text using Unicode NFKC and whitespace collapsing.
- Adds `has_abstract`.
- Adds `manufacturing_context` heuristic.
- Drops rows without abstracts.

`doi_resolver.py`:
- Uses `asyncio` + `aiohttp`.
- Retry strategy: exponential backoff based on `DOI_RETRY_BASE_DELAY`.
- Logs failures to `output/logs/failed_doi_log.json`.

`clients/`:
- `base.py`: abstract LLM client contract.
- `gemini_client.py`: Google Generative Language REST integration.
- `openai_client.py`: OpenAI Chat Completions REST integration.

`llm_extractor.py`:
- Uses `ThreadPoolExecutor`.
- Builds prompt from template at `PROMPT_TEMPLATE_PATH`.
- Parses strict JSON response and normalizes 23 fields.
- Writes row-level response JSON.
- Writes `failed_llm_log.json`.

`pipeline.py`:
- Coordinates all stages.
- Adds processing metadata columns.
- Serializes list/dict columns before output.
- Writes CSV, Parquet, and run metadata JSON.

`recovery.py`:
- Loads latest final dataset.
- Retries failed LLM rows with overwrite enabled.
- Merges recovered fields by `record_id`.
- Writes recovered CSV/Parquet and recovery report JSON.

## CLI and GUI Entrypoints

CLI:

1. `scripts/run_pipeline.py`
2. `scripts/recover_failures.py`
3. `python -m lit_review_pipeline`

GUI:

1. `scripts/run_gui.py`
2. Tkinter front-end in `gui.py` with progress updates by stage.

## Configuration Reference

Core:

1. `PIPELINE_LOG_LEVEL`
2. `PIPELINE_SEED`
3. `OUTPUT_DIR`
4. `PROMPT_TEMPLATE_PATH`

DOI resolver:

1. `DOI_CONCURRENCY`
2. `DOI_TIMEOUT_SECONDS`
3. `DOI_MAX_RETRIES`
4. `DOI_RETRY_BASE_DELAY`

LLM extraction:

1. `LLM_PROVIDER` (`gemini` or `openai`)
2. `LLM_MAX_WORKERS`
3. `LLM_REQUEST_TIMEOUT_SECONDS`
4. `LLM_TEMPERATURE`
5. `OVERWRITE_EXISTING_RESPONSES`

Provider keys/models:

1. `GEMINI_API_KEY`
2. `GEMINI_MODEL`
3. `OPENAI_API_KEY`
4. `OPENAI_MODEL`
5. `OPENALEX_API_KEY` (reserved for future API-based ingestion)

## Data Contracts

Input expected fields:

1. `id`
2. `title`
3. `abstract` or `abstract_inverted_index`
4. `doi`
5. `publication_year`
6. `type`

Structured LLM output fields:

1. `use_cases`
2. `opportunities`
3. `challenges`
4. `ai_category`
5. `business_function`
6. `technical_complexity`
7. `roi_impact`
8. `time_horizon`
9. `industry_segment`
10. `implementation_stage`
11. `data_requirements`
12. `model_family`
13. `deployment_pattern`
14. `human_in_the_loop`
15. `risk_factors`
16. `compliance_considerations`
17. `kpis`
18. `stakeholders`
19. `cost_profile`
20. `scalability`
21. `integration_complexity`
22. `confidence_score`
23. `concise_summary`

## Failure Modes

LLM failures:

1. Malformed JSON responses.
2. Provider API transient errors.
3. Invalid or unavailable model names.

DOI failures:

1. Invalid DOI values in input.
2. Missing DOI values.
3. API/network errors.

Recommended handling:

1. Keep per-row response cache.
2. Run `recover_failures.py` after main run.
3. Review remaining `llm_extraction_error` rows for manual fix or parser fallback logic.

## Extension Points

1. Add new provider by implementing `BaseLLMClient` and wiring `create_llm_client`.
2. Replace keyword heuristic in `preprocess.py` with a classifier.
3. Add OpenAlex API ingestion module that uses `OPENALEX_API_KEY`.
4. Add JSON repair fallback in `llm_extractor.py` to recover malformed responses.
5. Add richer analytics/reporting module over final CSV/Parquet outputs.

## Operational Recommendations

1. Use versioned output directories for production jobs.
2. Archive `run_metadata_*.json` and failure logs for traceability.
3. Rotate API keys if exposed.
4. Pin provider models in `.env` to avoid behavior drift.
