import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QStackedWidget,
    QVBoxLayout, QWidget
)


def _fmt_size(path: str) -> str:
    try:
        n = os.path.getsize(path)
    except OSError:
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return ""


class DropZone(QFrame):
    """Área que aceita arquivos por drag ou clique.

    Estado vazio: ícone + texto + dica (mono). Estado selecionado: 'chip' com
    nome do arquivo, tamanho e botão remover. Emite `files_selected` ao escolher
    e `removed` ao limpar.

    accept_extensions: tupla de extensões permitidas (com ponto, lowercase).
    multi: se True, files_selected emite uma lista a cada drop (não substitui).
    """

    files_selected = Signal(list)  # list[str] de paths
    removed = Signal()

    def __init__(self, label: str, accept_extensions: tuple, multi: bool = False, parent=None):
        super().__init__(parent)
        self._exts = tuple(e.lower() for e in accept_extensions)
        self._multi = multi
        self._label_text = label
        self.setAcceptDrops(True)
        self.setObjectName("dropzone")
        self.setMinimumHeight(128)
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("dragActive", False)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self._stack = QStackedWidget(self)
        self._stack.setStyleSheet("background: transparent;")
        root.addWidget(self._stack)

        # ---- página 0: vazio ----
        empty = QWidget(self)
        empty.setStyleSheet("background: transparent;")
        e_lay = QVBoxLayout(empty)
        e_lay.setAlignment(Qt.AlignCenter)
        e_lay.setSpacing(8)
        self._icon = QLabel("⬓", empty)
        self._icon.setObjectName("dropIcon")
        self._icon.setAlignment(Qt.AlignCenter)
        e_lay.addWidget(self._icon)
        self._lbl = QLabel(label, empty)
        self._lbl.setObjectName("dropLabel")
        self._lbl.setAlignment(Qt.AlignCenter)
        e_lay.addWidget(self._lbl)
        hint = QLabel("ou clique para selecionar", empty)
        hint.setObjectName("dropHint")
        hint.setAlignment(Qt.AlignCenter)
        e_lay.addWidget(hint)
        self._stack.addWidget(empty)

        # ---- página 1: chip de arquivo ----
        chip = QWidget(self)
        chip.setStyleSheet("background: transparent;")
        c_lay = QHBoxLayout(chip)
        c_lay.setContentsMargins(12, 12, 12, 12)
        c_lay.setSpacing(12)
        c_icon = QLabel("✓", chip)
        c_icon.setObjectName("chipIcon")
        c_icon.setFixedSize(36, 36)
        c_icon.setAlignment(Qt.AlignCenter)
        c_lay.addWidget(c_icon)
        info = QVBoxLayout(); info.setSpacing(2)
        self._chip_name = QLabel("", chip)
        self._chip_name.setObjectName("chipName")
        self._chip_meta = QLabel("", chip)
        self._chip_meta.setObjectName("chipMeta")
        info.addWidget(self._chip_name); info.addWidget(self._chip_meta)
        c_lay.addLayout(info)
        c_lay.addStretch()
        self._btn_x = QPushButton("✕", chip)
        self._btn_x.setObjectName("ghost")
        self._btn_x.setFixedSize(30, 30)
        self._btn_x.setCursor(Qt.PointingHandCursor)
        self._btn_x.clicked.connect(self._on_remove)
        c_lay.addWidget(self._btn_x)
        self._stack.addWidget(chip)

    # ---------- estilo ----------
    def _apply_style(self, active: bool) -> None:
        # Estilo vem do QSS global via propriedade dinâmica — re-polish aplica.
        self.setProperty("dragActive", active)
        self.style().unpolish(self)
        self.style().polish(self)

    # ---------- API ----------
    def show_file(self, path: str) -> None:
        self._chip_name.setText(os.path.basename(path))
        size = _fmt_size(path)
        ext = Path(path).suffix.lstrip(".").upper()
        meta = " · ".join(x for x in (ext, size) if x)
        self._chip_meta.setText(meta)
        self._stack.setCurrentIndex(1)
        self.setCursor(Qt.ArrowCursor)

    def reset(self) -> None:
        self._stack.setCurrentIndex(0)
        self._lbl.setText(self._label_text)
        self.setCursor(Qt.PointingHandCursor)

    def _on_remove(self) -> None:
        self.reset()
        self.removed.emit()

    # ---------- eventos ----------
    def mousePressEvent(self, ev):
        if self._stack.currentIndex() == 1:
            return  # já tem arquivo: usar o botão remover
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
        # Aceita também quando já há arquivo: o drop substitui a seleção.
        if self._has_acceptable_files(ev):
            ev.acceptProposedAction()
            self._apply_style(active=True)
        else:
            ev.ignore()

    def dragLeaveEvent(self, ev):
        self._apply_style(active=False)

    def dropEvent(self, ev: QDropEvent):
        paths = []
        for url in ev.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.suffix.lower() in self._exts and p.is_file():
                paths.append(str(p))
        self._apply_style(active=False)
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

    # ---------- compat com chamadas antigas ----------
    def set_label(self, text: str) -> None:
        self._lbl.setText(text)

    def reset_label(self) -> None:
        self._lbl.setText(self._label_text)
