"""
gui_styles.py — Centralised Qt Style Sheet (QSS) definitions.

Provides dark and light theme palettes with consistent, modern aesthetics:
rounded corners, subtle borders, gradient progress bars, custom scrollbars,
and colour-coded status badges.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Colour Palettes
# ---------------------------------------------------------------------------

DARK = {
    "bg":              "#0f0f13",
    "surface":         "#1a1a24",
    "surface_hover":   "#24243a",
    "surface_alt":     "#16161e",
    "primary":         "#6c5ce7",
    "primary_hover":   "#7c6ff7",
    "primary_pressed": "#5a4bd6",
    "success":         "#00b894",
    "warning":         "#fdcb6e",
    "error":           "#e17055",
    "info":            "#74b9ff",
    "text":            "#e8e8f0",
    "text_secondary":  "#8888a8",
    "text_dim":        "#555570",
    "border":          "#2a2a3e",
    "border_light":    "#3a3a52",
    "input_bg":        "#14141c",
    "scrollbar_bg":    "#14141c",
    "scrollbar_fg":    "#3a3a52",
    "selection":       "#6c5ce740",
}

LIGHT = {
    "bg":              "#f0f0f5",
    "surface":         "#ffffff",
    "surface_hover":   "#eeeef6",
    "surface_alt":     "#f7f7fc",
    "primary":         "#6c5ce7",
    "primary_hover":   "#5a4bd6",
    "primary_pressed": "#4a3bc6",
    "success":         "#00a884",
    "warning":         "#e6a800",
    "error":           "#d63031",
    "info":            "#0984e3",
    "text":            "#1a1a2e",
    "text_secondary":  "#6c6c8a",
    "text_dim":        "#9999b0",
    "border":          "#d8d8e8",
    "border_light":    "#e8e8f0",
    "input_bg":        "#f5f5fa",
    "scrollbar_bg":    "#e8e8f0",
    "scrollbar_fg":    "#c0c0d0",
    "selection":       "#6c5ce730",
}


# ---------------------------------------------------------------------------
# Status badge colours (used by the GUI for inline HTML & widget styling)
# ---------------------------------------------------------------------------

STATUS_COLORS = {
    "renamed":  "#00b894",
    "scanned":  "#74b9ff",
    "skip":     "#fdcb6e",
    "warning":  "#f39c12",
    "fail":     "#e17055",
    "error":    "#d63031",
    "pending":  "#555570",
    "cancel":   "#8888a8",
    "scanning": "#74b9ff",
    "renaming": "#6c5ce7",
}

LOG_COLORS = {
    "[RENAME]":  "#00b894",
    "[SKIP]":    "#fdcb6e",
    "[FAIL]":    "#e17055",
    "[ERROR]":   "#d63031",
    "[WARNING]": "#f39c12",
    "[SCAN]":    "#74b9ff",
    "[CANCEL]":  "#8888a8",
    "[INFO]":    "#6c5ce7",
}


# ---------------------------------------------------------------------------
# QSS Generator
# ---------------------------------------------------------------------------

def get_stylesheet(theme: str = "dark") -> str:
    """Return the full QSS string for the given *theme* ('dark' or 'light')."""
    c = DARK if theme == "dark" else LIGHT
    return _build_qss(c)


def _build_qss(c: dict[str, str]) -> str:
    """Build the complete QSS using colour dictionary *c*."""
    return f"""
    /* ===== Global ===== */
    QMainWindow {{
        background-color: {c['bg']};
    }}
    QWidget {{
        color: {c['text']};
        font-family: "Segoe UI", "Inter", sans-serif;
        font-size: 13px;
    }}
    QToolTip {{
        background-color: {c['surface']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 4px;
        padding: 4px 8px;
    }}

    /* ===== Scroll Area ===== */
    QScrollArea {{
        background: transparent;
        border: none;
    }}
    QScrollArea > QWidget > QWidget {{
        background: transparent;
    }}

    /* ===== Labels ===== */
    QLabel {{
        background: transparent;
        border: none;
    }}

    /* ===== Buttons ===== */
    QPushButton {{
        background-color: {c['surface']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 8px 20px;
        font-weight: 600;
        font-size: 13px;
        min-height: 18px;
    }}
    QPushButton:hover {{
        background-color: {c['surface_hover']};
        border-color: {c['border_light']};
    }}
    QPushButton:pressed {{
        background-color: {c['primary_pressed']};
    }}
    QPushButton:disabled {{
        background-color: {c['surface_alt']};
        color: {c['text_dim']};
        border-color: {c['border']};
    }}

    /* Primary button */
    QPushButton#btn_start {{
        background-color: {c['primary']};
        color: #ffffff;
        border: none;
    }}
    QPushButton#btn_start:hover {{
        background-color: {c['primary_hover']};
    }}
    QPushButton#btn_start:pressed {{
        background-color: {c['primary_pressed']};
    }}
    QPushButton#btn_start:disabled {{
        background-color: {c['text_dim']};
        color: {c['text_secondary']};
    }}

    /* Scan button */
    QPushButton#btn_scan {{
        background-color: transparent;
        color: {c['primary']};
        border: 1px solid {c['primary']};
    }}
    QPushButton#btn_scan:hover {{
        background-color: {c['selection']};
    }}
    QPushButton#btn_scan:disabled {{
        color: {c['text_dim']};
        border-color: {c['text_dim']};
    }}

    /* Cancel button */
    QPushButton#btn_cancel {{
        background-color: transparent;
        color: {c['error']};
        border: 1px solid {c['error']};
    }}
    QPushButton#btn_cancel:hover {{
        background-color: rgba(225, 112, 85, 0.12);
    }}
    QPushButton#btn_cancel:disabled {{
        color: {c['text_dim']};
        border-color: {c['text_dim']};
    }}

    /* Small icon buttons */
    QPushButton#btn_theme, QPushButton#btn_settings {{
        background: transparent;
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 4px 8px;
        font-size: 16px;
        min-width: 32px;
        max-width: 32px;
        min-height: 32px;
        max-height: 32px;
    }}
    QPushButton#btn_theme:hover, QPushButton#btn_settings:hover {{
        background-color: {c['surface_hover']};
    }}

    /* ===== Drop Zone ===== */
    QFrame#drop_zone {{
        background-color: {c['surface']};
        border: 2px dashed {c['border_light']};
        border-radius: 12px;
        min-height: 80px;
    }}
    QFrame#drop_zone:hover {{
        border-color: {c['primary']};
        background-color: {c['selection']};
    }}

    /* ===== Table ===== */
    QTableWidget {{
        background-color: {c['surface']};
        alternate-background-color: {c['surface_alt']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        gridline-color: {c['border']};
        selection-background-color: {c['selection']};
        outline: none;
    }}
    QTableWidget::item {{
        padding: 6px 10px;
        border: none;
    }}
    QTableWidget::item:selected {{
        background-color: {c['selection']};
        color: {c['text']};
    }}
    QHeaderView {{
        background-color: {c['surface']};
        border: none;
    }}
    QHeaderView::section {{
        background-color: {c['surface']};
        color: {c['text_secondary']};
        font-weight: 700;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        padding: 8px 10px;
        border: none;
        border-bottom: 2px solid {c['border']};
    }}
    QHeaderView::section:hover {{
        color: {c['text']};
    }}

    /* ===== Checkbox ===== */
    QCheckBox {{
        spacing: 6px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 2px solid {c['border_light']};
        border-radius: 4px;
        background: {c['input_bg']};
    }}
    QCheckBox::indicator:checked {{
        background-color: {c['primary']};
        border-color: {c['primary']};
    }}
    QCheckBox::indicator:hover {{
        border-color: {c['primary']};
    }}

    /* ===== Progress Bar ===== */
    QProgressBar {{
        background-color: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        text-align: center;
        color: {c['text_secondary']};
        font-weight: 600;
        font-size: 11px;
        min-height: 14px;
        max-height: 14px;
    }}
    QProgressBar::chunk {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 {c['primary']},
            stop:1 {c['primary_hover']}
        );
        border-radius: 5px;
    }}

    /* ===== Log Panel (QTextEdit) ===== */
    QTextEdit#log_panel {{
        background-color: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 8px;
        font-family: "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
        font-size: 12px;
        color: {c['text_secondary']};
        selection-background-color: {c['selection']};
    }}

    /* ===== Spin Box ===== */
    QSpinBox {{
        background-color: {c['input_bg']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 4px 8px;
        color: {c['text']};
        min-width: 60px;
    }}
    QSpinBox::up-button, QSpinBox::down-button {{
        width: 16px;
        border: none;
        background: transparent;
    }}

    /* ===== Combo Box ===== */
    QComboBox {{
        background-color: {c['input_bg']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 4px 8px;
        color: {c['text']};
        min-width: 80px;
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {c['surface']};
        border: 1px solid {c['border']};
        selection-background-color: {c['selection']};
        color: {c['text']};
    }}

    /* ===== Scrollbars ===== */
    QScrollBar:vertical {{
        background: {c['scrollbar_bg']};
        width: 8px;
        border-radius: 4px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {c['scrollbar_fg']};
        border-radius: 4px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {c['primary']};
    }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        height: 0px;
        background: none;
    }}

    QScrollBar:horizontal {{
        background: {c['scrollbar_bg']};
        height: 8px;
        border-radius: 4px;
        margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background: {c['scrollbar_fg']};
        border-radius: 4px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {c['primary']};
    }}
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal,
    QScrollBar::add-page:horizontal,
    QScrollBar::sub-page:horizontal {{
        width: 0px;
        background: none;
    }}

    /* ===== Settings Panel ===== */
    QFrame#settings_panel {{
        background-color: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 10px;
        padding: 12px;
    }}

    /* ===== Section Headers ===== */
    QLabel#section_header {{
        font-size: 11px;
        font-weight: 700;
        color: {c['text_secondary']};
        text-transform: uppercase;
        letter-spacing: 1px;
        padding-bottom: 4px;
    }}

    /* ===== Status labels ===== */
    QLabel#status_label {{
        font-size: 12px;
        color: {c['text_secondary']};
    }}

    /* ===== Path label ===== */
    QLabel#path_label {{
        font-size: 12px;
        color: {c['text_secondary']};
        font-family: "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
    }}
    """
