"""Qt theme: design tokens + stylesheet (dark / light).

A single tokenised stylesheet source — the whole UI switches theme by
re-applying it.  Colors roughly follow a Material-like palette; text
contrast is kept ≥ 4.5:1 in both themes.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

THEMES = ("dark", "light")


@dataclass(frozen=True)
class Tokens:
    name: str
    bg: str
    surface: str
    surface_alt: str
    border: str
    text: str
    text_muted: str
    primary: str
    primary_text: str
    danger: str
    warning: str
    success: str
    focus: str


DARK = Tokens(
    name="dark",
    bg="#16181d",
    surface="#1f232b",
    surface_alt="#272c36",
    border="#343a46",
    text="#e8eaed",
    text_muted="#9aa3af",
    primary="#4f8cff",
    primary_text="#0b1220",
    danger="#e5534b",
    warning="#e69500",
    success="#2ea043",
    focus="#6ea8ff",
)

LIGHT = Tokens(
    name="light",
    bg="#f3f4f6",
    surface="#ffffff",
    surface_alt="#e9ebef",
    border="#d3d8de",
    text="#1c2026",
    text_muted="#5c6470",
    primary="#1a73e8",
    primary_text="#ffffff",
    danger="#d1242f",
    warning="#b25e00",
    success="#1a7f37",
    focus="#1a73e8",
)

TOKENS = {"dark": DARK, "light": LIGHT}


def _palette(t: Tokens) -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(t.bg))
    palette.setColor(QPalette.WindowText, QColor(t.text))
    palette.setColor(QPalette.Base, QColor(t.surface))
    palette.setColor(QPalette.AlternateBase, QColor(t.surface_alt))
    palette.setColor(QPalette.ToolTipBase, QColor(t.surface_alt))
    palette.setColor(QPalette.ToolTipText, QColor(t.text))
    palette.setColor(QPalette.Text, QColor(t.text))
    palette.setColor(QPalette.Button, QColor(t.surface_alt))
    palette.setColor(QPalette.ButtonText, QColor(t.text))
    palette.setColor(QPalette.Highlight, QColor(t.primary))
    palette.setColor(QPalette.HighlightedText, QColor(t.primary_text))
    palette.setColor(QPalette.Link, QColor(t.primary))
    palette.setColor(QPalette.PlaceholderText, QColor(t.text_muted))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(t.text_muted))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(t.text_muted))
    return palette


def stylesheet(t: Tokens, font_family: str) -> str:
    return f"""
    * {{
        font-family: "{font_family}";
        font-size: 13px;
        color: {t.text};
    }}
    QMainWindow, QDialog {{
        background: {t.bg};
    }}
    QWidget {{
        background: transparent;
    }}
    QScrollArea {{
        border: none;
    }}
    QFrame#card {{
        background: {t.surface};
        border: 1px solid {t.border};
        border-radius: 12px;
    }}
    QFrame#card[highlight="true"] {{
        border: 2px solid {t.primary};
    }}
    QLabel#panelTitle {{
        font-size: 15px;
        font-weight: 600;
    }}
    QLabel#muted {{
        color: {t.text_muted};
    }}
    QLabel#badge {{
        color: {t.text};
        background: {t.surface_alt};
        border-radius: 9px;
        padding: 2px 8px;
    }}
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {{
        background: {t.bg};
        border: 1px solid {t.border};
        border-radius: 8px;
        padding: 5px 8px;
        selection-background-color: {t.primary};
        selection-color: {t.primary_text};
    }}
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
        border: 1px solid {t.focus};
    }}
    QLineEdit[readOnly="true"] {{
        background: {t.surface_alt};
        color: {t.text_muted};
    }}
    QLineEdit#invalid {{
        border: 1px solid {t.danger};
    }}
    QComboBox QAbstractItemView {{
        background: {t.surface};
        border: 1px solid {t.border};
        selection-background-color: {t.primary};
        selection-color: {t.primary_text};
    }}
    QPushButton {{
        background: {t.surface_alt};
        border: 1px solid {t.border};
        border-radius: 8px;
        padding: 6px 14px;
        min-height: 18px;
    }}
    QPushButton:hover {{ background: {t.border}; }}
    QPushButton:pressed {{ background: {t.bg}; }}
    QPushButton:disabled {{ color: {t.text_muted}; }}
    QPushButton#dominant {{
        background: {t.primary};
        color: {t.primary_text};
        border: none;
        font-weight: 600;
        padding: 8px 22px;
        min-height: 20px;
    }}
    QPushButton#dominant:hover {{ background: {t.focus}; }}
    QPushButton#danger {{
        background: transparent;
        color: {t.danger};
        border: 1px solid {t.danger};
    }}
    QPushButton#danger:hover {{ background: {t.danger}; color: {t.primary_text}; }}
    QPushButton#ghost {{
        background: transparent;
        border: none;
        color: {t.text_muted};
    }}
    QPushButton#ghost:hover {{ color: {t.text}; }}
    QCheckBox, QRadioButton {{ spacing: 6px; }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 16px; height: 16px;
    }}
    QToolButton {{
        background: transparent;
        border: none;
        border-radius: 8px;
        padding: 5px;
        color: {t.text_muted};
    }}
    QToolButton:hover {{ background: {t.surface_alt}; color: {t.text}; }}
    QGroupBox {{
        border: 1px solid {t.border};
        border-radius: 8px;
        margin-top: 12px;
        padding-top: 6px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 4px;
        color: {t.text_muted};
    }}
    QListWidget, QListView {{
        background: {t.surface};
        border: 1px solid {t.border};
        border-radius: 8px;
    }}
    QListWidget::item {{ padding: 8px; border-radius: 6px; }}
    QListWidget::item:selected {{ background: {t.primary}; color: {t.primary_text}; }}
    QListWidget::item:hover {{ background: {t.surface_alt}; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
    QScrollBar::handle:vertical {{
        background: {t.border}; border-radius: 5px; min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {t.text_muted}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; }}
    QScrollBar::handle:horizontal {{
        background: {t.border}; border-radius: 5px; min-width: 24px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QToolTip {{
        background: {t.surface_alt};
        color: {t.text};
        border: 1px solid {t.border};
        padding: 4px 6px;
    }}
    QStatusBar {{ background: {t.bg}; color: {t.text_muted}; }}
    QProgressBar {{
        background: {t.surface_alt};
        border: none;
        border-radius: 6px;
        height: 10px;
        text-align: center;
        color: {t.primary_text};
    }}
    QProgressBar::chunk {{ background: {t.primary}; border-radius: 6px; }}
    QLabel#snack {{
        background: {t.surface_alt};
        color: {t.text};
        border: 1px solid {t.border};
        border-radius: 10px;
        padding: 8px 16px;
    }}
    QLabel#dropZone {{
        color: {t.text_muted};
        border: 2px dashed {t.border};
        border-radius: 12px;
        background: {t.surface};
        padding: 26px;
    }}
    QLabel#dropZone[active="true"] {{
        color: {t.primary};
        border: 2px dashed {t.primary};
        background: {t.surface_alt};
    }}
    """


#: UI font preference — the first family actually installed wins, so Qt
#: never warns about missing fonts ("OpenType support missing for ...").
_UI_FONTS = (
    "Segoe UI",
    "SF Pro Text",
    "Cantarell",
    "Ubuntu",
    "Inter",
    "Noto Sans",
    "DejaVu Sans",
    "Liberation Sans",
)


def choose_font_family(app: QApplication) -> str:
    """Pick a real, installed UI font (falling back to the app default)."""
    try:
        available = set(QFontDatabase(app).families())
    except Exception:  # pragma: no cover - extremely defensive
        available = set()
    for family in _UI_FONTS:
        if family in available:
            return family
    return app.font().family()


def apply_theme(app: QApplication, theme: str) -> None:
    name = theme if theme in TOKENS else DARK.name
    tokens = TOKENS[name]
    app.setPalette(_palette(tokens))
    app.setStyleSheet(stylesheet(tokens, choose_font_family(app)))
