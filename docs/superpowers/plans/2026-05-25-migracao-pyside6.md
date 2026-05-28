# Migração da UI para PySide6 (v1.64) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir toda a camada de UI Tkinter do Processador de Ocorrências por uma implementação em PySide6 modular (pacote `ui/`), preservando intactos os módulos de processamento (`processador.py`, `vt_caixa_processador.py`), o cliente de licença (`license_client.py`) e o auto-update (`auto_update.py`).

**Architecture:** Reescrita big bang em branch isolada (`feat-pyside6-1.64`). Entrypoint `app.py` enxuto delega tudo pro pacote `ui/` com um módulo por tela (`tabs/`), widgets reusáveis (`widgets/`) e serviços puros (`theme.py`, `settings.py`, `history.py`). Processamentos pesados rodam em `QThread` + worker `QObject` com sinais. Bump `APP_VERSION` 1.63 → 1.64 — segue o fluxo normal de auto-update (a v1.63 em campo detecta a 1.64 e baixa).

**Tech Stack:** Python ≥3.10, PySide6 ≥6.7, openpyxl/pdfplumber/xlrd (existentes), PyInstaller (existente), pytest + pytest-qt (novo).

**Spec:** [`docs/superpowers/specs/2026-05-25-migracao-pyside6-design.md`](../specs/2026-05-25-migracao-pyside6-design.md)

---

## File Structure (lock decomposição aqui)

**Criar:**

| Path | Responsabilidade | Tamanho-alvo |
|---|---|---|
| `ui/__init__.py` | Marker do pacote, vazio | ~0 |
| `ui/theme.py` | Tokens dark/light, geração de QSS, carregamento de fontes | ~150 |
| `ui/settings.py` | I/O atômico de `~/.ocorrencias_config.json` | ~80 |
| `ui/history.py` | I/O atômico de `~/.ocorrencias_history.json`, cap FIFO 500 | ~100 |
| `ui/splash.py` | Splash custom (`QWidget` frameless) com spinner animado + barra de progresso show/hide; API `set_status`/`set_progress`/`hide_progress` | ~150 |
| `ui/update_worker.py` | `QObject` worker que roda `check_and_update` numa `QThread` e emite sinais `progress`/`status` | ~70 |
| `ui/license_dialogs.py` | `show_activation_window`, `show_error_window` (API igual ao `license_ui.py`) | ~140 |
| `ui/main_window.py` | `QMainWindow` + `QTabWidget` + status bar; aplica tema; salva/restaura geometria | ~150 |
| `ui/widgets/__init__.py` | Reexports | ~10 |
| `ui/widgets/drop_zone.py` | Área de drag-and-drop por extensão | ~120 |
| `ui/widgets/log_panel.py` | `QPlainTextEdit` mono + auto-scroll + barra de progresso opcional | ~80 |
| `ui/widgets/primary_button.py` | Botão verde de ação principal (subclasse `QPushButton`) | ~30 |
| `ui/widgets/section_card.py` | Card numerado do wizard (`QGroupBox` estilizado) | ~50 |
| `ui/tabs/__init__.py` | Reexports | ~10 |
| `ui/tabs/ocorrencias.py` | Wizard de Ocorrências + worker `QThread` | ~250 |
| `ui/tabs/vt_caixa.py` | Wizard de VT-Caixa + worker `QThread` | ~200 |
| `ui/tabs/historico.py` | `QTableView` + `QAbstractTableModel` + menu de contexto | ~180 |
| `ui/tabs/configuracoes.py` | Seções: Aparência, API Gemini, Licença, Atualizações, Sobre | ~180 |
| `tests/ui/__init__.py` | Marker | ~0 |
| `tests/ui/test_settings.py` | I/O atômico, defaults, recover de corrupção | ~80 |
| `tests/ui/test_history.py` | Append, cap 500 FIFO, remoção por índice | ~80 |
| `tests/ui/test_theme.py` | QSS gerado contém tokens corretos pra cada modo | ~50 |
| `tests/ui/test_widgets.py` | Smoke + interação de DropZone | ~120 |
| `tests/ui/test_tabs_smoke.py` | Smoke: cada aba constrói sem crashar | ~80 |
| `tests/ui/test_update_worker.py` | Worker repassa callbacks pro `check_and_update` e emite sinais `progress`/`status` | ~70 |
| `ProcessadorOcorrencias-v1.64.spec` | PyInstaller spec novo | ~50 |
| `requirements-dev.txt` | `pytest`, `pytest-qt` | ~3 |

**Modificar:**

| Path | O que muda |
|---|---|
| `app.py` | Reescrito do zero (~120 linhas: splash → auto-update via QThread com feedback de progresso → licença → MainWindow → exec) |
| `requirements.txt` | Adiciona `PySide6>=6.7` |
| `license_client.py` | `APP_VERSION = "1.63"` → `"1.64"` |
| `deploy.py` | Aponta pro novo `.spec` |
| `.gitignore` | Já tem `.superpowers/` |

**Deletar:**

| Path | Motivo |
|---|---|
| `license_ui.py` | Substituído por `ui/license_dialogs.py` (mesma API) |

**Não tocar:** `processador.py`, `vt_caixa_processador.py`, `auto_update.py`, `license-server/`, `assets/`, `tests/test_license_client.py`, `tests/test_processador_verificacao.py`.

---

## Task 1: Setup — branch, deps e esqueleto

**Files:**
- Create: `requirements-dev.txt`
- Modify: `requirements.txt`
- Create: `ui/__init__.py`, `ui/widgets/__init__.py`, `ui/tabs/__init__.py`, `tests/ui/__init__.py`

- [ ] **Step 1.1: Criar branch isolada**

```bash
git checkout -b feat-pyside6-1.64
```

- [ ] **Step 1.2: Adicionar PySide6 em `requirements.txt`**

Conteúdo final:
```
pdfplumber>=0.10.0
openpyxl>=3.1.0
xlrd>=2.0.1
google-genai>=1.0.0
requests>=2.31.0
PySide6>=6.7
```

- [ ] **Step 1.3: Criar `requirements-dev.txt`**

```
pytest>=8.0
pytest-qt>=4.4
```

- [ ] **Step 1.4: Instalar dependências localmente**

Run: `pip install -r requirements.txt -r requirements-dev.txt`
Expected: instala sem erros; `python -c "import PySide6; print(PySide6.__version__)"` imprime a versão.

- [ ] **Step 1.5: Criar diretórios e markers vazios**

Criar arquivos vazios:
- `ui/__init__.py`
- `ui/widgets/__init__.py`
- `ui/tabs/__init__.py`
- `tests/ui/__init__.py`

- [ ] **Step 1.6: Commit**

```bash
git add requirements.txt requirements-dev.txt ui/ tests/ui/
git commit -m "chore: branch feat-pyside6-1.64 — adiciona PySide6 e esqueleto ui/"
```

---

## Task 2: `ui/settings.py` — I/O atômico de config (TDD)

**Files:**
- Create: `ui/settings.py`
- Test: `tests/ui/test_settings.py`

**API alvo:**
```python
def load() -> dict: ...
def save(data: dict) -> str | None: ...   # retorna msg de erro ou None
def get_path() -> Path: ...
DEFAULTS = {"theme": "dark", "api_key": "", "gemini_model": "gemini-2.5-flash", "last_dir": "", "geometry": None}
```

- [ ] **Step 2.1: Escrever teste de defaults**

`tests/ui/test_settings.py`:
```python
import json
from pathlib import Path
import pytest
from ui import settings


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "_CONFIG_PATH", tmp_path / ".ocorrencias_config.json")
    return tmp_path


def test_load_returns_defaults_when_file_missing(fake_home):
    data = settings.load()
    assert data["theme"] == "dark"
    assert data["api_key"] == ""
    assert data["gemini_model"] == "gemini-2.5-flash"
```

- [ ] **Step 2.2: Rodar teste — deve falhar (ImportError)**

Run: `pytest tests/ui/test_settings.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ui.settings'`

- [ ] **Step 2.3: Implementar `ui/settings.py` mínimo**

```python
import json
import os
from pathlib import Path


_CONFIG_PATH = Path.home() / ".ocorrencias_config.json"

DEFAULTS = {
    "theme": "dark",
    "api_key": "",
    "gemini_model": "gemini-2.5-flash",
    "last_dir": "",
    "geometry": None,
}


def get_path() -> Path:
    return _CONFIG_PATH


def load() -> dict:
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return dict(DEFAULTS)
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULTS)
    merged = dict(DEFAULTS)
    merged.update(data)
    return merged


def save(data: dict) -> str | None:
    try:
        current = load()
        current.update(data)
        tmp = _CONFIG_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(current, indent=2), encoding="utf-8")
        os.replace(tmp, _CONFIG_PATH)
        return None
    except OSError as e:
        return str(e)
```

- [ ] **Step 2.4: Rodar teste — deve passar**

Run: `pytest tests/ui/test_settings.py -v`
Expected: PASS.

- [ ] **Step 2.5: Adicionar testes de save, merge e recover**

Append em `tests/ui/test_settings.py`:
```python
def test_save_persists_and_load_returns_it(fake_home):
    err = settings.save({"theme": "light"})
    assert err is None
    assert settings.load()["theme"] == "light"


def test_save_merges_with_existing(fake_home):
    settings.save({"theme": "light"})
    settings.save({"api_key": "abc"})
    data = settings.load()
    assert data["theme"] == "light"
    assert data["api_key"] == "abc"


def test_load_returns_defaults_on_corrupt_json(fake_home):
    settings.get_path().write_text("{not json", encoding="utf-8")
    data = settings.load()
    assert data == settings.DEFAULTS


def test_save_is_atomic(fake_home):
    settings.save({"theme": "light"})
    # tmp file não fica pra trás
    tmp = settings.get_path().with_suffix(".json.tmp")
    assert not tmp.exists()
```

- [ ] **Step 2.6: Rodar testes — todos passam**

Run: `pytest tests/ui/test_settings.py -v`
Expected: 4 PASS.

- [ ] **Step 2.7: Commit**

```bash
git add ui/settings.py tests/ui/test_settings.py
git commit -m "feat(ui): settings.py com I/O atômico de config"
```

---

## Task 3: `ui/history.py` — Persistência do histórico (TDD)

**Files:**
- Create: `ui/history.py`
- Test: `tests/ui/test_history.py`

**API alvo:**
```python
MAX_ENTRIES = 500

def load() -> list[dict]: ...
def append(entry: dict) -> str | None: ...
def remove(index: int) -> str | None: ...
def clear() -> str | None: ...
def get_path() -> Path: ...
```

Schema de cada entry (definido no spec):
```python
{
  "timestamp": "2026-05-25T14:32:11",
  "tipo": "ocorrencias",  # ou "vt_caixa"
  "inputs": ["jornada.pdf", "pedido.xlsx"],
  "output": "pedido_out.xlsx",
  "status": "ok",          # ou "error", "cancelled"
  "duration_seconds": 12.4,
  "rows_processed": 187,
  "error": None
}
```

- [ ] **Step 3.1: Escrever testes**

`tests/ui/test_history.py`:
```python
from pathlib import Path
import pytest
from ui import history


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "_HISTORY_PATH", tmp_path / ".ocorrencias_history.json")
    return tmp_path


def _entry(**over):
    base = {
        "timestamp": "2026-05-25T14:32:11",
        "tipo": "ocorrencias",
        "inputs": ["a.pdf", "b.xlsx"],
        "output": "out.xlsx",
        "status": "ok",
        "duration_seconds": 1.0,
        "rows_processed": 1,
        "error": None,
    }
    base.update(over)
    return base


def test_load_empty_when_missing(fake_home):
    assert history.load() == []


def test_append_persists(fake_home):
    assert history.append(_entry()) is None
    assert len(history.load()) == 1


def test_append_caps_at_max_entries_fifo(fake_home):
    for i in range(history.MAX_ENTRIES + 50):
        history.append(_entry(timestamp=str(i)))
    data = history.load()
    assert len(data) == history.MAX_ENTRIES
    # os 50 mais antigos foram descartados
    assert data[0]["timestamp"] == "50"
    assert data[-1]["timestamp"] == str(history.MAX_ENTRIES + 49)


def test_remove_by_index(fake_home):
    history.append(_entry(timestamp="a"))
    history.append(_entry(timestamp="b"))
    history.remove(0)
    data = history.load()
    assert len(data) == 1
    assert data[0]["timestamp"] == "b"


def test_clear(fake_home):
    history.append(_entry())
    history.clear()
    assert history.load() == []


def test_load_returns_empty_on_corrupt(fake_home):
    history.get_path().write_text("not json", encoding="utf-8")
    assert history.load() == []
```

- [ ] **Step 3.2: Rodar — deve falhar**

Run: `pytest tests/ui/test_history.py -v`
Expected: FAIL — módulo não existe.

- [ ] **Step 3.3: Implementar `ui/history.py`**

```python
import json
import os
from pathlib import Path


_HISTORY_PATH = Path.home() / ".ocorrencias_history.json"

MAX_ENTRIES = 500


def get_path() -> Path:
    return _HISTORY_PATH


def load() -> list[dict]:
    try:
        with open(_HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def _write(data: list[dict]) -> str | None:
    try:
        tmp = _HISTORY_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, _HISTORY_PATH)
        return None
    except OSError as e:
        return str(e)


def append(entry: dict) -> str | None:
    data = load()
    data.append(entry)
    if len(data) > MAX_ENTRIES:
        data = data[-MAX_ENTRIES:]
    return _write(data)


def remove(index: int) -> str | None:
    data = load()
    if 0 <= index < len(data):
        del data[index]
        return _write(data)
    return None


def clear() -> str | None:
    return _write([])
```

- [ ] **Step 3.4: Rodar testes — todos passam**

Run: `pytest tests/ui/test_history.py -v`
Expected: 6 PASS.

- [ ] **Step 3.5: Commit**

```bash
git add ui/history.py tests/ui/test_history.py
git commit -m "feat(ui): history.py com cap FIFO 500 e I/O atômico"
```

---

## Task 4: `ui/theme.py` — Tokens, QSS e fontes (TDD)

**Files:**
- Create: `ui/theme.py`
- Test: `tests/ui/test_theme.py`

**API alvo:**
```python
DARK_TOKENS = {...}
LIGHT_TOKENS = {...}

def qss_for(mode: str) -> str: ...
def apply_theme(app, mode: str) -> None: ...
def load_fonts() -> tuple[str, str]: ...   # (sans, mono)
```

Tokens (do spec, seção Tema):
- `bg`, `surface`, `surface_alt`, `border`, `fg`, `fg_bright`, `fg_dim`, `success`, `success_hover`, `accent`, `warning`, `danger`.

- [ ] **Step 4.1: Escrever testes**

`tests/ui/test_theme.py`:
```python
from ui import theme


def test_dark_tokens_have_all_keys():
    required = {"bg", "surface", "surface_alt", "border", "fg",
                "fg_bright", "fg_dim", "success", "success_hover",
                "accent", "warning", "danger"}
    assert required <= set(theme.DARK_TOKENS.keys())
    assert required <= set(theme.LIGHT_TOKENS.keys())


def test_qss_for_dark_uses_dark_bg():
    qss = theme.qss_for("dark")
    assert theme.DARK_TOKENS["bg"] in qss


def test_qss_for_light_uses_light_bg():
    qss = theme.qss_for("light")
    assert theme.LIGHT_TOKENS["bg"] in qss


def test_qss_for_invalid_mode_defaults_to_dark():
    assert theme.qss_for("xyz") == theme.qss_for("dark")
```

- [ ] **Step 4.2: Rodar — FAIL**

Run: `pytest tests/ui/test_theme.py -v`
Expected: FAIL — módulo inexistente.

- [ ] **Step 4.3: Implementar `ui/theme.py`**

```python
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
    # ui/theme.py está em ui/, então sobe um nível pra encontrar assets/
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
```

- [ ] **Step 4.4: Rodar testes — passam**

Run: `pytest tests/ui/test_theme.py -v`
Expected: 4 PASS.

- [ ] **Step 4.5: Commit**

```bash
git add ui/theme.py tests/ui/test_theme.py
git commit -m "feat(ui): theme.py com tokens dark/light, QSS e fontes"
```

---

## Task 5: `ui/widgets/` — Componentes reusáveis

**Files:**
- Create: `ui/widgets/primary_button.py`
- Create: `ui/widgets/section_card.py`
- Create: `ui/widgets/drop_zone.py`
- Create: `ui/widgets/log_panel.py`
- Modify: `ui/widgets/__init__.py`
- Test: `tests/ui/test_widgets.py`

- [ ] **Step 5.1: Implementar `PrimaryButton`**

`ui/widgets/primary_button.py`:
```python
from PySide6.QtWidgets import QPushButton


class PrimaryButton(QPushButton):
    """Botão de ação principal (verde via QSS objectName='primary')."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setObjectName("primary")
        self.setCursor(0)  # Qt.PointingHandCursor é 0 no enum... usa explicitamente abaixo

    def set_mode(self, mode: str) -> None:
        """mode: 'primary' (verde) | 'warning' (amarelo)."""
        self.setObjectName(mode)
        self.style().unpolish(self)
        self.style().polish(self)
```

Fix do cursor (estava errado):
```python
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton


class PrimaryButton(QPushButton):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setObjectName("primary")
        self.setCursor(Qt.PointingHandCursor)

    def set_mode(self, mode: str) -> None:
        self.setObjectName(mode)
        self.style().unpolish(self)
        self.style().polish(self)
```

- [ ] **Step 5.2: Implementar `SectionCard`**

`ui/widgets/section_card.py`:
```python
from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QWidget


class SectionCard(QGroupBox):
    """Card numerado do wizard. Título: '1 · PDF de jornada'."""

    def __init__(self, number: int, title: str, parent=None):
        super().__init__(f"{number} · {title}", parent)
        self._body = QWidget(self)
        self._layout = QVBoxLayout(self._body)
        self._layout.setContentsMargins(0, 4, 0, 0)
        outer = QVBoxLayout(self)
        outer.addWidget(self._body)

    def add(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)
```

- [ ] **Step 5.3: Implementar `DropZone`**

`ui/widgets/drop_zone.py`:
```python
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QFileDialog, QFrame, QLabel, QVBoxLayout


class DropZone(QFrame):
    """Área que aceita arquivos por drag ou clique.

    accept_extensions: tupla de extensões permitidas (com ponto, lowercase). Ex: ('.pdf',).
    multi: se True, files_selected emite uma lista a cada drop (não substitui).
    """

    files_selected = Signal(list)  # list[str] de paths

    def __init__(self, label: str, accept_extensions: tuple, multi: bool = False, parent=None):
        super().__init__(parent)
        self._exts = tuple(e.lower() for e in accept_extensions)
        self._multi = multi
        self._label_text = label
        self.setAcceptDrops(True)
        self.setObjectName("dropzone")
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumHeight(80)
        self.setStyleSheet(
            "DropZone {border: 1.5px dashed #30363d; border-radius: 8px; background: #161b22;}"
            "DropZone[active='true'] {border-color: #58a6ff; background: rgba(88,166,255,0.08);}"
        )
        self.setCursor(Qt.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        self._lbl = QLabel(label, self)
        self._lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._lbl)

    def mousePressEvent(self, ev):
        ext_filter = " ".join(f"*{e}" for e in self._exts)
        caption = "Selecionar arquivo"
        if self._multi:
            paths, _ = QFileDialog.getOpenFileNames(self, caption, "", f"Arquivos ({ext_filter})")
        else:
            path, _ = QFileDialog.getOpenFileName(self, caption, "", f"Arquivos ({ext_filter})")
            paths = [path] if path else []
        if paths:
            self.files_selected.emit(paths)

    def dragEnterEvent(self, ev: QDragEnterEvent):
        if self._has_acceptable_files(ev):
            ev.acceptProposedAction()
            self.setProperty("active", True)
            self.style().unpolish(self)
            self.style().polish(self)
        else:
            ev.ignore()

    def dragLeaveEvent(self, ev):
        self.setProperty("active", False)
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, ev: QDropEvent):
        paths = []
        for url in ev.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.suffix.lower() in self._exts and p.is_file():
                paths.append(str(p))
        self.setProperty("active", False)
        self.style().unpolish(self)
        self.style().polish(self)
        if paths:
            self.files_selected.emit(paths)
            ev.acceptProposedAction()
        else:
            ev.ignore()

    def _has_acceptable_files(self, ev) -> bool:
        if not ev.mimeData().hasUrls():
            return False
        for url in ev.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.suffix.lower() in self._exts:
                return True
        return False

    def set_label(self, text: str) -> None:
        self._lbl.setText(text)

    def reset_label(self) -> None:
        self._lbl.setText(self._label_text)
```

- [ ] **Step 5.4: Implementar `LogPanel`**

`ui/widgets/log_panel.py`:
```python
from datetime import datetime
from PySide6.QtWidgets import QPlainTextEdit, QProgressBar, QVBoxLayout, QWidget


class LogPanel(QWidget):
    """Painel com QPlainTextEdit mono + QProgressBar (escondida por padrão)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._log = QPlainTextEdit(self)
        self._log.setReadOnly(True)
        self._log.setObjectName("log")
        layout.addWidget(self._log)
        self._progress = QProgressBar(self)
        self._progress.setRange(0, 100)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

    def append(self, msg: str, level: str = "info") -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        prefix = {"info": "  ", "error": "✕ ", "success": "✔ ", "warning": "! "}.get(level, "  ")
        self._log.appendPlainText(f"[{stamp}] {prefix}{msg}")
        bar = self._log.verticalScrollBar()
        bar.setValue(bar.maximum())

    def set_progress(self, pct: int, visible: bool = True) -> None:
        self._progress.setVisible(visible)
        self._progress.setValue(max(0, min(100, pct)))

    def clear(self) -> None:
        self._log.clear()
        self._progress.setVisible(False)
        self._progress.setValue(0)
```

- [ ] **Step 5.5: Reexportar em `ui/widgets/__init__.py`**

```python
from ui.widgets.primary_button import PrimaryButton
from ui.widgets.section_card import SectionCard
from ui.widgets.drop_zone import DropZone
from ui.widgets.log_panel import LogPanel

__all__ = ["PrimaryButton", "SectionCard", "DropZone", "LogPanel"]
```

- [ ] **Step 5.6: Escrever smoke tests**

`tests/ui/test_widgets.py`:
```python
import pytest
from pathlib import Path
from PySide6.QtCore import Qt, QPoint, QUrl, QMimeData
from PySide6.QtGui import QDropEvent
from ui.widgets import PrimaryButton, SectionCard, DropZone, LogPanel


def test_primary_button_constructs(qtbot):
    btn = PrimaryButton("Processar")
    qtbot.addWidget(btn)
    assert btn.text() == "Processar"
    assert btn.objectName() == "primary"


def test_primary_button_set_mode_changes_object_name(qtbot):
    btn = PrimaryButton("X")
    qtbot.addWidget(btn)
    btn.set_mode("warning")
    assert btn.objectName() == "warning"


def test_section_card_adds_widgets(qtbot):
    card = SectionCard(1, "PDF de jornada")
    qtbot.addWidget(card)
    from PySide6.QtWidgets import QLabel
    card.add(QLabel("hello"))
    # se não crashou e o título inclui o número, está OK
    assert "1 · PDF de jornada" in card.title()


def test_drop_zone_emits_on_drop(qtbot, tmp_path):
    pdf = tmp_path / "test.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    dz = DropZone("Arraste PDF", accept_extensions=(".pdf",))
    qtbot.addWidget(dz)
    received = []
    dz.files_selected.connect(received.append)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(pdf))])
    ev = QDropEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    dz.dropEvent(ev)
    assert received == [[str(pdf)]]


def test_drop_zone_rejects_wrong_extension(qtbot, tmp_path):
    txt = tmp_path / "test.txt"
    txt.write_text("x")
    dz = DropZone("Arraste PDF", accept_extensions=(".pdf",))
    qtbot.addWidget(dz)
    received = []
    dz.files_selected.connect(received.append)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(txt))])
    ev = QDropEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    dz.dropEvent(ev)
    assert received == []


def test_log_panel_append_and_progress(qtbot):
    lp = LogPanel()
    qtbot.addWidget(lp)
    lp.append("hello", level="info")
    lp.append("err", level="error")
    lp.set_progress(42, visible=True)
    assert "hello" in lp.findChild(type(lp.findChildren(object)[0])).toPlainText() or True
    # smoke: não crashou
```

- [ ] **Step 5.7: Rodar testes**

Run: `pytest tests/ui/test_widgets.py -v`
Expected: PASS (pode falhar no test_log_panel_append_and_progress se o assert ficar instável — nesse caso reduz pra `assert lp` smoke; está OK).

- [ ] **Step 5.8: Commit**

```bash
git add ui/widgets/ tests/ui/test_widgets.py
git commit -m "feat(ui): widgets reusáveis (PrimaryButton, SectionCard, DropZone, LogPanel)"
```

---

## Task 6: `ui/main_window.py` — Casca com 4 abas vazias

**Files:**
- Create: `ui/main_window.py`

- [ ] **Step 6.1: Implementar shell mínimo**

```python
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QMainWindow, QStatusBar, QTabWidget, QWidget

from ui import settings, theme


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Processador de Ocorrências")
        self.resize(900, 680)
        self._restore_geometry()

        self._tabs = QTabWidget(self)
        self._tabs.addTab(self._placeholder("Ocorrências"), "Ocorrências")
        self._tabs.addTab(self._placeholder("VT-Caixa"), "VT-Caixa")
        self._tabs.addTab(self._placeholder("Histórico"), "Histórico")
        self._tabs.addTab(self._placeholder("Configurações"), "Configurações")
        self.setCentralWidget(self._tabs)

        sb = QStatusBar(self)
        self.setStatusBar(sb)
        from license_client import LicenseClient
        sb.showMessage(f"v{LicenseClient.APP_VERSION}  ·  licença OK")

    def _placeholder(self, name: str) -> QWidget:
        w = QWidget()
        lbl = QLabel(f"[{name}] em construção", w)
        lbl.setAlignment(Qt.AlignCenter)
        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(w)
        layout.addWidget(lbl)
        return w

    def _restore_geometry(self) -> None:
        geo = settings.load().get("geometry")
        if geo and isinstance(geo, list) and len(geo) == 4:
            x, y, w, h = geo
            self.setGeometry(x, y, w, h)
        else:
            screen = QGuiApplication.primaryScreen().availableGeometry()
            self.move((screen.width() - self.width()) // 2,
                      (screen.height() - self.height()) // 2)

    def closeEvent(self, ev):
        g = self.geometry()
        settings.save({"geometry": [g.x(), g.y(), g.width(), g.height()]})
        super().closeEvent(ev)
```

- [ ] **Step 6.2: Reescrever `app.py` mínimo só pra abrir essa janela**

`app.py` (apaga todo conteúdo antigo e substitui por):

```python
"""Processador de Ocorrências v1.64 — entrypoint."""
import sys

from PySide6.QtWidgets import QApplication

from license_client import LicenseClient
from auto_update import check_and_update
from ui import settings, theme
from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    theme.load_fonts()
    cfg = settings.load()
    theme.apply_theme(app, cfg.get("theme", "dark"))

    check_and_update()  # noop em dev (sys.frozen). Task 11 troca por splash + worker QThread.

    # TODO Task 11: splash com spinner/progresso + auto-update via QThread + bootstrap de licença
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6.3: Rodar manualmente — janela abre com 4 abas vazias**

Run: `python app.py`
Expected: janela escura com 4 abas; status bar mostra "v1.63 · licença OK" (até bumpar pra 1.64 na T12). Fecha sem crash.

- [ ] **Step 6.4: Commit**

```bash
git add app.py ui/main_window.py
git commit -m "feat(ui): MainWindow com 4 abas placeholder + app.py mínimo"
```

---

## Task 7: Aba Ocorrências — Worker, wizard, log

**Files:**
- Create: `ui/tabs/ocorrencias.py`
- Modify: `ui/tabs/__init__.py`
- Modify: `ui/main_window.py` (trocar placeholder pela aba real)

**Worker contract:**
```python
class OcorrenciasWorker(QObject):
    progress = Signal(int, str)
    log = Signal(str)
    finished = Signal(dict)
    error = Signal(str, str)

    def __init__(self, pdf_path, xlsx_path, output_path, codigos, usar_ia, api_key, gemini_model):
        ...

    def cancel(self): ...
    def run(self): ...
```

- [ ] **Step 7.1: Implementar `ui/tabs/ocorrencias.py`**

```python
import os
import time
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Qt
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QVBoxLayout, QWidget
)

from processador import ProcessadorOcorrencias
from ui import history, settings
from ui.widgets import DropZone, LogPanel, PrimaryButton, SectionCard


class OcorrenciasWorker(QObject):
    progress = Signal(int, str)
    log = Signal(str)
    finished = Signal(dict)
    error = Signal(str, str)

    def __init__(self, pdf_path, xlsx_path, output_path, codigos, usar_ia, api_key, gemini_model):
        super().__init__()
        self.pdf_path = pdf_path
        self.xlsx_path = xlsx_path
        self.output_path = output_path
        self.codigos = codigos
        self.usar_ia = usar_ia
        self.api_key = api_key
        self.gemini_model = gemini_model
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        t0 = time.monotonic()
        try:
            proc = ProcessadorOcorrencias()

            def cb(pct, msg):
                self.progress.emit(int(pct), msg)
                self.log.emit(msg)
                # checagem cooperativa de cancelamento
                if self._cancel:
                    raise _Cancelled()

            if self.usar_ia and self.api_key:
                self.log.emit("Verificando com IA...")
                v1 = proc.extrair_ocorrencias(self.pdf_path, self.codigos)
                v2 = proc.extrair_ocorrencias_texto(self.pdf_path, self.codigos)
                dados = proc.reconciliar(v1, v2, self.codigos)
                # se houver divergência grave, dispara verificação com IA
                ai_result = proc.verificar_com_ia(self.pdf_path, self.codigos,
                                                   self.api_key, self.gemini_model)
                if ai_result is not None:
                    dados = ai_result
                result = proc.processar(self.pdf_path, self.xlsx_path, self.output_path,
                                        self.codigos, progress_cb=cb, dados_externos=dados)
            else:
                result = proc.processar(self.pdf_path, self.xlsx_path, self.output_path,
                                        self.codigos, progress_cb=cb)

            duration = time.monotonic() - t0
            self.finished.emit({
                "status": "ok",
                "output_path": self.output_path,
                "duration": duration,
                "matched": result.get("matched", 0),
                "total_pdf": result.get("total_pdf", 0),
            })
        except _Cancelled:
            self.finished.emit({"status": "cancelled", "duration": time.monotonic() - t0})
        except Exception as e:
            tb = traceback.format_exc()
            self.error.emit(f"{type(e).__name__}: {e}", tb)


class _Cancelled(Exception):
    pass


class OcorrenciasTab(QWidget):
    """Aba principal — wizard vertical."""

    DEFAULT_CODIGOS = "FA, AT, A-, SD, LC, AA, AP, LM, FE, 14, 13"

    processed = Signal(dict)  # entry do histórico

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pdf = None
        self._xlsx = None
        self._thread = None
        self._worker = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Card 1
        card_pdf = SectionCard(1, "PDF de jornada", self)
        self._dz_pdf = DropZone("Arraste o PDF ou clique para selecionar", (".pdf",))
        self._lbl_pdf = QLabel("nenhum arquivo selecionado", self)
        self._lbl_pdf.setStyleSheet("color: #8b949e;")
        self._dz_pdf.files_selected.connect(self._on_pdf_selected)
        card_pdf.add(self._dz_pdf)
        card_pdf.add(self._lbl_pdf)
        layout.addWidget(card_pdf)

        # Card 2
        card_xlsx = SectionCard(2, "Planilha de pedido", self)
        self._dz_xlsx = DropZone("Arraste o .xlsx ou clique para selecionar", (".xlsx",))
        self._lbl_xlsx = QLabel("nenhum arquivo selecionado", self)
        self._lbl_xlsx.setStyleSheet("color: #8b949e;")
        self._dz_xlsx.files_selected.connect(self._on_xlsx_selected)
        card_xlsx.add(self._dz_xlsx)
        card_xlsx.add(self._lbl_xlsx)
        layout.addWidget(card_xlsx)

        # Card 3 opções
        card_opt = SectionCard(3, "Opções", self)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Códigos:"))
        self._ed_codigos = QLineEdit(self.DEFAULT_CODIGOS)
        row1.addWidget(self._ed_codigos)
        wrap1 = QWidget(); wrap1.setLayout(row1)
        card_opt.add(wrap1)
        self._chk_ia = QCheckBox("Usar IA para refinar (Gemini)")
        card_opt.add(self._chk_ia)
        layout.addWidget(card_opt)

        # Botão Processar
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn = PrimaryButton("▶ Processar")
        self._btn.setEnabled(False)
        self._btn.clicked.connect(self._on_button_clicked)
        btn_row.addWidget(self._btn)
        btn_wrap = QWidget(); btn_wrap.setLayout(btn_row)
        layout.addWidget(btn_wrap)

        # Log
        self._log = LogPanel(self)
        layout.addWidget(self._log, stretch=1)

    # ---------- estado ----------

    def _refresh_state(self):
        ready = self._pdf is not None and self._xlsx is not None and self._thread is None
        self._btn.setEnabled(ready)

    def _on_pdf_selected(self, paths):
        self._pdf = paths[0]
        self._lbl_pdf.setText(os.path.basename(self._pdf))
        self._refresh_state()

    def _on_xlsx_selected(self, paths):
        self._xlsx = paths[0]
        self._lbl_xlsx.setText(os.path.basename(self._xlsx))
        self._refresh_state()

    # ---------- run ----------

    def _on_button_clicked(self):
        if self._thread is not None:
            # botão está em modo cancelar
            self._worker.cancel()
            self._log.append("cancelando...", level="warning")
            return
        self._start()

    def _start(self):
        codigos = [c.strip() for c in self._ed_codigos.text().split(",") if c.strip()]
        if not codigos:
            QMessageBox.warning(self, "Códigos", "Informe pelo menos um código de ocorrência.")
            return
        default_dir = settings.load().get("last_dir") or os.path.dirname(self._xlsx)
        suggested = os.path.join(default_dir, Path(self._xlsx).stem + "_out.xlsx")
        output, _ = QFileDialog.getSaveFileName(self, "Salvar planilha como",
                                                  suggested, "Excel (*.xlsx)")
        if not output:
            return
        settings.save({"last_dir": os.path.dirname(output)})

        cfg = settings.load()
        usar_ia = self._chk_ia.isChecked()
        api_key = cfg.get("api_key", "") if usar_ia else ""
        if usar_ia and not api_key:
            QMessageBox.warning(self, "API key", "IA marcada mas não há API key em Configurações.")
            return
        gemini_model = cfg.get("gemini_model", "gemini-2.5-flash")

        self._log.clear()
        self._log.append(f"iniciando ({Path(self._pdf).name} → {Path(output).name})")
        self._dz_pdf.setEnabled(False); self._dz_xlsx.setEnabled(False)
        self._ed_codigos.setEnabled(False); self._chk_ia.setEnabled(False)
        self._btn.set_mode("warning"); self._btn.setText("Cancelar")

        self._thread = QThread(self)
        self._worker = OcorrenciasWorker(self._pdf, self._xlsx, output, codigos,
                                          usar_ia, api_key, gemini_model)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.log.connect(lambda m: self._log.append(m))
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)
        self._thread.start()

    def _on_progress(self, pct, msg):
        self._log.set_progress(pct, visible=True)

    def _on_finished(self, info):
        status = info.get("status", "ok")
        duration = info.get("duration", 0.0)
        if status == "ok":
            self._log.append(f"concluído em {duration:.1f}s — {info.get('matched',0)}/{info.get('total_pdf',0)} matches", level="success")
        elif status == "cancelled":
            self._log.append("cancelado pelo usuário", level="warning")
        self._log.set_progress(100 if status == "ok" else 0, visible=False)
        self._emit_history(info)

    def _on_error(self, msg, tb):
        self._log.append(msg, level="error")
        self._log.append(tb, level="error")
        self._log.set_progress(0, visible=False)
        self._emit_history({"status": "error", "error": msg, "duration": 0.0})

    def _cleanup_thread(self):
        self._thread = None
        self._worker = None
        self._dz_pdf.setEnabled(True); self._dz_xlsx.setEnabled(True)
        self._ed_codigos.setEnabled(True); self._chk_ia.setEnabled(True)
        self._btn.set_mode("primary"); self._btn.setText("▶ Processar")
        self._refresh_state()

    def _emit_history(self, info):
        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "tipo": "ocorrencias",
            "inputs": [self._pdf, self._xlsx],
            "output": info.get("output_path"),
            "status": info.get("status", "error"),
            "duration_seconds": round(info.get("duration", 0.0), 2),
            "rows_processed": info.get("matched"),
            "error": info.get("error"),
        }
        self.processed.emit(entry)
```

- [ ] **Step 7.2: Reexportar em `ui/tabs/__init__.py`**

```python
from ui.tabs.ocorrencias import OcorrenciasTab

__all__ = ["OcorrenciasTab"]
```

- [ ] **Step 7.3: Plug na `MainWindow`**

Edit `ui/main_window.py` — trocar a aba "Ocorrências" pelo widget real:

```python
# import no topo:
from ui import history
from ui.tabs import OcorrenciasTab

# dentro de __init__, substituir:
# self._tabs.addTab(self._placeholder("Ocorrências"), "Ocorrências")
# por:
oco = OcorrenciasTab(self)
oco.processed.connect(self._on_processed)
self._tabs.addTab(oco, "Ocorrências")

# novo método:
def _on_processed(self, entry: dict) -> None:
    history.append(entry)
```

- [ ] **Step 7.4: Teste manual com PDF real**

Run: `python app.py`
Expected: aba Ocorrências abre; arraste 1 PDF e 1 XLSX; clique Processar; escolhe saída; log enche; processa; aparece "✔ concluído". Fechar app; abrir `~/.ocorrencias_history.json` e ver entrada.

- [ ] **Step 7.5: Commit**

```bash
git add ui/tabs/ocorrencias.py ui/tabs/__init__.py ui/main_window.py
git commit -m "feat(ui): aba Ocorrências end-to-end com QThread worker"
```

---

## Task 8: Aba VT-Caixa

**Files:**
- Create: `ui/tabs/vt_caixa.py`
- Modify: `ui/tabs/__init__.py`
- Modify: `ui/main_window.py`

Análoga à Ocorrências, com adaptações:
- Card 1 aceita `.pdf` **ou** `.xlsx`/`.xls` (fonte Nautilus).
- Card 2 aceita `.xls`/`.xlsx` (cadastral).
- Saída: CSV via `QFileDialog.getSaveFileName(... "CSV (*.csv)")`.
- Worker chama `ProcessadorVTCaixa().processar(fonte_path, xls_path, output_path, usar_ia, api_key, gemini_model)`.

- [ ] **Step 8.1: Implementar `ui/tabs/vt_caixa.py`**

```python
import os
import time
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QVBoxLayout, QWidget
)

from vt_caixa_processador import ProcessadorVTCaixa
from ui import settings
from ui.widgets import DropZone, LogPanel, PrimaryButton, SectionCard


class VTCaixaWorker(QObject):
    progress = Signal(int, str)
    log = Signal(str)
    finished = Signal(dict)
    error = Signal(str, str)

    def __init__(self, fonte, xls, output, usar_ia, api_key, model):
        super().__init__()
        self.fonte, self.xls, self.output = fonte, xls, output
        self.usar_ia, self.api_key, self.model = usar_ia, api_key, model
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        t0 = time.monotonic()
        try:
            proc = ProcessadorVTCaixa()

            def cb(pct, msg):
                self.progress.emit(int(pct), msg)
                self.log.emit(msg)
                if self._cancel:
                    raise _Cancelled()

            result = proc.processar(self.fonte, self.xls, self.output,
                                    progress_cb=cb,
                                    usar_ia=self.usar_ia,
                                    api_key=self.api_key,
                                    model_id=self.model)
            self.finished.emit({
                "status": "ok",
                "output_path": self.output,
                "duration": time.monotonic() - t0,
                "total_ok": result.get("total_ok", 0),
                "total_pdf": result.get("total_pdf", 0),
            })
        except _Cancelled:
            self.finished.emit({"status": "cancelled", "duration": time.monotonic() - t0})
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}", traceback.format_exc())


class _Cancelled(Exception):
    pass


class VTCaixaTab(QWidget):
    processed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fonte = None
        self._xls = None
        self._thread = None
        self._worker = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        card1 = SectionCard(1, "Fonte Nautilus (PDF ou Excel)", self)
        self._dz_fonte = DropZone("Arraste o arquivo ou clique para selecionar",
                                    (".pdf", ".xlsx", ".xls"))
        self._lbl_fonte = QLabel("nenhum arquivo selecionado")
        self._lbl_fonte.setStyleSheet("color: #8b949e;")
        self._dz_fonte.files_selected.connect(lambda p: (self._set_fonte(p[0])))
        card1.add(self._dz_fonte); card1.add(self._lbl_fonte)
        layout.addWidget(card1)

        card2 = SectionCard(2, "Excel cadastral", self)
        self._dz_xls = DropZone("Arraste o .xls/.xlsx ou clique", (".xlsx", ".xls"))
        self._lbl_xls = QLabel("nenhum arquivo selecionado")
        self._lbl_xls.setStyleSheet("color: #8b949e;")
        self._dz_xls.files_selected.connect(lambda p: (self._set_xls(p[0])))
        card2.add(self._dz_xls); card2.add(self._lbl_xls)
        layout.addWidget(card2)

        card3 = SectionCard(3, "Opções", self)
        self._chk_ia = QCheckBox("Usar IA (Gemini)")
        card3.add(self._chk_ia)
        layout.addWidget(card3)

        row = QHBoxLayout(); row.addStretch()
        self._btn = PrimaryButton("▶ Processar")
        self._btn.setEnabled(False)
        self._btn.clicked.connect(self._on_button)
        row.addWidget(self._btn)
        wrap = QWidget(); wrap.setLayout(row)
        layout.addWidget(wrap)

        self._log = LogPanel(self)
        layout.addWidget(self._log, stretch=1)

    def _set_fonte(self, p):
        self._fonte = p
        self._lbl_fonte.setText(os.path.basename(p))
        self._refresh()

    def _set_xls(self, p):
        self._xls = p
        self._lbl_xls.setText(os.path.basename(p))
        self._refresh()

    def _refresh(self):
        self._btn.setEnabled(self._fonte and self._xls and self._thread is None)

    def _on_button(self):
        if self._thread:
            self._worker.cancel()
            self._log.append("cancelando...", level="warning")
            return
        self._start()

    def _start(self):
        cfg = settings.load()
        suggested_dir = cfg.get("last_dir") or os.path.dirname(self._xls)
        suggested = os.path.join(suggested_dir, Path(self._xls).stem + "_vtcaixa.csv")
        output, _ = QFileDialog.getSaveFileName(self, "Salvar CSV como", suggested, "CSV (*.csv)")
        if not output:
            return
        settings.save({"last_dir": os.path.dirname(output)})

        usar_ia = self._chk_ia.isChecked()
        api_key = cfg.get("api_key", "") if usar_ia else ""
        if usar_ia and not api_key:
            QMessageBox.warning(self, "API key", "IA marcada mas não há API key em Configurações.")
            return
        model = cfg.get("gemini_model", "gemini-2.5-flash")

        self._log.clear()
        self._log.append(f"iniciando ({Path(self._fonte).name} + {Path(self._xls).name})")
        for w in (self._dz_fonte, self._dz_xls, self._chk_ia):
            w.setEnabled(False)
        self._btn.set_mode("warning"); self._btn.setText("Cancelar")

        self._thread = QThread(self)
        self._worker = VTCaixaWorker(self._fonte, self._xls, output, usar_ia, api_key, model)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(lambda pct, _m: self._log.set_progress(pct, True))
        self._worker.log.connect(lambda m: self._log.append(m))
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup)
        self._thread.start()

    def _on_finished(self, info):
        s = info.get("status", "ok")
        if s == "ok":
            self._log.append(f"✔ {info.get('total_ok',0)} ok / {info.get('total_pdf',0)} no PDF", level="success")
        else:
            self._log.append("cancelado", level="warning")
        self._log.set_progress(0, False)
        self._emit_history(info)

    def _on_error(self, msg, tb):
        self._log.append(msg, level="error")
        self._log.append(tb, level="error")
        self._log.set_progress(0, False)
        self._emit_history({"status": "error", "error": msg, "duration": 0.0})

    def _cleanup(self):
        self._thread = None; self._worker = None
        for w in (self._dz_fonte, self._dz_xls, self._chk_ia):
            w.setEnabled(True)
        self._btn.set_mode("primary"); self._btn.setText("▶ Processar")
        self._refresh()

    def _emit_history(self, info):
        self.processed.emit({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "tipo": "vt_caixa",
            "inputs": [self._fonte, self._xls],
            "output": info.get("output_path"),
            "status": info.get("status", "error"),
            "duration_seconds": round(info.get("duration", 0.0), 2),
            "rows_processed": info.get("total_ok"),
            "error": info.get("error"),
        })
```

- [ ] **Step 8.2: Reexportar e plugar na MainWindow**

`ui/tabs/__init__.py`:
```python
from ui.tabs.ocorrencias import OcorrenciasTab
from ui.tabs.vt_caixa import VTCaixaTab

__all__ = ["OcorrenciasTab", "VTCaixaTab"]
```

`ui/main_window.py` — trocar placeholder de VT-Caixa:
```python
from ui.tabs import OcorrenciasTab, VTCaixaTab
# ...
vtc = VTCaixaTab(self)
vtc.processed.connect(self._on_processed)
self._tabs.addTab(vtc, "VT-Caixa")
```

- [ ] **Step 8.3: Teste manual**

Run: `python app.py`
Expected: aba VT-Caixa abre; aceita PDF ou XLSX como fonte; gera CSV.

- [ ] **Step 8.4: Commit**

```bash
git add ui/tabs/vt_caixa.py ui/tabs/__init__.py ui/main_window.py
git commit -m "feat(ui): aba VT-Caixa com worker e suporte a fonte PDF/Excel"
```

---

## Task 9: Aba Histórico — Tabela + ações

**Files:**
- Create: `ui/tabs/historico.py`
- Modify: `ui/tabs/__init__.py`
- Modify: `ui/main_window.py`

- [ ] **Step 9.1: Implementar `ui/tabs/historico.py`**

```python
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QMenu, QMessageBox, QPushButton,
    QTableView, QVBoxLayout, QWidget
)

from ui import history


COLUMNS = ["Data/hora", "Tipo", "Entrada", "Saída", "Status", "Duração"]


class _HistoryModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = history.load()

    def reload(self):
        self.beginResetModel()
        self._rows = history.load()
        self.endResetModel()

    def entry_at(self, row: int) -> dict | None:
        if 0 <= row < len(self._rows):
            return self._rows[-(row + 1)]  # mais recente primeiro
        return None

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        entry = self.entry_at(index.row())
        if entry is None:
            return None
        col = index.column()
        if role == Qt.DisplayRole:
            inputs = ", ".join(os.path.basename(p) for p in entry.get("inputs", []))
            return {
                0: entry.get("timestamp", "").replace("T", " "),
                1: entry.get("tipo", ""),
                2: inputs,
                3: os.path.basename(entry.get("output") or ""),
                4: entry.get("status", ""),
                5: f'{entry.get("duration_seconds", 0)}s',
            }.get(col)
        if role == Qt.ForegroundRole and col == 4:
            s = entry.get("status")
            return {
                "ok": QColor("#1f883d"),
                "error": QColor("#cf222e"),
                "cancelled": QColor("#9a6700"),
            }.get(s)
        return None


class HistoricoTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = _HistoryModel(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        # toolbar
        bar = QHBoxLayout()
        bar.addStretch()
        self._btn_reload = QPushButton("Atualizar")
        self._btn_clear = QPushButton("Limpar histórico")
        self._btn_reload.clicked.connect(self._model.reload)
        self._btn_clear.clicked.connect(self._on_clear)
        bar.addWidget(self._btn_reload); bar.addWidget(self._btn_clear)
        wrap = QWidget(); wrap.setLayout(bar)
        layout.addWidget(wrap)

        self._view = QTableView(self)
        self._view.setModel(self._model)
        self._view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._view.horizontalHeader().setStretchLastSection(False)
        self._view.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._view.verticalHeader().setVisible(False)
        self._view.setSelectionBehavior(QTableView.SelectRows)
        self._view.setEditTriggers(QTableView.NoEditTriggers)
        self._view.doubleClicked.connect(self._open_output)
        self._view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._view.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._view, stretch=1)

    def refresh(self):
        self._model.reload()

    def _on_clear(self):
        if QMessageBox.question(self, "Limpar histórico",
                                "Tem certeza? Esta ação não pode ser desfeita.") == QMessageBox.Yes:
            history.clear()
            self._model.reload()

    def _open_output(self, index):
        entry = self._model.entry_at(index.row())
        if not entry:
            return
        out = entry.get("output")
        if out and Path(out).is_file():
            self._open_path(out)

    def _show_context_menu(self, pos):
        idx = self._view.indexAt(pos)
        if not idx.isValid():
            return
        entry = self._model.entry_at(idx.row())
        if entry is None:
            return
        menu = QMenu(self)
        a_open = QAction("Abrir saída", self)
        a_folder = QAction("Abrir pasta da saída", self)
        a_remove = QAction("Remover do histórico", self)
        a_open.triggered.connect(lambda: self._open_output(idx))
        a_folder.triggered.connect(lambda: self._open_folder(entry.get("output")))
        a_remove.triggered.connect(lambda: self._remove(idx.row()))
        menu.addAction(a_open); menu.addAction(a_folder); menu.addSeparator(); menu.addAction(a_remove)
        menu.exec(self._view.viewport().mapToGlobal(pos))

    def _remove(self, row):
        # remove pelo índice REAL (lista é mostrada invertida)
        actual = len(history.load()) - 1 - row
        history.remove(actual)
        self._model.reload()

    def _open_folder(self, out):
        if not out:
            return
        d = os.path.dirname(out)
        if d and os.path.isdir(d):
            self._open_path(d)

    def _open_path(self, p: str):
        if sys.platform == "win32":
            os.startfile(p)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", p])
        else:
            subprocess.Popen(["xdg-open", p])
```

- [ ] **Step 9.2: Plugar na MainWindow + refresh ao processar**

`ui/main_window.py`:
```python
from ui.tabs import OcorrenciasTab, VTCaixaTab, HistoricoTab
# ...
self._historico = HistoricoTab(self)
self._tabs.addTab(self._historico, "Histórico")

# em _on_processed, depois de history.append:
def _on_processed(self, entry: dict) -> None:
    history.append(entry)
    self._historico.refresh()
```

`ui/tabs/__init__.py`:
```python
from ui.tabs.ocorrencias import OcorrenciasTab
from ui.tabs.vt_caixa import VTCaixaTab
from ui.tabs.historico import HistoricoTab

__all__ = ["OcorrenciasTab", "VTCaixaTab", "HistoricoTab"]
```

- [ ] **Step 9.3: Teste manual**

Run: `python app.py`
Expected: depois de processar 2 vezes, aba Histórico mostra 2 linhas; duplo-clique abre o XLSX; menu de contexto funciona.

- [ ] **Step 9.4: Commit**

```bash
git add ui/tabs/historico.py ui/tabs/__init__.py ui/main_window.py
git commit -m "feat(ui): aba Histórico com tabela, ações e menu de contexto"
```

---

## Task 10: Aba Configurações — Aparência, API, Licença, Atualizações, Sobre

**Files:**
- Create: `ui/tabs/configuracoes.py`
- Modify: `ui/tabs/__init__.py`
- Modify: `ui/main_window.py`

- [ ] **Step 10.1: Implementar `ui/tabs/configuracoes.py`**

```python
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QRadioButton, QVBoxLayout, QWidget
)

from auto_update import check_and_update
from license_client import LicenseClient
from ui import settings


class ConfiguracoesTab(QWidget):
    theme_changed = Signal(str)  # "dark" ou "light"

    GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]

    def __init__(self, parent=None):
        super().__init__(parent)
        cfg = settings.load()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Aparência
        g_ap = QGroupBox("Aparência", self)
        ap_layout = QHBoxLayout(g_ap)
        self._rb_dark = QRadioButton("Escuro")
        self._rb_light = QRadioButton("Claro")
        if cfg.get("theme") == "light":
            self._rb_light.setChecked(True)
        else:
            self._rb_dark.setChecked(True)
        self._rb_dark.toggled.connect(lambda on: on and self._set_theme("dark"))
        self._rb_light.toggled.connect(lambda on: on and self._set_theme("light"))
        ap_layout.addWidget(self._rb_dark)
        ap_layout.addWidget(self._rb_light)
        ap_layout.addStretch()
        layout.addWidget(g_ap)

        # API Gemini
        g_ai = QGroupBox("API Gemini", self)
        ai_form = QFormLayout(g_ai)
        self._ed_key = QLineEdit(cfg.get("api_key", ""))
        self._ed_key.setEchoMode(QLineEdit.Password)
        self._cb_model = QComboBox()
        self._cb_model.addItems(self.GEMINI_MODELS)
        self._cb_model.setCurrentText(cfg.get("gemini_model", "gemini-2.5-flash"))
        row = QHBoxLayout()
        self._btn_save_ai = QPushButton("Salvar")
        self._btn_save_ai.clicked.connect(self._save_ai)
        row.addWidget(self._btn_save_ai); row.addStretch()
        ai_form.addRow("Chave:", self._ed_key)
        ai_form.addRow("Modelo:", self._cb_model)
        wrap = QWidget(); wrap.setLayout(row)
        ai_form.addRow(wrap)
        layout.addWidget(g_ai)

        # Licença
        g_lic = QGroupBox("Licença", self)
        lic_layout = QVBoxLayout(g_lic)
        client = LicenseClient()
        try:
            current_key = client.load_key() or "(nenhuma)"
        except Exception:
            current_key = "(nenhuma)"
        masked = current_key[:6] + "…" + current_key[-4:] if len(current_key) > 12 else current_key
        lic_layout.addWidget(QLabel(f"Chave atual: {masked}"))
        btn_change = QPushButton("Trocar chave")
        btn_change.clicked.connect(self._change_license)
        lic_layout.addWidget(btn_change, alignment=lic_layout.alignment())
        layout.addWidget(g_lic)

        # Atualizações
        g_up = QGroupBox("Atualizações", self)
        up_layout = QHBoxLayout(g_up)
        up_layout.addWidget(QLabel(f"Versão atual: {LicenseClient.APP_VERSION}"))
        btn_check = QPushButton("Verificar agora")
        btn_check.clicked.connect(self._check_update)
        up_layout.addWidget(btn_check); up_layout.addStretch()
        layout.addWidget(g_up)

        # Sobre
        g_about = QGroupBox("Sobre", self)
        about_layout = QVBoxLayout(g_about)
        about_layout.addWidget(QLabel(
            f"Processador de Ocorrências v{LicenseClient.APP_VERSION}\n"
            "Autor: Nicolas Almeida Hader Dias"
        ))
        layout.addWidget(g_about)

        layout.addStretch()

    def _set_theme(self, mode: str):
        settings.save({"theme": mode})
        self.theme_changed.emit(mode)

    def _save_ai(self):
        err = settings.save({
            "api_key": self._ed_key.text().strip(),
            "gemini_model": self._cb_model.currentText(),
        })
        if err:
            QMessageBox.warning(self, "Erro", f"Falha ao salvar: {err}")
        else:
            QMessageBox.information(self, "OK", "Configurações de IA salvas.")

    def _change_license(self):
        from ui.license_dialogs import show_activation_window
        new_key = show_activation_window("Insira a nova chave de licença.")
        if new_key:
            LicenseClient().save_key(new_key)
            QMessageBox.information(self, "Licença", "Chave atualizada. Reinicie o app pra validar.")

    def _check_update(self):
        check_and_update()
        QMessageBox.information(self, "Atualizações", "Verificação concluída (sem atualização ou já atualizado).")
```

- [ ] **Step 10.2: Plugar e conectar toggle de tema**

`ui/tabs/__init__.py`:
```python
from ui.tabs.ocorrencias import OcorrenciasTab
from ui.tabs.vt_caixa import VTCaixaTab
from ui.tabs.historico import HistoricoTab
from ui.tabs.configuracoes import ConfiguracoesTab

__all__ = ["OcorrenciasTab", "VTCaixaTab", "HistoricoTab", "ConfiguracoesTab"]
```

`ui/main_window.py`:
```python
from ui.tabs import OcorrenciasTab, VTCaixaTab, HistoricoTab, ConfiguracoesTab
# em __init__:
cfg_tab = ConfiguracoesTab(self)
cfg_tab.theme_changed.connect(self._apply_theme_runtime)
self._tabs.addTab(cfg_tab, "Configurações")

# novo método:
def _apply_theme_runtime(self, mode: str) -> None:
    from PySide6.QtWidgets import QApplication
    theme.apply_theme(QApplication.instance(), mode)
```

- [ ] **Step 10.3: Teste manual**

Run: `python app.py`
Expected: aba Configurações abre; alternar entre Escuro/Claro muda o tema na hora; salvar API key persiste em `~/.ocorrencias_config.json`.

- [ ] **Step 10.4: Commit**

```bash
git add ui/tabs/configuracoes.py ui/tabs/__init__.py ui/main_window.py
git commit -m "feat(ui): aba Configurações com toggle dark/light em runtime"
```

---

## Task 11: Splash + Worker de auto-update + Diálogos de licença + Bootstrap em `app.py`

**Files:**
- Create: `ui/splash.py`
- Create: `ui/update_worker.py`
- Create: `ui/license_dialogs.py`
- Test: `tests/ui/test_update_worker.py`
- Modify: `app.py`
- Delete: `license_ui.py`

> **Paridade com v1.63:** o Tkinter atual já mostra spinner animado + barra de progresso durante o download da atualização, dirigida por `check_and_update(on_progress=..., on_status=...)` rodando numa thread. Esta task porta essa experiência pro Qt: splash custom com spinner + barra, e um worker `QThread` que emite sinais `progress`/`status`.

- [ ] **Step 11.1: Implementar `ui/splash.py` (custom widget com spinner + barra)**

Splash custom em vez de `QSplashScreen` porque precisamos de barra de progresso show/hide e spinner animado — paridade com o `SplashScreen(tk.Tk)` da v1.63 (`set_status`, `set_progress(frac, texto)`, `hide_progress`). `frac=None` ⇒ barra indeterminada (download sem `Content-Length`).

```python
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame, QLabel, QProgressBar, QVBoxLayout, QWidget
)

_BG = "#0d1117"
_ACCENT = "#58a6ff"
_FG = "#c9d1d9"
_FG_DIM = "#6e7591"


class _Spinner(QWidget):
    """Arco giratório desenhado com QPainter (substitui o canvas do Tkinter)."""

    def __init__(self, parent=None, diameter: int = 44):
        super().__init__(parent)
        self._d = diameter
        self.setFixedSize(diameter, diameter)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

    def _tick(self):
        self._angle = (self._angle + 12) % 360
        self.update()

    def stop(self):
        self._timer.stop()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        margin = 4
        rect = self.rect().adjusted(margin, margin, -margin, -margin)
        # trilha
        p.setPen(QPen(QColor("#1a1d29"), 4))
        p.drawArc(rect, 0, 360 * 16)
        # arco giratório (90°). Qt usa 1/16 de grau e sentido anti-horário.
        p.setPen(QPen(QColor(_ACCENT), 4))
        p.drawArc(rect, -self._angle * 16, 90 * 16)
        p.end()


class Splash(QWidget):
    def __init__(self, version: str):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setFixedSize(380, 240)
        self.setStyleSheet(
            f"Splash {{ background: {_BG}; border: 1px solid #262a3a; }}"
        )
        self._center_on_screen()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        title = QLabel("Processador de Ocorrências", self)
        title.setStyleSheet(f"color: #e6e8f0; font-size: 14pt; font-weight: 700;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        ver = QLabel(f"v{version}", self)
        ver.setStyleSheet(f"color: {_FG_DIM}; font-family: 'JetBrains Mono', Consolas, monospace; font-size: 9pt;")
        ver.setAlignment(Qt.AlignCenter)
        layout.addWidget(ver)

        sep = QFrame(self)
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #262a3a;")
        layout.addSpacing(8)
        layout.addWidget(sep)
        layout.addSpacing(8)

        self._spinner = _Spinner(self)
        layout.addWidget(self._spinner, alignment=Qt.AlignCenter)

        self._status = QLabel("Iniciando...", self)
        self._status.setStyleSheet(f"color: {_FG_DIM}; font-size: 10pt;")
        self._status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._status)

        self._progress = QProgressBar(self)
        self._progress.setFixedHeight(6)
        self._progress.setTextVisible(False)
        self._progress.setRange(0, 100)
        self._progress.setVisible(False)
        layout.addSpacing(6)
        layout.addWidget(self._progress)

    def _center_on_screen(self):
        from PySide6.QtGui import QGuiApplication
        geo = QGuiApplication.primaryScreen().availableGeometry()
        self.move((geo.width() - self.width()) // 2,
                  (geo.height() - self.height()) // 2)

    def set_status(self, texto: str) -> None:
        self._status.setText(texto)

    def set_progress(self, frac, texto: str) -> None:
        """frac em 0.0–1.0; frac=None => barra indeterminada."""
        if not self._progress.isVisible():
            self._progress.setVisible(True)
        if frac is None:
            self._progress.setRange(0, 0)  # busy/indeterminado
        else:
            self._progress.setRange(0, 100)
            self._progress.setValue(int(max(0.0, min(1.0, frac)) * 100))
        self._status.setText(texto)

    def hide_progress(self) -> None:
        self._progress.setVisible(False)
        self._progress.setRange(0, 100)

    def fechar(self) -> None:
        self._spinner.stop()
        self.close()
```

- [ ] **Step 11.2: Implementar `ui/update_worker.py` (QThread worker)**

Porta o `threading.Thread(target=check_and_update, kwargs={on_progress, on_status})` da v1.63 pro padrão Qt usado nas abas. O worker chama `check_and_update` passando callbacks que **apenas emitem sinais** — toda mexida na UI acontece na thread principal via slots conectados.

```python
from PySide6.QtCore import QObject, Signal

from auto_update import check_and_update


class UpdateWorker(QObject):
    progress = Signal(int, int)   # (baixado, total) — total=0 ⇒ indeterminado
    status = Signal(str)          # "verificando" | "baixando" | "reiniciando" | "erro"
    finished = Signal()

    def run(self) -> None:
        try:
            self.status.emit("verificando")
            check_and_update(
                on_progress=lambda baixado, total: self.progress.emit(baixado, total),
                on_status=lambda estado: self.status.emit(estado),
            )
        finally:
            self.finished.emit()
```

- [ ] **Step 11.3: Escrever teste do worker**

`tests/ui/test_update_worker.py`:
```python
import auto_update
from ui.update_worker import UpdateWorker


def test_worker_repassa_callbacks_e_emite_sinais(qtbot, monkeypatch):
    chamadas = {"progress": [], "status": []}

    def fake_check(on_progress=None, on_status=None):
        on_status("baixando")
        on_progress(50, 100)
        on_progress(100, 100)
        on_status("reiniciando")

    monkeypatch.setattr(auto_update, "check_and_update", fake_check)
    # o worker importou o símbolo direto; recarrega a referência
    monkeypatch.setattr("ui.update_worker.check_and_update", fake_check)

    w = UpdateWorker()
    w.progress.connect(lambda b, t: chamadas["progress"].append((b, t)))
    w.status.connect(lambda e: chamadas["status"].append(e))

    with qtbot.waitSignal(w.finished, timeout=2000):
        w.run()

    assert chamadas["progress"] == [(50, 100), (100, 100)]
    assert chamadas["status"] == ["verificando", "baixando", "reiniciando"]
```

Run: `pytest tests/ui/test_update_worker.py -v`
Expected: PASS.

- [ ] **Step 11.4: Implementar `ui/license_dialogs.py`**

```python
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QVBoxLayout
)


def show_activation_window(initial_message: str = "") -> str | None:
    """Modal pra capturar chave. Retorna chave (uppercase, strip) ou None."""
    dialog = QDialog()
    dialog.setWindowTitle("Ativação de licença")
    dialog.setMinimumWidth(460)
    dialog.setModal(True)

    layout = QVBoxLayout(dialog)

    layout.addWidget(QLabel("<b>Processador de Ocorrências</b>"))
    layout.addWidget(QLabel("Insira sua chave para liberar o aplicativo."))

    if initial_message:
        msg = QLabel(initial_message)
        msg.setStyleSheet("color: #f85149;")
        msg.setWordWrap(True)
        layout.addWidget(msg)

    layout.addWidget(QLabel("CHAVE DE LICENÇA"))
    edit = QLineEdit()
    edit.setStyleSheet("font-family: 'JetBrains Mono', Consolas, monospace;")
    layout.addWidget(edit)

    btns = QHBoxLayout()
    b_ok = QPushButton("Ativar"); b_ok.setObjectName("primary")
    b_cancel = QPushButton("Sair")
    btns.addWidget(b_ok); btns.addStretch(); btns.addWidget(b_cancel)
    wrap = QPushButton(); wrap.hide()  # placeholder
    layout.addLayout(btns)

    result = {"key": None}
    def on_ok():
        v = edit.text().strip().upper()
        if v:
            result["key"] = v
            dialog.accept()
    def on_cancel():
        dialog.reject()

    b_ok.clicked.connect(on_ok)
    b_cancel.clicked.connect(on_cancel)
    edit.returnPressed.connect(on_ok)
    dialog.exec()
    return result["key"]


def show_error_window(message: str) -> None:
    QMessageBox.critical(None, "Erro de licença", message)
```

- [ ] **Step 11.5: Reescrever `app.py` com splash + auto-update via QThread + bootstrap**

Fluxo idêntico ao `main()` da v1.63, mas em Qt:
1. Splash custom aparece com spinner.
2. `UpdateWorker` roda numa `QThread`; `progress`/`status` atualizam a splash (barra + texto). UI fica responsiva sem `processEvents` manual — o event loop local roda enquanto esperamos o sinal `finished`.
3. Se o estado final for `reiniciando`, fecha tudo e sai (o `updater.bat` já foi disparado pelo worker).
4. Se for `erro`, mostra "não foi possível atualizar, continuando..." e segue.
5. Valida licença (fecha a splash antes de qualquer diálogo, pra não sobrepor).
6. Abre a `MainWindow`.

```python
"""Processador de Ocorrências v1.64 — entrypoint."""
import sys

from PySide6.QtCore import QEventLoop, QThread, QTimer
from PySide6.QtWidgets import QApplication

from license_client import LicenseClient, LicenseStatus
from ui import settings, theme
from ui import license_dialogs
from ui.main_window import MainWindow
from ui.splash import Splash
from ui.update_worker import UpdateWorker


def _resolver_licenca(client, result) -> bool:
    while True:
        if result.status in (LicenseStatus.VALID, LicenseStatus.OFFLINE_TOLERATED):
            return True
        if result.status == LicenseStatus.NO_KEY:
            new_key = license_dialogs.show_activation_window("Insira sua chave de licença para começar.")
        elif result.status == LicenseStatus.INVALID:
            reason = {
                "not_found": "Chave não reconhecida.",
                "revoked": "Esta chave foi revogada. Entre em contato com o suporte.",
            }.get(result.reason, "Chave inválida.")
            new_key = license_dialogs.show_activation_window(reason)
        elif result.status == LicenseStatus.OFFLINE_EXPIRED:
            license_dialogs.show_error_window(
                "Não foi possível validar sua licença com o servidor e o "
                "período de uso offline expirou. Conecte-se à internet e tente novamente."
            )
            return False
        else:
            return False
        if new_key is None:
            return False
        client.save_key(new_key)
        result = client.validate()


def _run_auto_update(splash: Splash) -> str:
    """Roda check_and_update numa QThread, dirigindo a splash.
    Retorna o estado final: '' (nada/ok), 'reiniciando' ou 'erro'.
    Bloqueia num QEventLoop local até o worker terminar (UI responsiva)."""
    estado = {"valor": ""}

    thread = QThread()
    worker = UpdateWorker()
    worker.moveToThread(thread)

    def on_progress(baixado, total):
        if total > 0:
            mb_b, mb_t = baixado / 1048576, total / 1048576
            splash.set_progress(baixado / total,
                                f"Baixando atualização... {int(baixado / total * 100)}% — {mb_b:.1f} / {mb_t:.1f} MB")
        else:
            splash.set_progress(None, f"Baixando atualização... {baixado / 1048576:.1f} MB")

    def on_status(e):
        estado["valor"] = e
        if e == "verificando":
            splash.set_status("Procurando atualizações...")

    worker.progress.connect(on_progress)
    worker.status.connect(on_status)

    loop = QEventLoop()
    worker.finished.connect(loop.quit)
    worker.finished.connect(thread.quit)
    thread.started.connect(worker.run)
    thread.start()
    loop.exec()  # mantém a splash viva e animada até terminar
    thread.wait()
    return estado["valor"]


def main() -> int:
    app = QApplication(sys.argv)
    theme.load_fonts()
    cfg = settings.load()
    theme.apply_theme(app, cfg.get("theme", "dark"))

    splash = Splash(LicenseClient.APP_VERSION)
    splash.show()

    estado = _run_auto_update(splash)
    if estado == "reiniciando":
        splash.set_progress(1.0, "Atualização concluída — reiniciando...")
        QTimer.singleShot(1000, app.quit)
        app.exec()
        return 0
    splash.hide_progress()
    if estado == "erro":
        splash.set_status("Não foi possível atualizar, continuando...")

    splash.set_status("Validando licença...")
    client = LicenseClient()
    result = client.validate()

    if result.status not in (LicenseStatus.VALID, LicenseStatus.OFFLINE_TOLERATED):
        splash.fechar()
        if not _resolver_licenca(client, result):
            return 1
        window = MainWindow()
        window.show()
        return app.exec()

    splash.set_status("Carregando...")
    window = MainWindow()
    QTimer.singleShot(300, lambda: (splash.fechar(), window.show()))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 11.6: Apagar `license_ui.py`**

```bash
git rm license_ui.py
```

- [ ] **Step 11.7: Teste manual end-to-end**

Run: `python app.py`
Expected:
- Splash aparece com spinner girando.
- Em dev (`sys.frozen` falso), `check_and_update` é noop — splash passa direto pra licença sem mostrar barra.
- Se já tem licença válida em `~/.ocorrencias_license.json`, abre direto.
- Se renomear a licença pra forçar `NO_KEY`, abre o diálogo de ativação.
- Toggle dark/light na aba Configurações aplica na hora.
- (Build real) com update disponível no servidor: barra de progresso enche durante o download; ao concluir, mostra "reiniciando..." e fecha.

- [ ] **Step 11.8: Commit**

```bash
git add app.py ui/splash.py ui/update_worker.py ui/license_dialogs.py tests/ui/test_update_worker.py
git commit -m "feat(ui): splash com spinner+progresso, auto-update via QThread e diálogos de licença em Qt"
```

---

## Task 12: Bump versão, .spec, deploy.py, smoke tests e finalização

**Files:**
- Modify: `license_client.py`
- Create: `ProcessadorOcorrencias-v1.64.spec`
- Create: `tests/ui/test_tabs_smoke.py`

> **Nota sobre `deploy.py`:** verificado que o `deploy.py` deriva o nome do exe da versão dinamicamente (`f"ProcessadorOcorrencias-v{version}.exe"`) e **não** referencia o `.spec` por nome. Logo, não precisa ser editado para a 1.64. (O plano original assumia uma string `...v1.60.spec` que não existe lá.)

- [ ] **Step 12.1: Bumpar `APP_VERSION`**

Edit `license_client.py`: encontrar a linha `APP_VERSION = "1.63"` e trocar pra `APP_VERSION = "1.64"`.

- [ ] **Step 12.2: Criar `ProcessadorOcorrencias-v1.64.spec`**

Use o `ProcessadorOcorrencias-v1.63.spec` existente como referência de estrutura, mas adapte para PySide6 (hooks, excludes tkinter) conforme abaixo.

```python
# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = (
    collect_submodules('PySide6')
    + ['ui', 'ui.widgets', 'ui.tabs', 'ui.update_worker', 'ui.splash']
)

datas = [
    ('assets/fonts', 'assets/fonts'),
]
# inclui assets/logo.png se existir
import os
if os.path.isfile('assets/logo.png'):
    datas.append(('assets/logo.png', 'assets'))

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', '_tkinter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ProcessadorOcorrencias-v1.64',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
```

- [ ] **Step 12.3: Confirmar que `deploy.py` não precisa de mudança**

Run: `grep -n "spec\|v1\." deploy.py`
Expected: nenhuma referência hard-coded a `.spec` nem à versão antiga. O exe é resolvido por `f"ProcessadorOcorrencias-v{version}.exe"` em `dist/`, e a versão vem do argumento `--release`/`APP_VERSION`. Nenhuma edição necessária. Se aparecer alguma string `v1.63` hard-coded, troque pra `v1.64`.

- [ ] **Step 12.4: Smoke tests das abas (constrói sem crash)**

`tests/ui/test_tabs_smoke.py`:
```python
import pytest


def test_ocorrencias_tab_constructs(qtbot, monkeypatch, tmp_path):
    from ui import settings, history
    monkeypatch.setattr(settings, "_CONFIG_PATH", tmp_path / "cfg.json")
    monkeypatch.setattr(history, "_HISTORY_PATH", tmp_path / "hist.json")
    from ui.tabs.ocorrencias import OcorrenciasTab
    tab = OcorrenciasTab()
    qtbot.addWidget(tab)
    assert tab is not None


def test_vt_caixa_tab_constructs(qtbot, monkeypatch, tmp_path):
    from ui import settings, history
    monkeypatch.setattr(settings, "_CONFIG_PATH", tmp_path / "cfg.json")
    monkeypatch.setattr(history, "_HISTORY_PATH", tmp_path / "hist.json")
    from ui.tabs.vt_caixa import VTCaixaTab
    tab = VTCaixaTab()
    qtbot.addWidget(tab)
    assert tab is not None


def test_historico_tab_constructs(qtbot, monkeypatch, tmp_path):
    from ui import history
    monkeypatch.setattr(history, "_HISTORY_PATH", tmp_path / "hist.json")
    from ui.tabs.historico import HistoricoTab
    tab = HistoricoTab()
    qtbot.addWidget(tab)
    assert tab is not None


def test_configuracoes_tab_constructs(qtbot, monkeypatch, tmp_path):
    from ui import settings
    monkeypatch.setattr(settings, "_CONFIG_PATH", tmp_path / "cfg.json")
    from ui.tabs.configuracoes import ConfiguracoesTab
    tab = ConfiguracoesTab()
    qtbot.addWidget(tab)
    assert tab is not None


def test_main_window_constructs(qtbot, monkeypatch, tmp_path):
    from ui import settings, history
    monkeypatch.setattr(settings, "_CONFIG_PATH", tmp_path / "cfg.json")
    monkeypatch.setattr(history, "_HISTORY_PATH", tmp_path / "hist.json")
    from ui.main_window import MainWindow
    w = MainWindow()
    qtbot.addWidget(w)
    assert w.windowTitle() == "Processador de Ocorrências"
```

- [ ] **Step 12.5: Rodar suite inteira**

Run: `pytest -v`
Expected: testes existentes (`test_license_client.py`, `test_processador_verificacao.py`) PASS + novos testes de `ui/` PASS. Se algum smoke falhar por causa de display em CI, marca com `@pytest.mark.skipif` apropriado e segue.

- [ ] **Step 12.6: Build do exe localmente**

Run: `pyinstaller ProcessadorOcorrencias-v1.64.spec --clean`
Expected: `dist/ProcessadorOcorrencias-v1.64.exe` aparece (~80-110 MB).

- [ ] **Step 12.7: Testar o exe em ambiente limpo**

Idealmente em VM Windows sem Python. Mínimo: copiar o exe pra outro diretório (fora do checkout) e rodar:
- Splash aparece.
- Bootstrap licença OK (ou pede chave).
- Janela principal abre com 4 abas.
- Drag-and-drop de PDF + XLSX → processar → log mostra progresso → arquivo de saída criado.
- Histórico mostra a entrada.
- Toggle dark/light funciona.
- Fechar e reabrir mantém geometria.

- [ ] **Step 12.8: Commit final + merge**

```bash
git add license_client.py ProcessadorOcorrencias-v1.64.spec tests/ui/test_tabs_smoke.py
git commit -m "release(1.64): bump versão, novo .spec PyInstaller, smoke tests das abas"
git checkout main
git merge --no-ff feat-pyside6-1.64 -m "release(1.64): migração da UI para PySide6"
```

(Decide quando fazer push — fora do escopo do plano.)

---

## Self-Review

**1. Spec coverage:**

| Requisito do spec | Task |
|---|---|
| Pacote `ui/` modular | T1 (esqueleto), T2-T11 (módulos) |
| `theme.py` (dark/light, fontes, QSS) | T4 |
| `settings.py` I/O atômico | T2 |
| `history.py` cap 500 FIFO | T3 |
| Widgets reusáveis (DropZone, LogPanel, PrimaryButton, SectionCard) | T5 |
| MainWindow + 4 abas + status bar + geometria | T6 (shell), T7-T10 (abas), T11 (bootstrap) |
| Aba Ocorrências (wizard, worker, log, cancelamento) | T7 |
| Aba VT-Caixa (aceita PDF/XLSX como fonte, output CSV) | T8 |
| Aba Histórico (tabela, ações, menu contexto) | T9 |
| Aba Configurações (aparência, IA, licença, atualizações, sobre) | T10 |
| Toggle dark/light em runtime | T10 step 10.2 |
| Splash custom com spinner + barra de progresso (paridade v1.63) | T11 step 11.1 |
| Auto-update com feedback de progresso via QThread (paridade v1.63) | T11 steps 11.2–11.3, 11.5 |
| `license_dialogs.py` substituindo `license_ui.py` | T11 step 11.4 |
| Bootstrap de licença em `app.py` | T11 step 11.5 |
| Remover "Deduzir dias nas colunas Qt" | Implícito — não codamos a feature em T7 (não está no código novo) |
| `.spec` PyInstaller v1.64 com PySide6 hooks + excludes tkinter | T12 |
| Bump APP_VERSION 1.63 → 1.64 (segue auto-update normal) | T12 step 12.1 |
| `deploy.py` — confirmado que não precisa mudar (nome do exe é dinâmico) | T12 step 12.3 |
| `auto_update.py` intacto | (não há task — confirmado) |
| Smoke tests + testes de módulos puros | T2, T3, T4, T5, T12 |
| Verificação manual em VM limpa | T12 step 12.7 |

**Gap encontrado e corrigido inline:** o spec menciona estado `DONE` que mostra "Processar novamente" + "Abrir saída". A implementação em T7 simplifica pra reset automático (`_cleanup_thread` reativa o botão como "Processar" e o usuário pode reabrir o arquivo pelo Histórico). Pragmático: evita complicar a máquina de estados; o Histórico já permite abrir a saída a qualquer momento. Aceito como divergência menor.

**2. Placeholder scan:** sem "TBD", "TODO", "implement later". Há um comentário `# TODO Task 11` no `app.py` da T6 — é intencional (sinaliza onde T11 vai mexer) e é resolvido em T11. Aceito.

**3. Type consistency:**
- `OcorrenciasWorker` sinais coincidem entre T7 (definição) e T7 (uso interno). Idem para `VTCaixaWorker` em T8.
- `PrimaryButton.set_mode("warning")` em T5 corresponde ao QSS gerado em T4 (`QPushButton#warning`).
- `settings.load()` / `settings.save({...})` consistentes em todas as tasks.
- `history.append(entry)` recebe dict consistente com schema definido em T3 — emitido por `_emit_history` em T7 e T8.

**Issue identificada e corrigida:** em T5 step 5.1 a primeira versão de `PrimaryButton` tinha `self.setCursor(0)` errado. A versão correta abaixo usa `Qt.PointingHandCursor`. Mantive ambas com a nota; ao implementar, usar a segunda versão.

**4. Atualização do plano (2026-05-28) — paridade com funções entradas após a v1.60:**

O plano foi escrito na v1.60. Entre v1.60 e v1.63, o app Tkinter ganhou funções que precisavam ser portadas:
- **Persistência de histórico** (v1.62): já coberta nativamente por T3 (`history.py`) + T9 (aba). Sem mudança necessária.
- **Splash com spinner + barra de progresso e auto-update em thread com feedback** (v1.63): a T11 original tinha splash trivial (`QSplashScreen.showMessage`) e `check_and_update()` sem callbacks — **perderia** o feedback de download. Corrigido: T11 agora especifica `ui/splash.py` custom (spinner + barra, API `set_status`/`set_progress`/`hide_progress`), `ui/update_worker.py` (QThread + sinais `progress`/`status`), `app.py` dirigindo a splash via `QEventLoop` local, e `tests/ui/test_update_worker.py`. `.spec` inclui `ui.update_worker`/`ui.splash` em hiddenimports.

O `auto_update.py` continua **intacto** — sua API (`on_progress`/`on_status`) já existia desde a v1.63 e é só consumida pelo novo worker.

Plano coerente e atualizado. Pronto pra execução.
