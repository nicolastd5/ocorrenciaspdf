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
        prefix = {"info": "  ", "error": "X ", "success": "OK ", "warning": "! "}.get(level, "  ")
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

    def text(self) -> str:
        return self._log.toPlainText()
