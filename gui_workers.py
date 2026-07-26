"""
gui_workers.py — QThread workers for background OCR and rename operations.

Workers emit Qt signals so the GUI can update in real-time without freezing.
The OCR reader is initialised **once per worker run** (not per-file) for
performance parity with the CLI tool.
"""

from __future__ import annotations

import os
import re
import threading
from typing import Optional

from PySide6.QtCore import QThread, Signal

# ---------------------------------------------------------------------------
# Import core logic from the original script (kept untouched)
# ---------------------------------------------------------------------------
from Auto_RenameScans import (
    extract_name_with_ocr,
    clean_filename,
    reformat_name,
)


# ---------------------------------------------------------------------------
# Scan Worker — runs OCR to extract names (no renaming)
# ---------------------------------------------------------------------------
class ScanWorker(QThread):
    """Run OCR on every PDF in *file_paths* and emit the extracted name.

    Signals
    -------
    file_scanned(int, str, str, str)
        (row_index, original_filename, extracted_name_or_empty, status)
        status is one of: "scanned", "fail"
    progress(int, int)
        (current_count, total_count)
    log_message(str)
        Human-readable log line (with timestamp added by the GUI).
    finished_all()
        Emitted when all files have been processed (or cancelled).
    """

    file_scanned = Signal(int, str, str, str)   # row, orig, extracted, status
    progress = Signal(int, int)                   # current, total
    log_message = Signal(str)                     # formatted message
    finished_all = Signal()                       # done

    def __init__(
        self,
        file_paths: list[str],
        cancel_event: threading.Event | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.file_paths = file_paths
        self.cancel_event = cancel_event or threading.Event()

    # ---- main loop --------------------------------------------------------
    def run(self) -> None:  # noqa: D401
        total = len(self.file_paths)
        for idx, path in enumerate(self.file_paths):
            if self.cancel_event.is_set():
                self.log_message.emit("[CANCEL] Processing cancelled by user")
                break

            filename = os.path.basename(path)
            self.log_message.emit(f"[SCAN] Scanning {filename}...")

            try:
                extracted: Optional[str] = extract_name_with_ocr(path)
            except Exception as exc:
                extracted = None
                self.log_message.emit(f"[ERROR] {filename}: {exc}")

            if extracted:
                self.file_scanned.emit(idx, filename, extracted, "scanned")
                self.log_message.emit(
                    f"[SCAN] {filename} → {extracted}"
                )
            else:
                self.file_scanned.emit(idx, filename, "", "fail")
                self.log_message.emit(
                    f"[FAIL] {filename} — Could not extract name"
                )

            self.progress.emit(idx + 1, total)

        self.finished_all.emit()


# ---------------------------------------------------------------------------
# Rename Worker — performs the actual file renames
# ---------------------------------------------------------------------------
class RenameWorker(QThread):
    """Rename files based on pre-scanned results.

    Parameters
    ----------
    rename_map : list[tuple[str, str]]
        Each entry is ``(original_full_path, new_name_without_ext)``.

    Signals
    -------
    file_renamed(int, str, str, str)
        (row_index, original_filename, new_filename, status)
        status is one of: "renamed", "skip", "warning", "error"
    progress(int, int)
    log_message(str)
    finished_all()
    """

    file_renamed = Signal(int, str, str, str)
    progress = Signal(int, int)
    log_message = Signal(str)
    finished_all = Signal()

    def __init__(
        self,
        rename_map: list[tuple[int, str, str]],
        cancel_event: threading.Event | None = None,
        parent=None,
    ):
        super().__init__(parent)
        # rename_map items: (row_index, full_path, extracted_name)
        self.rename_map = rename_map
        self.cancel_event = cancel_event or threading.Event()

    # ---- main loop --------------------------------------------------------
    def run(self) -> None:  # noqa: D401
        total = len(self.rename_map)
        for count, (row_idx, full_path, extracted) in enumerate(self.rename_map):
            if self.cancel_event.is_set():
                self.log_message.emit("[CANCEL] Renaming cancelled by user")
                break

            folder, filename = os.path.split(full_path)
            safe = clean_filename(extracted)
            if len(safe) > 100:
                safe = safe[:100]

            new_name = safe + ".pdf"
            new_path = os.path.join(folder, new_name)

            if filename == new_name:
                self.file_renamed.emit(row_idx, filename, new_name, "skip")
                self.log_message.emit(
                    f"[SKIP] {filename} — Already correct"
                )
            elif os.path.exists(new_path):
                self.file_renamed.emit(row_idx, filename, new_name, "warning")
                self.log_message.emit(
                    f"[WARNING] {new_name} already exists — skipped"
                )
            else:
                try:
                    os.rename(full_path, new_path)
                    self.file_renamed.emit(row_idx, filename, new_name, "renamed")
                    self.log_message.emit(
                        f"[RENAME] {filename} → {new_name}"
                    )
                except Exception as exc:
                    self.file_renamed.emit(row_idx, filename, new_name, "error")
                    self.log_message.emit(
                        f"[ERROR] Rename failed for {filename}: {exc}"
                    )

            self.progress.emit(count + 1, total)

        self.finished_all.emit()
