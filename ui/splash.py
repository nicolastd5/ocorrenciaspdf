from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QLabel, QProgressBar, QVBoxLayout, QWidget

_BG = "#0d1117"
_ACCENT = "#58a6ff"
_FG_DIM = "#6e7591"


class _Spinner(QWidget):
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
        rect = self.rect().adjusted(4, 4, -4, -4)
        p.setPen(QPen(QColor("#1a1d29"), 4))
        p.drawArc(rect, 0, 360 * 16)
        p.setPen(QPen(QColor(_ACCENT), 4))
        p.drawArc(rect, -self._angle * 16, 90 * 16)
        p.end()


class Splash(QWidget):
    def __init__(self, version: str):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setFixedSize(380, 240)
        self.setStyleSheet(f"Splash {{ background: {_BG}; border: 1px solid #262a3a; }}")
        self._center_on_screen()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        title = QLabel("Processador de Ocorrências", self)
        title.setStyleSheet("color: #e6e8f0; font-size: 14pt; font-weight: 700;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        ver = QLabel(f"v{version}", self)
        ver.setStyleSheet(f"color: {_FG_DIM}; font-family: 'JetBrains Mono', Consolas, monospace; font-size: 9pt;")
        ver.setAlignment(Qt.AlignCenter)
        layout.addWidget(ver)

        sep = QFrame(self)
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #262a3a;")
        layout.addSpacing(8); layout.addWidget(sep); layout.addSpacing(8)

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
        layout.addSpacing(6); layout.addWidget(self._progress)

    def _center_on_screen(self):
        from PySide6.QtGui import QGuiApplication
        geo = QGuiApplication.primaryScreen().availableGeometry()
        self.move((geo.width() - self.width()) // 2, (geo.height() - self.height()) // 2)

    def set_status(self, texto: str) -> None:
        self._status.setText(texto)

    def set_progress(self, frac, texto: str) -> None:
        if not self._progress.isVisible():
            self._progress.setVisible(True)
        if frac is None:
            self._progress.setRange(0, 0)
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
