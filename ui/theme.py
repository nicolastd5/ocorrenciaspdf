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
    "accent_overlay": "rgba(88,166,255,0.08)",
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
    "accent_overlay": "rgba(9,105,218,0.08)",
}


_QSS_TEMPLATE = """
QWidget {{ background: {bg}; color: {fg}; font-family: "Inter", "Segoe UI", sans-serif; font-size: 10pt; }}
QMainWindow, QDialog {{ background: {bg}; }}

/* ---------- Scrollbars (finas, sem setas) ---------- */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px 2px 2px 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0 2px 2px 2px; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 4px; min-height: 32px; }}
QScrollBar::handle:horizontal {{ background: {border}; border-radius: 4px; min-width: 32px; }}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{ background: {fg_dim}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; background: transparent; border: none; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---------- Tooltip ---------- */
QToolTip {{ background: {surface_alt}; color: {fg_bright}; border: 1px solid {border};
    padding: 5px 8px; font-size: 9pt; }}

/* ---------- Tabs (mantido para diálogos/compat) ---------- */
QTabWidget::pane {{ border: 1px solid {border}; background: {surface}; top: -1px; }}
QTabBar::tab {{
    background: {bg}; color: {fg_dim}; padding: 8px 16px;
    border: 1px solid transparent; border-bottom: none;
}}
QTabBar::tab:selected {{ background: {surface}; color: {fg_bright}; border-color: {border}; }}
QTabBar::tab:hover:!selected {{ color: {fg}; }}

/* ---------- Sidebar ---------- */
QFrame#sidebar {{
    background: {surface}; border: none; border-right: 1px solid {border};
}}
QLabel#sideSect {{
    color: {fg_dim}; font-size: 8pt; font-weight: 600; padding: 10px 9px 4px;
    background: transparent;
}}

/* ---------- Card de licença na sidebar ---------- */
QFrame#licard {{ background: {bg}; border: 1px solid {border}; border-radius: 10px; }}
QFrame#licard QLabel {{ background: transparent; }}
QLabel#licardKey {{ color: {fg_dim}; }}
QLabel#licardVal {{ color: {fg}; font-family: "JetBrains Mono", "Consolas", monospace; font-size: 9pt; }}

/* ---------- Cabeçalho de página ---------- */
QLabel#pageTitle {{ color: {fg_bright}; font-size: 16pt; font-weight: 600; background: transparent; }}
QLabel#pageSub {{ color: {fg_dim}; font-size: 9.5pt; background: transparent; }}

/* ---------- Texto de apoio (dicas/ajuda) ---------- */
QLabel#helpText {{ color: {fg_dim}; font-size: 9pt; background: transparent; }}

/* ---------- DropZone ---------- */
QFrame#dropzone {{ border: 1.5px dashed {border}; border-radius: 10px; background: {bg}; }}
QFrame#dropzone:hover {{ border-color: {fg_dim}; }}
QFrame#dropzone[dragActive="true"] {{ border: 1.5px solid {accent}; background: {accent_overlay}; }}
QLabel#dropIcon {{ color: {fg_dim}; font-size: 20pt; background: transparent; border: none; }}
QLabel#dropLabel {{ background: transparent; border: none; }}
QLabel#dropHint {{ color: {fg_dim}; font-size: 8pt; background: transparent; border: none;
    font-family: "JetBrains Mono", "Consolas", monospace; }}
QLabel#chipName {{ color: {fg_bright}; font-weight: 500; background: transparent; border: none; }}
QLabel#chipMeta {{ color: {fg_dim}; font-size: 8pt; background: transparent; border: none;
    font-family: "JetBrains Mono", "Consolas", monospace; }}
QLabel#chipIcon {{ color: {ok_text}; background: rgba(46,160,67,0.12); border-radius: 9px;
    font-size: 14pt; border: none; }}

/* ---------- Prompt do painel de execução ---------- */
QLabel#promptIcon {{ color: {fg_dim}; font-size: 22pt; background: transparent; }}
QLabel#promptIcon[state="ready"] {{ color: {ok_text}; }}
QLabel#promptTitle {{ color: {fg_bright}; font-weight: 500; background: transparent; }}
QLabel#promptSub {{ color: {fg_dim}; font-size: 9pt; background: transparent; }}

/* ---------- Banner de atualização ---------- */
QWidget#updateBanner {{ background: {banner_bg}; }}
QLabel#updateBannerLbl {{ color: {banner_fg}; font-weight: 600; background: transparent; }}

/* ---------- Cards (QGroupBox numerado) ---------- */
QGroupBox {{
    background: {surface}; border: 1px solid {border}; border-radius: 9px;
    margin-top: 14px; padding: 16px;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {fg_bright}; font-weight: 600; }}

/* SectionCard com cabeçalho próprio (sem título nativo do QGroupBox) */
QFrame#card {{ background: {surface}; border: 1px solid {border}; border-radius: 10px; }}
QFrame#cardHead {{ background: {surface_alt}; border: none; border-top-left-radius: 10px; border-top-right-radius: 10px;
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
    padding: 7px 15px; border-radius: 7px;
}}
QPushButton:hover {{ background: {border}; }}
QPushButton:pressed {{ background: {border}; border-color: {fg_dim}; }}
QPushButton:focus {{ border-color: {accent}; outline: none; }}
QPushButton:disabled {{ color: {fg_dim}; }}
QPushButton#primary {{ background: {success}; color: white; border: none; font-weight: 600; padding: 8px 20px; }}
QPushButton#primary:hover {{ background: {success_hover}; }}
QPushButton#primary:disabled {{ background: {surface_alt}; color: {fg_dim}; }}
QPushButton#warning {{ background: {warning}; color: white; border: none; font-weight: 600; padding: 8px 20px; }}
QPushButton#warning:hover {{ background: {warning}; }}
QPushButton#ghost {{ background: transparent; border: 1px solid transparent; }}
QPushButton#ghost:hover {{ background: {surface_alt}; }}

/* ---------- Inputs ---------- */
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox {{
    background: {surface}; color: {fg_bright}; border: 1px solid {border}; border-radius: 6px;
    padding: 7px 9px;
    selection-background-color: {accent};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{ border-color: {accent}; }}
QLineEdit:hover, QComboBox:hover {{ border-color: {fg_dim}; }}
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
    border: 1px solid {border}; border-radius: 8px; }}
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
QFrame#kpi {{ background: {surface}; border: 1px solid {border}; border-radius: 10px; }}
QFrame#kpi QLabel {{ background: transparent; }}
QLabel#kpiLabel {{ color: {fg_dim}; font-size: 8.5pt; }}
QLabel#kpiNum {{ color: {fg_bright}; font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 17pt; font-weight: 700; }}
QLabel#kpiNum[accent="ok"] {{ color: {ok_text}; }}
QLabel#kpiNum[accent="warn"] {{ color: {warn_text}; }}
QLabel#kpiNum[accent="accent"] {{ color: {accent}; }}
QLabel#kpiSub {{ color: {fg_dim}; font-size: 8pt; }}

/* ---------- Sidebar: itens de navegação ---------- */
QPushButton#navItem {{ background: transparent; border: 1px solid transparent;
    text-align: left; border-radius: 7px; }}
QPushButton#navItem:hover {{ background: {surface_alt}; }}
QPushButton#navItem:checked {{ background: {surface_alt}; }}
QPushButton#navItem:focus {{ border: 1px solid {accent}; outline: none; }}
QLabel#navLabel {{ background: transparent; font-size: 9.5pt; }}
QLabel#navGlyph {{ background: transparent; color: {fg_dim}; font-size: 11pt; }}
QPushButton#navItem:checked QLabel#navLabel {{ font-weight: 600; color: {fg_bright}; }}
QPushButton#navItem:checked QLabel#navGlyph {{ color: {accent}; }}
QLabel#navCount {{ background: {surface_alt}; border-radius: 8px; padding: 0 7px;
    font-family: "JetBrains Mono", monospace; font-size: 8pt; color: {fg_dim}; }}

/* ---------- Painel (coluna direita) ---------- */
QFrame#panel {{ background: {surface}; border: 1px solid {border}; border-radius: 10px; }}
QFrame#panelHead {{ background: {surface_alt}; border: none; border-bottom: 1px solid {border};
    border-top-left-radius: 10px; border-top-right-radius: 10px; }}
QLabel#panelTitle {{ color: {fg_bright}; font-weight: 600; background: transparent; }}

/* ---------- Segmented toggle (tema) ---------- */
QFrame#seg {{ background: {bg}; border: 1px solid {border}; border-radius: 8px; }}
QPushButton#segBtn {{ background: transparent; color: {fg_dim}; border: none;
    border-radius: 6px; padding: 6px 16px; font-weight: 500; }}
QPushButton#segBtn:checked {{ background: {surface_alt}; color: {fg_bright}; }}
QPushButton#segBtn:hover:!checked {{ color: {fg}; }}
"""


_current_mode = "dark"


def qss_for(mode: str) -> str:
    tokens = LIGHT_TOKENS if mode == "light" else DARK_TOKENS
    return _QSS_TEMPLATE.format(**tokens)


def tokens_for(mode: str) -> dict:
    """Tokens crus do tema atual — para estilos pontuais (cores de log, badges)."""
    return dict(LIGHT_TOKENS if mode == "light" else DARK_TOKENS)


def current_mode() -> str:
    return _current_mode


def token(name: str) -> str:
    """Token do tema ativo — para cores aplicadas em código (ex.: QColor em models)."""
    tokens = LIGHT_TOKENS if _current_mode == "light" else DARK_TOKENS
    return tokens[name]


def apply_theme(app, mode: str) -> None:
    global _current_mode
    _current_mode = "light" if mode == "light" else "dark"
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
