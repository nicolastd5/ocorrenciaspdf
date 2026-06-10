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
    # tons derivados usados no shell (sidebar, log, banner)
    "log_bg":        "#06080c",
    "banner_bg":     "#0f1a14",
    "banner_fg":     "#2ea043",
    "ok_text":       "#3fb950",
    "warn_text":     "#e3b341",
    "err_text":      "#ff7b72",
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
    "log_bg":        "#0d1117",
    "banner_bg":     "#dafbe1",
    "banner_fg":     "#1a7f37",
    "ok_text":       "#1a7f37",
    "warn_text":     "#9a6700",
    "err_text":      "#cf222e",
}


_QSS_TEMPLATE = """
QWidget {{ background: {bg}; color: {fg}; font-family: "Inter", "Segoe UI", sans-serif; font-size: 10pt; }}
QMainWindow, QDialog {{ background: {bg}; }}

/* ---------- Tabs (mantido para diálogos/compat) ---------- */
QTabWidget::pane {{ border: 1px solid {border}; background: {surface}; top: -1px; }}
QTabBar::tab {{
    background: {bg}; color: {fg_dim}; padding: 8px 16px;
    border: 1px solid transparent; border-bottom: none;
}}
QTabBar::tab:selected {{ background: {surface}; color: {fg_bright}; border-color: {border}; }}
QTabBar::tab:hover:!selected {{ color: {fg}; }}

/* ---------- Sidebar (QListWidget de navegação) ---------- */
QListWidget#sidebar {{
    background: {surface}; border: none; border-right: 1px solid {border};
    outline: 0; padding: 8px 8px;
}}
QListWidget#sidebar::item {{
    color: {fg}; padding: 8px 10px; border-radius: 7px; margin: 2px 0;
}}
QListWidget#sidebar::item:hover {{ background: {surface_alt}; }}
QListWidget#sidebar::item:selected {{
    background: {surface_alt}; color: {fg_bright};
    border-left: 3px solid {accent};
}}
QLabel#sideSect {{
    color: {fg_dim}; font-size: 8pt; font-weight: 600; padding: 10px 9px 4px;
}}

/* ---------- Card de licença na sidebar ---------- */
QFrame#licard {{ background: {bg}; border: 1px solid {border}; border-radius: 8px; }}
QFrame#licard QLabel {{ background: transparent; }}
QLabel#licardKey {{ color: {fg_dim}; }}
QLabel#licardVal {{ color: {fg}; font-family: "JetBrains Mono", "Consolas", monospace; font-size: 9pt; }}

/* ---------- Cabeçalho de página ---------- */
QLabel#pageTitle {{ color: {fg_bright}; font-size: 13pt; font-weight: 600; }}
QLabel#pageSub {{ color: {fg_dim}; font-size: 9pt; }}

/* ---------- Cards (QGroupBox numerado) ---------- */
QGroupBox {{
    background: {surface}; border: 1px solid {border}; border-radius: 6px;
    margin-top: 14px; padding: 14px;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {fg_bright}; font-weight: 600; }}

/* SectionCard com cabeçalho próprio (sem título nativo do QGroupBox) */
QFrame#card {{ background: {surface}; border: 1px solid {border}; border-radius: 8px; }}
QFrame#cardHead {{ background: {surface_alt}; border: none; border-top-left-radius: 8px; border-top-right-radius: 8px;
    border-bottom: 1px solid {border}; }}
QFrame#cardBody {{ background: transparent; border: none; }}
QLabel#cardTitle {{ color: {fg_bright}; font-weight: 600; background: transparent; }}
QLabel#step {{
    background: {bg}; border: 1px solid {border}; border-radius: 11px;
    color: {fg_bright}; font-weight: 600; min-width: 22px; max-width: 22px;
    min-height: 22px; max-height: 22px;
}}
QLabel#stepDone {{
    background: {success}; border: 1px solid {success}; border-radius: 11px;
    color: white; font-weight: 600; min-width: 22px; max-width: 22px;
    min-height: 22px; max-height: 22px;
}}
QLabel#cardOpt {{ color: {fg_dim}; font-size: 8pt; background: {bg}; border: 1px solid {border};
    border-radius: 9px; padding: 1px 8px; }}

/* ---------- Botões ---------- */
QPushButton {{
    background: {surface_alt}; color: {fg}; border: 1px solid {border};
    padding: 6px 14px; border-radius: 6px;
}}
QPushButton:hover {{ background: {border}; }}
QPushButton:disabled {{ color: {fg_dim}; }}
QPushButton#primary {{ background: {success}; color: white; border: none; font-weight: 600; padding: 8px 18px; }}
QPushButton#primary:hover {{ background: {success_hover}; }}
QPushButton#primary:disabled {{ background: {surface_alt}; color: {fg_dim}; }}
QPushButton#warning {{ background: {warning}; color: white; border: none; font-weight: 600; padding: 8px 18px; }}
QPushButton#warning:hover {{ background: {warning}; }}
QPushButton#ghost {{ background: transparent; border: 1px solid transparent; }}
QPushButton#ghost:hover {{ background: {surface_alt}; }}

/* ---------- Inputs ---------- */
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox {{
    background: {surface}; color: {fg_bright}; border: 1px solid {border}; border-radius: 4px; padding: 6px;
    selection-background-color: {accent};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{ border-color: {accent}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{ background: {surface}; color: {fg}; border: 1px solid {border};
    selection-background-color: {surface_alt}; selection-color: {fg_bright}; }}
QPlainTextEdit#log {{ font-family: "JetBrains Mono", "Consolas", monospace; font-size: 9pt;
    background: {log_bg}; border: 1px solid {border}; }}

/* ---------- Radio / Checkbox ---------- */
QRadioButton, QCheckBox {{ color: {fg}; spacing: 8px; padding: 4px 2px; }}
QRadioButton::indicator {{ width: 15px; height: 15px; border-radius: 8px;
    border: 1.5px solid {fg_dim}; background: transparent; }}
QRadioButton::indicator:checked {{ border-color: {accent};
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fp:0.5, fy:0.5,
        stop:0 {accent}, stop:0.45 {accent}, stop:0.5 transparent); }}
QCheckBox::indicator {{ width: 15px; height: 15px; border-radius: 4px;
    border: 1.5px solid {fg_dim}; background: transparent; }}
QCheckBox::indicator:checked {{ border-color: {accent}; background: {accent}; }}

/* ---------- Tabelas ---------- */
QTableView, QTableWidget {{ background: {surface}; gridline-color: {border};
    border: 1px solid {border}; border-radius: 6px; }}
QTableView::item:selected, QTableWidget::item:selected {{ background: {surface_alt}; color: {fg_bright}; }}
QHeaderView::section {{ background: {surface_alt}; color: {fg_dim}; padding: 7px 10px;
    border: none; border-right: 1px solid {border}; border-bottom: 1px solid {border};
    font-weight: 600; }}

/* ---------- Status bar ---------- */
QStatusBar {{ background: {surface_alt}; color: {fg_dim}; border-top: 1px solid {border}; }}
QStatusBar::item {{ border: none; }}
QStatusBar QLabel {{ background: transparent; }}

/* ---------- Progress ---------- */
QProgressBar {{ background: {surface_alt}; border: 1px solid {border}; border-radius: 4px;
    text-align: center; color: {fg_bright}; max-height: 8px; }}
QProgressBar::chunk {{ background: {accent}; border-radius: 3px; }}

/* ---------- KPI tiles ---------- */
QFrame#kpi {{ background: {surface}; border: 1px solid {border}; border-radius: 8px; }}
QFrame#kpi QLabel {{ background: transparent; }}
QLabel#kpiLabel {{ color: {fg_dim}; font-size: 8.5pt; }}
QLabel#kpiNum {{ color: {fg_bright}; font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 17pt; font-weight: 700; }}
QLabel#kpiSub {{ color: {fg_dim}; font-size: 8pt; }}

/* ---------- Painel (coluna direita) ---------- */
QFrame#panel {{ background: {surface}; border: 1px solid {border}; border-radius: 8px; }}
QFrame#panelHead {{ background: {surface_alt}; border: none; border-bottom: 1px solid {border};
    border-top-left-radius: 8px; border-top-right-radius: 8px; }}
QLabel#panelTitle {{ color: {fg_bright}; font-weight: 600; background: transparent; }}

/* ---------- Segmented toggle (tema) ---------- */
QFrame#seg {{ background: {bg}; border: 1px solid {border}; border-radius: 8px; }}
QPushButton#segBtn {{ background: transparent; color: {fg_dim}; border: none;
    border-radius: 6px; padding: 6px 16px; font-weight: 500; }}
QPushButton#segBtn:checked {{ background: {surface_alt}; color: {fg_bright}; }}
QPushButton#segBtn:hover:!checked {{ color: {fg}; }}
"""


def qss_for(mode: str) -> str:
    tokens = LIGHT_TOKENS if mode == "light" else DARK_TOKENS
    return _QSS_TEMPLATE.format(**tokens)


def tokens_for(mode: str) -> dict:
    """Tokens crus do tema atual — para estilos pontuais (cores de log, badges)."""
    return dict(LIGHT_TOKENS if mode == "light" else DARK_TOKENS)


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
