from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QVBoxLayout, QWidget
)


class LogPanel(QWidget):
    """Painel com QPlainTextEdit mono + QProgressBar (escondida por padrão)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        # Barra acima do log: fica visível mesmo com o log rolando/extenso.
        # O percentual vai num label próprio ao lado — dentro da barra fina
        # ele ficava achatado/cortado.
        self._progress_row = QWidget(self)
        self._progress_row.setVisible(False)
        row = QHBoxLayout(self._progress_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self._progress = QProgressBar(self._progress_row)
        self._progress.setRange(0, 100)
        self._progress.setTextVisible(False)
        row.addWidget(self._progress, stretch=1)
        self._pct = QLabel("0%", self._progress_row)
        self._pct.setObjectName("progressPct")
        self._pct.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        self._pct.setMinimumWidth(38)
        row.addWidget(self._pct)
        layout.addWidget(self._progress_row)
        self._log = QPlainTextEdit(self)
        self._log.setReadOnly(True)
        self._log.setObjectName("log")
        # Quebra em qualquer ponto: caminhos/arquivos longos não somem na borda.
        self._log.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        layout.addWidget(self._log)

    def append(self, msg: str, level: str = "info") -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        prefix = {"info": "  ", "error": "X ", "success": "OK ", "warning": "! "}.get(level, "  ")
        self._log.appendPlainText(f"[{stamp}] {prefix}{msg}")
        bar = self._log.verticalScrollBar()
        bar.setValue(bar.maximum())

    def set_progress(self, pct: int, visible: bool = True) -> None:
        pct = max(0, min(100, pct))
        self._progress_row.setVisible(visible)
        self._progress.setValue(pct)
        self._pct.setText(f"{pct}%")

    def clear(self) -> None:
        self._log.clear()
        self._progress_row.setVisible(False)
        self._progress.setValue(0)
        self._pct.setText("0%")

    def text(self) -> str:
        return self._log.toPlainText()
