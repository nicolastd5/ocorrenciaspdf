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
