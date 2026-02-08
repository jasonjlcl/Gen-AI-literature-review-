"""Module entry point for `python -m lit_review_pipeline`."""

from __future__ import annotations

import argparse

from .pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the literature review pipeline.")
    parser.add_argument("--input", required=True, help="Path to OpenAlex export (.csv/.json).")
    parser.add_argument("--output-dir", default=None, help="Optional output directory override.")
    parser.add_argument(
        "--llm-provider",
        choices=["gemini", "openai"],
        default=None,
        help="Optional LLM provider override.",
    )
    parser.add_argument("--env-file", default=None, help="Optional .env file path.")
    args = parser.parse_args()

    result = run_pipeline(
        input_path=args.input,
        output_dir=args.output_dir,
        llm_provider=args.llm_provider,
        env_file=args.env_file,
    )
    print(f"Run complete: {result.run_id}")
    print(f"CSV: {result.output_csv}")
    print(f"Parquet: {result.output_parquet}")


if __name__ == "__main__":
    main()
