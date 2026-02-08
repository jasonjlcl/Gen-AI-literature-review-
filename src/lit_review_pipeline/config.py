"""Configuration loading for the literature review pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _as_int(value: str | None, default: int) -> int:
    if value is None or value.strip() == "":
        return default
    return int(value)


def _as_float(value: str | None, default: float) -> float:
    if value is None or value.strip() == "":
        return default
    return float(value)


@dataclass(slots=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    output_dir: Path
    log_level: str
    seed: int
    prompt_template_path: Path
    overwrite_existing_responses: bool

    doi_concurrency: int
    doi_timeout_seconds: int
    doi_max_retries: int
    doi_retry_base_delay: float

    llm_provider: str
    llm_max_workers: int
    llm_request_timeout_seconds: int
    llm_temperature: float

    gemini_api_key: str
    gemini_model: str

    openai_api_key: str
    openai_model: str

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> "Settings":
        """Create settings from process environment and optional .env file."""
        load_dotenv(dotenv_path=env_file)

        output_dir = Path(os.getenv("OUTPUT_DIR", "output"))
        return cls(
            output_dir=output_dir,
            log_level=os.getenv("PIPELINE_LOG_LEVEL", "INFO"),
            seed=_as_int(os.getenv("PIPELINE_SEED"), 42),
            prompt_template_path=Path(
                os.getenv("PROMPT_TEMPLATE_PATH", "prompts/abstract_structuring_prompt.txt")
            ),
            overwrite_existing_responses=_as_bool(
                os.getenv("OVERWRITE_EXISTING_RESPONSES"),
                default=False,
            ),
            doi_concurrency=_as_int(os.getenv("DOI_CONCURRENCY"), 20),
            doi_timeout_seconds=_as_int(os.getenv("DOI_TIMEOUT_SECONDS"), 30),
            doi_max_retries=_as_int(os.getenv("DOI_MAX_RETRIES"), 3),
            doi_retry_base_delay=_as_float(os.getenv("DOI_RETRY_BASE_DELAY"), 1.5),
            llm_provider=os.getenv("LLM_PROVIDER", "gemini").strip().lower(),
            llm_max_workers=_as_int(os.getenv("LLM_MAX_WORKERS"), 8),
            llm_request_timeout_seconds=_as_int(
                os.getenv("LLM_REQUEST_TIMEOUT_SECONDS"),
                60,
            ),
            llm_temperature=_as_float(os.getenv("LLM_TEMPERATURE"), 0.0),
            gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip(),
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
        )

    @property
    def logs_dir(self) -> Path:
        return self.output_dir / "logs"

    @property
    def llm_responses_dir(self) -> Path:
        return self.output_dir / "llm_responses"

    @property
    def failed_doi_log_path(self) -> Path:
        return self.logs_dir / "failed_doi_log.json"

    @property
    def failed_llm_log_path(self) -> Path:
        return self.logs_dir / "failed_llm_log.json"

    def ensure_directories(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.llm_responses_dir.mkdir(parents=True, exist_ok=True)
