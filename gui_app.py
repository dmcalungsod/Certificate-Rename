"""
gui_app.py — Modern PySide6 GUI for the Certificate Renamer tool.

Launch with:  python gui_app.py
"""

from __future__ import annotations

import os
import sys
import threading
from datetime import datetime

from PySide6.QtCore import Qt, QUrl, QMimeData
from PySide6.QtGui import QDesktopServices, QFont, QIcon, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui_styles import get_stylesheet, STATUS_COLORS, LOG_COLORS
from gui_workers import ScanWorker, RenameWorker


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
APP_TITLE = "Certificate Renamer"
APP_VERSION = "0.0.0.2"
MIN_WIDTH, MIN_HEIGHT = 960, 700


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def _make_status_html(label: str, color: str) -> str:
    return (
        f'<span style="background:{color}22; color:{color}; '
        f'padding:2px 10px; border-radius:4px; font-weight:600; '
        f'font-size:11px;">{label.upper()}</span>'
    )


class StatusWidget(QLabel):
    """Tiny coloured badge label for the table status column."""

    def __init__(self, text: str, status_key: str, parent=None):
        super().__init__(parent)
        colour = STATUS_COLORS.get(status_key, STATUS_COLORS["pending"])
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            f"background-color: {colour}22; color: {colour}; "
            f"border-radius: 4px; padding: 3px 10px; "
            f"font-weight: 700; font-size: 11px; border: none;"
        )
        self.setText(text.upper())


# ---------------------------------------------------------------------------
# Drop Zone Widget
# ---------------------------------------------------------------------------

class DropZone(QFrame):
    """A dashed-border frame that accepts folder drag-and-drop."""

    def __init__(self, on_folder_selected, parent=None):
        super().__init__(parent)
        self.setObjectName("drop_zone")
        self.setAcceptDrops(True)
        self._callback = on_folder_selected

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(6)

        icon_lbl = QLabel("📁")
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 28px; border: none; background: transparent;")
        layout.addWidget(icon_lbl)

        text_lbl = QLabel("Drop a folder here or click Browse")
        text_lbl.setAlignment(Qt.AlignCenter)
        text_lbl.setStyleSheet("font-size: 13px; font-weight: 600; border: none; background: transparent;")
        layout.addWidget(text_lbl)

        self.path_label = QLabel("")
        self.path_label.setObjectName("path_label")
        self.path_label.setAlignment(Qt.AlignCenter)
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

    # ---- Drag & Drop -------------------------------------------------------
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        mime: QMimeData = event.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile() and os.path.isdir(url.toLocalFile()):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isdir(path):
                self._callback(path)
                return


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_TITLE}  v{APP_VERSION}")
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)
        self.resize(1060, 760)

        # State
        self._theme = "dark"
        self._folder: str = ""
        self._pdf_paths: list[str] = []
        self._scan_results: dict[int, str] = {}  # row -> extracted name
        self._cancel_event = threading.Event()
        self._worker: ScanWorker | RenameWorker | None = None
        self._settings_visible = False

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(0)

        self._main_layout = QVBoxLayout()
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(14)
        root.addLayout(self._main_layout)

        # Build sections
        self._build_header()
        self._build_settings_panel()
        self._build_drop_zone()
        self._build_table()
        self._build_progress()
        self._build_log()
        self._build_action_bar()

        # Apply theme
        self._apply_theme()

    # =======================================================================
    # HEADER
    # =======================================================================
    def _build_header(self) -> None:
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        # Title
        title = QLabel(APP_TITLE)
        title.setStyleSheet(
            "font-size: 20px; font-weight: 800; letter-spacing: 0.5px; "
            "background: transparent; border: none;"
        )
        header.addWidget(title)

        # Version badge
        ver = QLabel(f"v{APP_VERSION}")
        ver.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #6c5ce7; "
            "background: transparent; border: none; margin-top: 5px;"
        )
        header.addWidget(ver)

        header.addStretch()

        # Theme toggle
        self.btn_theme = QPushButton("🌙")
        self.btn_theme.setObjectName("btn_theme")
        self.btn_theme.setToolTip("Toggle dark/light theme")
        self.btn_theme.clicked.connect(self._toggle_theme)
        header.addWidget(self.btn_theme)

        # Settings gear
        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setObjectName("btn_settings")
        self.btn_settings.setToolTip("Settings")
        self.btn_settings.clicked.connect(self._toggle_settings)
        header.addWidget(self.btn_settings)

        self._main_layout.addLayout(header)

    # =======================================================================
    # SETTINGS PANEL (collapsible)
    # =======================================================================
    def _build_settings_panel(self) -> None:
        self.settings_panel = QFrame()
        self.settings_panel.setObjectName("settings_panel")
        self.settings_panel.setVisible(False)

        layout = QHBoxLayout(self.settings_panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(20)

        # GPU / CPU
        lbl_device = QLabel("Device:")
        lbl_device.setObjectName("section_header")
        layout.addWidget(lbl_device)
        self.combo_device = QComboBox()
        self.combo_device.addItems(["GPU (CUDA)", "CPU"])
        self.combo_device.currentIndexChanged.connect(self._on_device_changed)
        layout.addWidget(self.combo_device)

        # Workers
        lbl_workers = QLabel("Workers:")
        lbl_workers.setObjectName("section_header")
        layout.addWidget(lbl_workers)
        self.spin_workers = QSpinBox()
        self.spin_workers.setRange(1, 8)
        self.spin_workers.setValue(1)
        layout.addWidget(self.spin_workers)

        # Info bubble
        lbl_info = QLabel("ℹ️")
        lbl_info.setCursor(Qt.PointingHandCursor)
        lbl_info.setToolTip(
            "<b>Recommended Presets:</b><br>"
            "• <b>GPU:</b> 1 Worker (Prevents Out-Of-Memory crashes on most GPUs)<br>"
            "• <b>CPU:</b> 2 to 4 Workers (Speeds up processing by utilizing multiple CPU cores)"
        )
        layout.addWidget(lbl_info)

        layout.addStretch()
        self._main_layout.addWidget(self.settings_panel)

    def _on_device_changed(self, index: int) -> None:
        if index == 0:  # GPU selected
            self.spin_workers.setValue(1)
        else:           # CPU selected
            cores = os.cpu_count() or 4
            self.spin_workers.setValue(max(2, min(4, cores // 2)))

    # =======================================================================
    # DROP ZONE
    # =======================================================================
    def _build_drop_zone(self) -> None:
        zone_layout = QHBoxLayout()
        zone_layout.setSpacing(10)

        self.drop_zone = DropZone(self._on_folder_selected)
        zone_layout.addWidget(self.drop_zone, stretch=1)

        self.btn_browse = QPushButton("Browse…")
        self.btn_browse.setMinimumHeight(80)
        self.btn_browse.setMaximumWidth(110)
        self.btn_browse.clicked.connect(self._browse_folder)
        zone_layout.addWidget(self.btn_browse)

        self._main_layout.addLayout(zone_layout)

    # =======================================================================
    # FILE TABLE
    # =======================================================================
    def _build_table(self) -> None:
        # Table header bar
        tbar = QHBoxLayout()
        lbl = QLabel("FILES")
        lbl.setObjectName("section_header")
        tbar.addWidget(lbl)
        tbar.addStretch()

        self.btn_select_all = QPushButton("Select All")
        self.btn_select_all.setFixedHeight(26)
        self.btn_select_all.setStyleSheet("font-size:11px; padding: 2px 12px;")
        self.btn_select_all.clicked.connect(self._select_all)
        tbar.addWidget(self.btn_select_all)

        self.btn_deselect_all = QPushButton("Deselect All")
        self.btn_deselect_all.setFixedHeight(26)
        self.btn_deselect_all.setStyleSheet("font-size:11px; padding: 2px 12px;")
        self.btn_deselect_all.clicked.connect(self._deselect_all)
        tbar.addWidget(self.btn_deselect_all)

        self._main_layout.addLayout(tbar)

        # Table widget
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["", "Original Name", "Extracted Name", "Status"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setMinimumHeight(200)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        hdr.resizeSection(0, 36)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.Fixed)
        hdr.resizeSection(3, 110)

        self._main_layout.addWidget(self.table, stretch=1)

    # =======================================================================
    # PROGRESS
    # =======================================================================
    def _build_progress(self) -> None:
        pbar_layout = QHBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        pbar_layout.addWidget(self.progress_bar, stretch=1)

        self.progress_label = QLabel("Ready")
        self.progress_label.setObjectName("status_label")
        self.progress_label.setMinimumWidth(170)
        self.progress_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        pbar_layout.addWidget(self.progress_label)

        self._main_layout.addLayout(pbar_layout)

    # =======================================================================
    # LOG PANEL
    # =======================================================================
    def _build_log(self) -> None:
        lbl = QLabel("LOG")
        lbl.setObjectName("section_header")
        self._main_layout.addWidget(lbl)

        self.log_panel = QTextEdit()
        self.log_panel.setObjectName("log_panel")
        self.log_panel.setReadOnly(True)
        self.log_panel.setMinimumHeight(120)
        self.log_panel.setMaximumHeight(200)
        self._main_layout.addWidget(self.log_panel)

    # =======================================================================
    # ACTION BAR
    # =======================================================================
    def _build_action_bar(self) -> None:
        bar = QHBoxLayout()
        bar.setSpacing(10)

        self.btn_scan = QPushButton("🔍  Scan Only")
        self.btn_scan.setObjectName("btn_scan")
        self.btn_scan.setToolTip("Extract names without renaming (preview mode)")
        self.btn_scan.clicked.connect(self._start_scan)
        bar.addWidget(self.btn_scan)

        self.btn_start = QPushButton("▶  Start Rename")
        self.btn_start.setObjectName("btn_start")
        self.btn_start.setToolTip("Scan + rename all selected files")
        self.btn_start.clicked.connect(self._start_rename)
        bar.addWidget(self.btn_start)

        self.btn_cancel = QPushButton("✕  Cancel")
        self.btn_cancel.setObjectName("btn_cancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_processing)
        bar.addWidget(self.btn_cancel)

        bar.addStretch()

        self.btn_export = QPushButton("💾  Export Log")
        self.btn_export.clicked.connect(self._export_log)
        bar.addWidget(self.btn_export)

        self.btn_open = QPushButton("📂  Open Folder")
        self.btn_open.clicked.connect(self._open_folder)
        bar.addWidget(self.btn_open)

        self._main_layout.addLayout(bar)

    # ===================================================================
    # THEME
    # ===================================================================
    def _apply_theme(self) -> None:
        self.setStyleSheet(get_stylesheet(self._theme))

    def _toggle_theme(self) -> None:
        self._theme = "light" if self._theme == "dark" else "dark"
        self.btn_theme.setText("☀️" if self._theme == "dark" else "🌙")
        self._apply_theme()

    # ===================================================================
    # SETTINGS
    # ===================================================================
    def _toggle_settings(self) -> None:
        self._settings_visible = not self._settings_visible
        self.settings_panel.setVisible(self._settings_visible)

    # ===================================================================
    # FOLDER SELECTION
    # ===================================================================
    def _browse_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Certificate Folder")
        if path:
            self._on_folder_selected(path)

    def _on_folder_selected(self, path: str) -> None:
        self._folder = path
        self.drop_zone.path_label.setText(path)

        # Find PDFs
        self._pdf_paths = [
            os.path.join(path, f)
            for f in sorted(os.listdir(path))
            if f.lower().endswith(".pdf")
        ]

        self._populate_table()

        if self._pdf_paths:
            self._log(f"[INFO] Found {len(self._pdf_paths)} PDF files in folder")
        else:
            self._log("[WARNING] No PDF files found in the selected folder")

    # ===================================================================
    # TABLE HELPERS
    # ===================================================================
    def _populate_table(self) -> None:
        self.table.setRowCount(0)
        self._scan_results.clear()
        self.progress_bar.setValue(0)
        self.progress_label.setText("Ready")

        for i, path in enumerate(self._pdf_paths):
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Checkbox
            chk = QCheckBox()
            chk.setChecked(True)
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.addWidget(chk)
            chk_layout.setAlignment(Qt.AlignCenter)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 0, chk_widget)

            # Original name
            name_item = QTableWidgetItem(os.path.basename(path))
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 1, name_item)

            # Extracted name placeholder
            ext_item = QTableWidgetItem("—")
            ext_item.setFlags(ext_item.flags() & ~Qt.ItemIsEditable)
            ext_item.setForeground(Qt.gray)
            self.table.setItem(row, 2, ext_item)

            # Status badge
            self.table.setCellWidget(row, 3, StatusWidget("Pending", "pending"))

        self.table.resizeRowsToContents()

    def _get_checked_rows(self) -> list[int]:
        checked: list[int] = []
        for row in range(self.table.rowCount()):
            widget = self.table.cellWidget(row, 0)
            if widget:
                chk = widget.findChild(QCheckBox)
                if chk and chk.isChecked():
                    checked.append(row)
        return checked

    def _select_all(self) -> None:
        for row in range(self.table.rowCount()):
            widget = self.table.cellWidget(row, 0)
            if widget:
                chk = widget.findChild(QCheckBox)
                if chk:
                    chk.setChecked(True)

    def _deselect_all(self) -> None:
        for row in range(self.table.rowCount()):
            widget = self.table.cellWidget(row, 0)
            if widget:
                chk = widget.findChild(QCheckBox)
                if chk:
                    chk.setChecked(False)

    def _update_table_status(self, row: int, status_text: str, status_key: str) -> None:
        if 0 <= row < self.table.rowCount():
            self.table.setCellWidget(row, 3, StatusWidget(status_text, status_key))

    def _update_table_extracted(self, row: int, name: str) -> None:
        if 0 <= row < self.table.rowCount():
            item = self.table.item(row, 2)
            if item:
                item.setText(name if name else "—")
                item.setForeground(Qt.white if name else Qt.gray)

    # ===================================================================
    # LOGGING
    # ===================================================================
    def _log(self, message: str) -> None:
        ts = _timestamp()
        # Colour the tag
        colour = "#8888a8"
        for tag, clr in LOG_COLORS.items():
            if message.startswith(tag):
                colour = clr
                break

        html = (
            f'<span style="color:#555570">{ts}</span>  '
            f'<span style="color:{colour}">{message}</span>'
        )
        self.log_panel.append(html)
        # Auto-scroll
        sb = self.log_panel.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ===================================================================
    # SCAN ONLY
    # ===================================================================
    def _start_scan(self) -> None:
        checked = self._get_checked_rows()
        if not checked:
            self._log("[WARNING] No files selected")
            return

        self._set_processing_state(True)
        self._cancel_event.clear()
        self._scan_results.clear()

        paths = [self._pdf_paths[r] for r in checked]

        # Mark rows as scanning
        for r in checked:
            self._update_table_status(r, "Scanning", "scanning")

        self._worker = ScanWorker(paths, self._cancel_event)
        self._worker.file_scanned.connect(self._on_file_scanned)
        self._worker.progress.connect(self._on_progress)
        self._worker.log_message.connect(self._log)
        self._worker.finished_all.connect(self._on_scan_finished)
        # Map worker indices → actual table rows
        self._worker_row_map = {i: r for i, r in enumerate(checked)}
        self._worker.start()

    def _on_file_scanned(self, idx: int, orig: str, extracted: str, status: str) -> None:
        row = self._worker_row_map.get(idx, idx)
        if extracted:
            self._scan_results[row] = extracted
            self._update_table_extracted(row, extracted)
            self._update_table_status(row, "Scanned", "scanned")
        else:
            self._update_table_status(row, "Fail", "fail")

    def _on_scan_finished(self) -> None:
        self._set_processing_state(False)
        self._log("[INFO] Scan complete")
        scanned = len(self._scan_results)
        self.progress_label.setText(f"Scan complete — {scanned} names extracted")

        # If rename was waiting on scan results, chain into rename now
        if getattr(self, "_rename_after_scan", False):
            self._rename_after_scan = False
            checked = getattr(self, "_rename_checked_rows", [])
            if checked:
                self._do_rename(checked)

    # ===================================================================
    # START RENAME (scan → rename pipeline)
    # ===================================================================
    def _start_rename(self) -> None:
        checked = self._get_checked_rows()
        if not checked:
            self._log("[WARNING] No files selected")
            return

        # If we don't have scan results yet, scan first then rename
        missing = [r for r in checked if r not in self._scan_results]
        if missing:
            # Need to scan first
            self._rename_after_scan = True
            self._rename_checked_rows = checked
            self._start_scan()
            return

        self._do_rename(checked)

    def _do_rename(self, checked_rows: list[int]) -> None:
        self._set_processing_state(True)
        self._cancel_event.clear()

        rename_map: list[tuple[int, str, str]] = []
        for row in checked_rows:
            extracted = self._scan_results.get(row)
            if extracted:
                rename_map.append((row, self._pdf_paths[row], extracted))
                self._update_table_status(row, "Renaming", "renaming")

        if not rename_map:
            self._log("[WARNING] No names to rename (all scans failed?)")
            self._set_processing_state(False)
            return

        self._worker = RenameWorker(rename_map, self._cancel_event)
        self._worker.file_renamed.connect(self._on_file_renamed)
        self._worker.progress.connect(self._on_progress)
        self._worker.log_message.connect(self._log)
        self._worker.finished_all.connect(self._on_rename_finished)
        self._worker.start()

    def _on_file_renamed(self, row: int, orig: str, new_name: str, status: str) -> None:
        label_map = {
            "renamed": "Renamed",
            "skip": "Skipped",
            "warning": "Warning",
            "error": "Error",
        }
        self._update_table_status(row, label_map.get(status, status), status)

    def _on_rename_finished(self) -> None:
        self._set_processing_state(False)
        self._log("[INFO] Rename complete")
        self.progress_label.setText("Rename complete ✓")




    # ===================================================================
    # PROGRESS
    # ===================================================================
    def _on_progress(self, current: int, total: int) -> None:
        pct = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(pct)
        self.progress_label.setText(f"Processing {current} of {total}  ({pct}%)")

    # ===================================================================
    # CANCEL
    # ===================================================================
    def _cancel_processing(self) -> None:
        self._cancel_event.set()
        self._log("[CANCEL] Cancellation requested…")
        self.btn_cancel.setEnabled(False)
        self.progress_label.setText("Cancelling…")

    # ===================================================================
    # UI STATE
    # ===================================================================
    def _set_processing_state(self, processing: bool) -> None:
        self.btn_scan.setEnabled(not processing)
        self.btn_start.setEnabled(not processing)
        self.btn_browse.setEnabled(not processing)
        self.btn_cancel.setEnabled(processing)

    # ===================================================================
    # EXPORT LOG
    # ===================================================================
    def _export_log(self) -> None:
        default_name = f"certificate_rename_log_{datetime.now():%Y%m%d_%H%M%S}.txt"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Log",
            os.path.join(self._folder or os.getcwd(), default_name),
            "Text Files (*.txt);;All Files (*)",
        )
        if path:
            plain = self.log_panel.toPlainText()
            with open(path, "w", encoding="utf-8") as f:
                f.write(plain)
            self._log(f"[INFO] Log exported to {os.path.basename(path)}")

    # ===================================================================
    # OPEN FOLDER
    # ===================================================================
    def _open_folder(self) -> None:
        if self._folder and os.path.isdir(self._folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._folder))
        else:
            self._log("[WARNING] No folder selected")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)

    # Set default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    # Set App Icon
    app.setWindowIcon(QIcon(resource_path("assets/favicon.ico")))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
