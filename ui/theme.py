import os
import sys
from pathlib import Path

DARK_TOKENS = {
    "bg":            "#0d1117",
    "surface":       "#161b22",
    "surface_alt":   "#21262d",
    "border":        "#30363d",
    "fg":            "#c9d1d9",
    "fg_bright":     "#f0f6fc",
    "fg_dim":        "#8b949e",
    "success":       "#238636",
    "success_hover": "#2ea043",
    "accent":        "#58a6ff",
    "warning":       "#d29922",
    "danger":        "#f85149",
}

LIGHT_TOKENS = {
    "bg":            "#f6f8fa",
    "surface":       "#ffffff",
    "surface_alt":   "#f0f3f6",
    "border":        "#d0d7de",
    "fg":            "#1f2328",
    "fg_bright":     "#0d1117",
    "fg_dim":        "#656d76",
    "success":       "#1f883d",
    "success_hover": "#1a7f37",
    "accent":        "#0969da",
    "warning":       "#9a6700",
    "danger":        "#cf222e",
}


_QSS_TEMPLATE = """
QWidget {{ background: {bg}; color: {fg}; font-family: "Inter", "Segoe UI", sans-serif; font-size: 10pt; }}
QMainWindow, QDialog {{ background: {bg}; }}

QTabWidget::pane {{ border: 1px solid {border}; background: {surface}; top: -1px; }}
QTabBar::tab {{
    background: {bg}; color: {fg_dim}; padding: 8px 16px;
    border: 1px solid transparent; border-bottom: none;
}}
QTabBar::tab:selected {{ background: {surface}; color: {fg_bright}; border-color: {border}; }}
QTabBar::tab:hover:!selected {{ color: {fg}; }}

QGroupBox {{
    background: {surface}; border: 1px solid {border}; border-radius: 6px;
    margin-top: 14px; padding: 14px;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {fg_bright}; font-weight: 600; }}

QPushButton {{
    background: {surface_alt}; color: {fg}; border: 1px solid {border};
    padding: 6px 14px; border-radius: 6px;
}}
QPushButton:hover {{ background: {border}; }}
QPushButton:disabled {{ color: {fg_dim}; }}
QPushButton#primary {{ background: {success}; color: white; border: none; font-weight: 600; padding: 8px 18px; }}
QPushButton#primary:hover {{ background: {success_hover}; }}
QPushButton#primary:disabled {{ background: {surface_alt}; color: {fg_dim}; }}
QPushButton#warning {{ background: {warning}; color: white; border: none; font-weight: 600; }}

QLineEdit, QPlainTextEdit, QTextEdit {{
    background: {surface}; color: {fg_bright}; border: 1px solid {border}; border-radius: 4px; padding: 6px;
    selection-background-color: {accent};
}}
QLineEdit:focus, QPlainTextEdit:focus {{ border-color: {accent}; }}
QPlainTextEdit#log {{ font-family: "JetBrains Mono", "Consolas", monospace; font-size: 9pt; }}

QTableView {{ background: {surface}; gridline-color: {border}; border: 1px solid {border}; }}
QHeaderView::section {{ background: {surface_alt}; color: {fg_bright}; padding: 6px; border: none; border-right: 1px solid {border}; }}

QStatusBar {{ background: {surface_alt}; color: {fg_dim}; }}

QProgressBar {{ background: {surface_alt}; border: 1px solid {border}; border-radius: 4px; text-align: center; color: {fg_bright}; }}
QProgressBar::chunk {{ background: {accent}; border-radius: 3px; }}
"""


def qss_for(mode: str) -> str:
    tokens = LIGHT_TOKENS if mode == "light" else DARK_TOKENS
    return _QSS_TEMPLATE.format(**tokens)


def apply_theme(app, mode: str) -> None:
    app.setStyleSheet(qss_for(mode))


def _assets_dir() -> Path:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    if not getattr(sys, "_MEIPASS", None):
        base = os.path.dirname(base)
    return Path(base) / "assets"


def load_fonts() -> tuple[str, str]:
    """Registra Inter + JetBrains Mono via QFontDatabase. Retorna (sans, mono)."""
    from PySide6.QtGui import QFontDatabase
    sans, mono = "Segoe UI", "Consolas"
    font_dir = _assets_dir() / "fonts"
    if not font_dir.is_dir():
        return sans, mono
    families_found = {"sans": None, "mono": None}
    for fname in ("Inter-Regular.ttf", "Inter-Medium.ttf",
                  "Inter-SemiBold.ttf", "Inter-Bold.ttf",
                  "JetBrainsMono-Regular.ttf", "JetBrainsMono-Medium.ttf"):
        path = font_dir / fname
        if not path.is_file():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        fams = QFontDatabase.applicationFontFamilies(font_id)
        if not fams:
            continue
        fam = fams[0]
        if "Inter" in fam and families_found["sans"] is None:
            families_found["sans"] = fam
        if "JetBrains" in fam and families_found["mono"] is None:
            families_found["mono"] = fam
    if families_found["sans"]:
        sans = families_found["sans"]
    if families_found["mono"]:
        mono = families_found["mono"]
    return sans, mono
