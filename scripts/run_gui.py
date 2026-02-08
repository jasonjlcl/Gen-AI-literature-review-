"""Launch Tkinter GUI for the pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from lit_review_pipeline.gui import launch_gui


if __name__ == "__main__":
    launch_gui()
