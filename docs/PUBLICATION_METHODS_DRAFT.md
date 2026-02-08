# Methods

## Study Design

We implemented a reproducible, end-to-end automated literature review pipeline to transform OpenAlex-exported bibliographic records into a structured analytical dataset. The workflow was designed to support high-throughput screening, metadata enrichment, and large-scale abstraction of study-level insights using a large language model (LLM). The pipeline was developed in Python (3.10+) with modular stages for ingestion, preprocessing, DOI resolution, LLM-based structuring, failure recovery, and audited output generation.

## Data Source and Input Specification

The primary source corpus was exported from OpenAlex in comma-separated values (`.csv`) or JavaScript Object Notation (`.json`) format. The input schema expected the following core attributes: `id`, `title`, `abstract`, `doi`, `publication_year`, and `type`. For OpenAlex records that represented abstracts as an inverted index, the pipeline reconstructed plain-text abstracts before downstream processing.

## Preprocessing and Eligibility Filtering

Preprocessing was performed using `pandas` to standardize and filter records before model-based extraction. Processing included:

1. Unicode normalization (`NFKC`) and whitespace canonicalization for text-bearing fields.
2. Binary flag generation for `has_abstract` (presence/absence of abstract text).
3. Rule-based `manufacturing_context` detection using a predefined keyword heuristic.
4. Exclusion of records lacking abstract text.
5. Deterministic sorting of retained records to ensure reproducible run order.

This stage produced the analysis-ready candidate pool for enrichment and information extraction.

## Asynchronous DOI Enrichment

DOI enrichment was performed asynchronously with `asyncio` and `aiohttp` against a DOI metadata endpoint (Crossref API). For each unique DOI:

1. Requests were executed under bounded concurrency.
2. Failed calls were retried with exponential backoff.
3. Non-retryable DOI client errors were short-circuited.
4. Error states (DOI, status code, attempts, timestamp) were serialized to `failed_doi_log.json`.

Resolved metadata were joined back to record-level rows using DOI keys, with row-level indicators for successful vs failed resolution.

## LLM-Based Abstract Structuring

### Prompting Strategy

Each abstract was processed with a constrained prompt template requiring strict JSON output and explicit enumeration constraints for categorical fields (e.g., AI category, technical complexity, ROI impact, and time horizon). The prompt enforced null/empty-list behavior for unknown values to reduce schema drift.

### Provider Abstraction

The pipeline used a configurable LLM client layer with provider swap capability between Google Gemini (default) and OpenAI. Provider credentials and model names were supplied via environment variables (`.env`) without hard-coding secrets.

### Parallel Extraction and Schema

LLM inference was parallelized with `ThreadPoolExecutor`. For each eligible abstract, the model output was parsed and normalized into 23 structured fields:

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

## Failure Handling and Recovery

To support fault tolerance and resumability:

1. Each successful LLM extraction was stored as an individual JSON artifact (`output/llm_responses/<record_id>.json`).
2. Failed extractions were logged to `failed_llm_log.json` with row identifiers and error traces.
3. Re-execution used skip-if-cached semantics by default, avoiding repeated cost on completed rows.
4. A dedicated recovery script retried failed rows and merged recovered fields into the latest dataset snapshot.

Record-level deterministic identifiers were used to guarantee stable merges and prevent collisions when source identifiers were duplicated.

## Output Artifacts

Each run emitted:

1. A final structured dataset in CSV and Parquet formats.
2. Run metadata with processing timestamps and row-count summaries.
3. DOI and LLM failure logs.
4. Row-level extraction payloads for auditability and replay.

Run metadata included processing start/end timestamps, provider configuration, and failure-log references to support transparent reporting.

## Reproducibility Controls

Reproducibility was operationalized through:

1. Environment-based configuration (`.env`) for all tunable parameters.
2. Fixed random seed configuration.
3. Deterministic preprocessing order.
4. Low-temperature inference defaults for reduced output variance.
5. Persistent intermediate artifacts enabling deterministic partial reruns.

## Quality Assurance

Quality assurance was implemented via:

1. Schema normalization of parsed LLM outputs.
2. Explicit retention of row-level extraction errors (`llm_extraction_error`).
3. Recovery workflows for transient or malformed model outputs.
4. Basic automated test coverage for preprocessing and deterministic identifier behavior.

## Ethical and Reporting Considerations

This pipeline automates abstraction and categorization but does not replace domain-expert interpretation. LLM-derived fields should be treated as machine-assisted annotations and validated for high-stakes conclusions. Any publication should report:

1. Provider/model versions used.
2. Prompt template and constrained schema design.
3. Extraction failure rates and recovery procedures.
4. Residual unresolved rows and potential annotation bias.

## Suggested Manuscript Adaptation Notes

Before submission, replace this generic wording with study-specific values:

1. Exact corpus size and date window.
2. Final inclusion/exclusion counts.
3. DOI success/failure rates.
4. LLM extraction success and post-recovery success rates.
5. Any manual validation protocol (e.g., dual review subset, inter-rater checks).
