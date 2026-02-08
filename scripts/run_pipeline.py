"""CLI entry point for running the full literature review pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from lit_review_pipeline.pipeline import run_pipeline


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run automated literature review pipeline.")
    parser.add_argument("--input", required=True, help="Path to OpenAlex .csv or .json export.")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory override (default from .env or output).",
    )
    parser.add_argument(
        "--llm-provider",
        choices=["gemini", "openai"],
        default=None,
        help="Optional LLM provider override.",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="Optional path to .env file.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = run_pipeline(
        input_path=args.input,
        output_dir=args.output_dir,
        llm_provider=args.llm_provider,
        env_file=args.env_file,
    )
    print("Pipeline completed.")
    print(f"Run ID: {result.run_id}")
    print(f"CSV: {result.output_csv}")
    print(f"Parquet: {result.output_parquet}")
    print(f"Run metadata: {result.run_metadata}")


if __name__ == "__main__":
    main()
