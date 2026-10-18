"""
Theme and styling engine for King Video Cutter.
Provides sleek modern Dark and Light stylesheets with Khmer typography support.
"""

from typing import Tuple
from PySide6.QtGui import QFontDatabase, QFont

DARK_PALETTE = {
    "bg_main": "#0f1117",
    "bg_card": "#181b24",
    "bg_card_hover": "#1e222e",
    "bg_input": "#13151c",
    "border": "#282c3c",
    "border_focus": "#f59e0b",
    "text_primary": "#f8fafc",
    "text_secondary": "#94a3b8",
    "text_muted": "#64748b",
    "accent_gold": "#f59e0b",
    "accent_gold_hover": "#fbbf24",
    "accent_blue": "#0284c7",
    "accent_blue_hover": "#38bdf8",
    "success": "#10b981",
    "danger": "#ef4444",
    "danger_hover": "#dc2626",
    "warning": "#f59e0b",
}

LIGHT_PALETTE = {
    "bg_main": "#f8fafc",
    "bg_card": "#ffffff",
    "bg_card_hover": "#f1f5f9",
    "bg_input": "#ffffff",
    "border": "#cbd5e1",
    "border_focus": "#d97706",
    "text_primary": "#0f172a",
    "text_secondary": "#475569",
    "text_muted": "#64748b",
    "accent_gold": "#d97706",
    "accent_gold_hover": "#b45309",
    "accent_blue": "#0284c7",
    "accent_blue_hover": "#0369a1",
    "success": "#059669",
    "danger": "#dc2626",
    "danger_hover": "#b91c1c",
    "warning": "#d97706",
}

def get_font_family() -> str:
    """Returns preferred font family with Noto Sans Khmer priority."""
    families = QFontDatabase.families()
    for fam in ["Noto Sans Khmer", "Khmer OS", "Khmer OS Siemreap", "Segoe UI", "Inter", "Arial"]:
        if fam in families:
            return fam
    return "Segoe UI"

def get_stylesheet(theme: str = "dark") -> str:
    p = DARK_PALETTE if theme == "dark" else LIGHT_PALETTE
    font_fam = get_font_family()

    return f"""
    * {{
        font-family: "{font_fam}", "Noto Sans Khmer", "Segoe UI", sans-serif;
        font-size: 13px;
        color: {p["text_primary"]};
        outline: none;
    }}

    QMainWindow, QDialog {{
        background-color: {p["bg_main"]};
    }}

    QWidget {{
        background-color: transparent;
    }}

    /* Card Panels */
    QFrame[card="true"] {{
        background-color: {p["bg_card"]};
        border: 1px solid {p["border"]};
        border-radius: 12px;
        padding: 12px;
    }}

    QGroupBox {{
        background-color: {p["bg_card"]};
        border: 1px solid {p["border"]};
        border-radius: 10px;
        margin-top: 14px;
        padding-top: 16px;
        padding-left: 10px;
        padding-right: 10px;
        padding-bottom: 10px;
        font-weight: bold;
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 2px 10px;
        color: {p["accent_gold"]};
        font-size: 13px;
    }}

    /* Tabs */
    QTabWidget::pane {{
        border: 1px solid {p["border"]};
        border-radius: 12px;
        background-color: {p["bg_card"]};
        top: -1px;
    }}

    QTabBar::tab {{
        background-color: {p["bg_main"]};
        border: 1px solid {p["border"]};
        border-bottom: none;
        padding: 10px 24px;
        margin-right: 6px;
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
        font-weight: 600;
        font-size: 14px;
        color: {p["text_secondary"]};
        min-height: 28px;
    }}

    QTabBar::tab:selected {{
        background-color: {p["bg_card"]};
        border-color: {p["border"]};
        color: {p["accent_gold"]};
        border-top: 3px solid {p["accent_gold"]};
    }}

    QTabBar::tab:hover:!selected {{
        background-color: {p["bg_card_hover"]};
        color: {p["text_primary"]};
    }}

    /* Buttons */
    QPushButton {{
        background-color: {p["bg_card_hover"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
        padding: 8px 16px;
        font-weight: 600;
        min-height: 22px;
    }}

    QPushButton:hover {{
        background-color: {p["border"]};
        border-color: {p["accent_gold"]};
    }}

    QPushButton:pressed {{
        background-color: {p["bg_input"]};
    }}

    QPushButton:disabled {{
        background-color: {p["bg_input"]};
        color: {p["text_muted"]};
        border-color: {p["border"]};
    }}

    QPushButton[variant="primary"] {{
        background-color: {p["accent_gold"]};
        color: #000000;
        border: none;
        font-size: 14px;
        font-weight: bold;
    }}

    QPushButton[variant="primary"]:hover {{
        background-color: {p["accent_gold_hover"]};
    }}

    QPushButton[variant="danger"] {{
        background-color: {p["danger"]};
        color: #ffffff;
        border: none;
        font-weight: bold;
    }}

    QPushButton[variant="danger"]:hover {{
        background-color: {p["danger_hover"]};
    }}

    /* Inputs & Selects */
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {p["bg_input"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
        padding: 6px 10px;
        min-height: 22px;
        selection-background-color: {p["accent_gold"]};
        selection-color: #000000;
    }}

    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border: 1.5px solid {p["border_focus"]};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {p["bg_card"]};
        border: 1px solid {p["border"]};
        selection-background-color: {p["accent_gold"]};
        selection-color: #000000;
        border-radius: 6px;
        padding: 4px;
    }}

    /* Progress Bar */
    QProgressBar {{
        background-color: {p["bg_input"]};
        border: 1px solid {p["border"]};
        border-radius: 6px;
        text-align: center;
        height: 14px;
        font-weight: bold;
        font-size: 11px;
    }}

    QProgressBar::chunk {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {p["accent_gold"]}, stop:1 #eab308);
        border-radius: 5px;
    }}

    QProgressBar[color="blue"]::chunk {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
        border-radius: 5px;
    }}

    /* Sliders */
    QSlider::groove:horizontal {{
        height: 6px;
        background: {p["bg_input"]};
        border-radius: 3px;
        border: 1px solid {p["border"]};
    }}

    QSlider::sub-page:horizontal {{
        background: {p["accent_gold"]};
        border-radius: 3px;
    }}

    QSlider::handle:horizontal {{
        background: {p["accent_gold_hover"]};
        border: 2px solid #ffffff;
        width: 16px;
        margin-top: -6px;
        margin-bottom: -6px;
        border-radius: 8px;
    }}

    /* Table Widget */
    QTableWidget {{
        background-color: {p["bg_card"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
        gridline-color: {p["border"]};
        selection-background-color: {p["bg_card_hover"]};
        selection-color: {p["accent_gold"]};
    }}

    QHeaderView::section {{
        background-color: {p["bg_main"]};
        border: none;
        border-bottom: 2px solid {p["border"]};
        padding: 8px 6px;
        font-weight: bold;
        color: {p["text_secondary"]};
    }}

    /* Scrollbars */
    QScrollBar:vertical {{
        background: {p["bg_main"]};
        width: 8px;
        border-radius: 4px;
    }}

    QScrollBar::handle:vertical {{
        background: {p["border"]};
        min-height: 20px;
        border-radius: 4px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {p["accent_gold"]};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    /* Tooltips */
    QToolTip {{
        background-color: {p["bg_card"]};
        color: {p["text_primary"]};
        border: 1px solid {p["accent_gold"]};
        border-radius: 6px;
        padding: 4px 8px;
    }}
    """
