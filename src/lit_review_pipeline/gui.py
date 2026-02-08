"""Optional Tkinter GUI for running the pipeline."""

from __future__ import annotations

import queue
import shutil
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from .pipeline import PipelineResult, run_pipeline


class PipelineGUI(tk.Tk):
    """Simple desktop UI for running pipeline jobs."""

    _STAGE_WEIGHTS = {
        "ingestion": (0, 5),
        "preprocess": (5, 5),
        "doi": (10, 30),
        "llm": (40, 60),
    }

    def __init__(self) -> None:
        super().__init__()
        self.title("Automated Literature Review Pipeline")
        self.geometry("740x320")
        self.resizable(False, False)

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar(value="output")
        self.save_csv_var = tk.StringVar()
        self.provider_var = tk.StringVar(value="gemini")
        self.status_var = tk.StringVar(value="Idle")
        self.progress_var = tk.DoubleVar(value=0.0)

        self._events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._worker: threading.Thread | None = None

        self._build_layout()
        self.after(150, self._poll_events)

    def _build_layout(self) -> None:
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Input file (.csv/.json)").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.input_var, width=70).grid(row=1, column=0, sticky="we", padx=(0, 8))
        ttk.Button(frame, text="Browse", command=self._browse_input).grid(row=1, column=1, sticky="e")

        ttk.Label(frame, text="Output directory").grid(row=2, column=0, sticky="w", pady=(16, 0))
        ttk.Entry(frame, textvariable=self.output_var, width=70).grid(row=3, column=0, sticky="we", padx=(0, 8))
        ttk.Button(frame, text="Browse", command=self._browse_output).grid(row=3, column=1, sticky="e")

        ttk.Label(frame, text="LLM provider").grid(row=4, column=0, sticky="w", pady=(16, 0))
        provider_combo = ttk.Combobox(
            frame,
            textvariable=self.provider_var,
            values=["gemini", "openai"],
            state="readonly",
            width=20,
        )
        provider_combo.grid(row=5, column=0, sticky="w")
        provider_combo.current(0)

        ttk.Label(frame, text="Save CSV output as (optional)").grid(row=6, column=0, sticky="w", pady=(16, 0))
        ttk.Entry(frame, textvariable=self.save_csv_var, width=70).grid(
            row=7,
            column=0,
            sticky="we",
            padx=(0, 8),
        )
        ttk.Button(frame, text="Browse", command=self._browse_save_csv).grid(row=7, column=1, sticky="e")

        self.run_button = ttk.Button(frame, text="Run Pipeline", command=self._start_run)
        self.run_button.grid(row=8, column=0, sticky="w", pady=(20, 4))

        self.progress = ttk.Progressbar(
            frame,
            orient="horizontal",
            mode="determinate",
            maximum=100.0,
            variable=self.progress_var,
            length=600,
        )
        self.progress.grid(row=9, column=0, columnspan=2, sticky="we", pady=(8, 4))

        ttk.Label(frame, textvariable=self.status_var).grid(row=10, column=0, columnspan=2, sticky="w")
        frame.columnconfigure(0, weight=1)

    def _browse_input(self) -> None:
        path = filedialog.askopenfilename(
            title="Select OpenAlex export",
            filetypes=[("Data files", "*.csv *.json"), ("All files", "*.*")],
        )
        if path:
            self.input_var.set(path)

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(title="Select output directory")
        if path:
            self.output_var.set(path)

    def _browse_save_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save output CSV as",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if path:
            self.save_csv_var.set(path)

    def _start_run(self) -> None:
        input_path = self.input_var.get().strip()
        if not input_path:
            messagebox.showerror("Missing input", "Please select an input CSV or JSON file.")
            return

        self.run_button.configure(state="disabled")
        self.progress_var.set(0.0)
        self.status_var.set("Starting pipeline...")

        self._worker = threading.Thread(
            target=self._run_pipeline_worker,
            args=(
                input_path,
                self.output_var.get().strip() or "output",
                self.provider_var.get().strip() or "gemini",
            ),
            daemon=True,
        )
        self._worker.start()

    def _run_pipeline_worker(self, input_path: str, output_dir: str, llm_provider: str) -> None:
        def callback(stage: str, completed: int, total: int) -> None:
            self._events.put(("progress", {"stage": stage, "completed": completed, "total": total}))

        try:
            result = run_pipeline(
                input_path=input_path,
                output_dir=output_dir,
                llm_provider=llm_provider,
                progress_callback=callback,
            )
            self._events.put(("done", result))
        except Exception as exc:
            self._events.put(("error", str(exc)))

    def _poll_events(self) -> None:
        while not self._events.empty():
            event_type, payload = self._events.get()
            if event_type == "progress":
                self._handle_progress(payload)
            elif event_type == "done":
                self._handle_done(payload)
            elif event_type == "error":
                self._handle_error(payload)
        self.after(150, self._poll_events)

    def _handle_progress(self, payload: dict[str, Any]) -> None:
        stage = str(payload["stage"])
        completed = int(payload["completed"])
        total = max(int(payload["total"]), 1)
        base, span = self._STAGE_WEIGHTS.get(stage, (0, 0))
        percent = base + (completed / total) * span
        self.progress_var.set(min(100.0, max(0.0, percent)))
        self.status_var.set(f"{stage.upper()} {completed}/{total}")

    def _handle_done(self, result: PipelineResult) -> None:
        selected_csv = self.save_csv_var.get().strip()
        if selected_csv:
            target_csv = Path(selected_csv)
            target_csv.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(result.output_csv, target_csv)

        self.progress_var.set(100.0)
        self.status_var.set("Completed successfully.")
        self.run_button.configure(state="normal")
        messagebox.showinfo(
            "Pipeline complete",
            (
                f"Run ID: {result.run_id}\n"
                f"CSV: {result.output_csv}\n"
                f"Parquet: {result.output_parquet}"
                + (f"\nSaved CSV: {selected_csv}" if selected_csv else "")
            ),
        )

    def _handle_error(self, error_message: str) -> None:
        self.run_button.configure(state="normal")
        self.status_var.set("Failed.")
        messagebox.showerror("Pipeline failed", error_message)


def launch_gui() -> None:
    app = PipelineGUI()
    app.mainloop()
