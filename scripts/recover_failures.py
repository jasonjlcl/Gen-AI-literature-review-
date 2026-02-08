"""CLI entry point for recovering failed LLM rows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from lit_review_pipeline.recovery import recover_failed_rows


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recover failed LLM rows and merge output.")
    parser.add_argument("--input", required=True, help="Path to original OpenAlex input file.")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory override.",
    )
    parser.add_argument(
        "--llm-provider",
        choices=["gemini", "openai"],
        default=None,
        help="Optional provider override for recovery.",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="Optional path to .env file.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = recover_failed_rows(
        input_path=args.input,
        output_dir=args.output_dir,
        llm_provider=args.llm_provider,
        env_file=args.env_file,
    )
    print("Recovery completed.")
    for key, value in report.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
