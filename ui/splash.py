"""Splash de inicialização — janela translúcida com cartão arredondado,
selo do app com anel girante em gradiente e barra de progresso.

Mantém a API usada pelo app.py: set_status, set_progress, hide_progress, fechar.
"""
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QRectF, QTimer
from PySide6.QtGui import (
    QBrush, QColor, QConicalGradient, QFont, QLinearGradient, QPainter, QPen
)
from PySide6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QProgressBar,
    QVBoxLayout, QWidget
)

# Cores próprias do splash (momento de marca — independe do tema claro/escuro)
_FG = "#f0f6fc"
_FG_DIM = "#8b95a7"
_BORDER = "#273450"
_BLUE = "#1f6feb"
_ACCENT = "#58a6ff"
_GREEN = "#3fb950"


class _LogoSpinner(QWidget):
    """Selo do app (badge em gradiente) com anel girante ao redor."""

    def __init__(self, parent=None, size: int = 96):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)  # ~60 fps

    def _tick(self):
        self._angle = (self._angle + 3.0) % 360
        self.update()

    def stop(self):
        self._timer.stop()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        ring = QRectF(self.rect()).adjusted(5, 5, -5, -5)

        # trilho discreto do anel
        p.setPen(QPen(QColor(255, 255, 255, 20), 3))
        p.drawEllipse(ring)

        # arco girante com gradiente cônico (azul → verde → some)
        grad = QConicalGradient(ring.center(), -self._angle)
        grad.setColorAt(0.00, QColor(_ACCENT))
        grad.setColorAt(0.45, QColor(_GREEN))
        grad.setColorAt(0.80, QColor(88, 166, 255, 0))
        grad.setColorAt(1.00, QColor(_ACCENT))
        pen = QPen(QBrush(grad), 3.5)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(ring, int(-self._angle * 16), 300 * 16)

        # badge central em gradiente com o glyph do app
        badge = ring.adjusted(17, 17, -17, -17)
        bg = QLinearGradient(badge.topLeft(), badge.bottomRight())
        bg.setColorAt(0.0, QColor(_BLUE))
        bg.setColorAt(1.0, QColor("#238636"))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(bg))
        p.drawRoundedRect(badge, 14, 14)

        p.setPen(QColor("white"))
        f = QFont(self.font())
        f.setPointSize(18)
        f.setBold(True)
        p.setFont(f)
        p.drawText(badge, Qt.AlignCenter, "▣")
        p.end()


class Splash(QWidget):
    def __init__(self, version: str):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(460, 350)
        self._center_on_screen()
        self._anim = None
        self._shown_once = False
        self._closing = False
        self.setWindowOpacity(0.0)  # entra com fade-in no primeiro show

        # margem externa dá espaço para a sombra do cartão
        outer = QVBoxLayout(self)
        outer.setContentsMargins(26, 26, 26, 26)

        card = QFrame(self)
        card.setObjectName("splashCard")
        card.setStyleSheet(f"""
            QFrame#splashCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0e1626, stop:0.5 #0d1117, stop:1 #11203a);
                border: 1px solid {_BORDER};
                border-radius: 18px;
            }}
            QFrame#splashCard QLabel {{ background: transparent; border: none; }}
            QProgressBar {{
                background: rgba(255,255,255,0.07);
                border: none; border-radius: 3px;
            }}
            QProgressBar::chunk {{
                border-radius: 3px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {_BLUE}, stop:1 {_GREEN});
            }}
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(38)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 170))
        card.setGraphicsEffect(shadow)
        outer.addWidget(card)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(30, 28, 30, 22)
        lay.setSpacing(0)

        self._spinner = _LogoSpinner(card)
        lay.addWidget(self._spinner, alignment=Qt.AlignHCenter)
        lay.addSpacing(16)

        title = QLabel("Processador de Ocorrências", card)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color: {_FG}; font-size: 14.5pt; font-weight: 700;")
        lay.addWidget(title)
        lay.addSpacing(8)

        # pill de versão
        pill_row = QHBoxLayout()
        pill_row.addStretch()
        ver = QLabel(f"v{version}", card)
        ver.setStyleSheet(
            f"color: {_FG_DIM}; border: 1px solid {_BORDER}; border-radius: 9px;"
            f"padding: 1px 10px; font-size: 8.5pt;"
            f"font-family: 'JetBrains Mono', Consolas, monospace;"
        )
        pill_row.addWidget(ver)
        pill_row.addStretch()
        lay.addLayout(pill_row)

        lay.addStretch()

        self._status = QLabel("Iniciando...", card)
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setStyleSheet(f"color: {_FG_DIM}; font-size: 9.5pt;")
        lay.addWidget(self._status)
        lay.addSpacing(10)

        self._progress = QProgressBar(card)
        self._progress.setFixedHeight(6)
        self._progress.setTextVisible(False)
        self._progress.setRange(0, 100)
        self._progress.setVisible(False)
        lay.addWidget(self._progress)

    def _center_on_screen(self):
        from PySide6.QtGui import QGuiApplication
        geo = QGuiApplication.primaryScreen().availableGeometry()
        self.move(geo.left() + (geo.width() - self.width()) // 2,
                  geo.top() + (geo.height() - self.height()) // 2)

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

    # ---------- fade in/out ----------
    def _fade(self, end: float, ms: int, on_done=None) -> None:
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(ms)
        anim.setStartValue(self.windowOpacity())
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.InOutQuad)
        if on_done:
            anim.finished.connect(on_done)
        self._anim = anim  # referência mantém a animação viva até o fim
        anim.start()

    def showEvent(self, ev):
        super().showEvent(ev)
        if not self._shown_once:
            self._shown_once = True
            self._fade(1.0, 220)

    def fechar(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._fade(0.0, 200, on_done=self._finalizar)

    def _finalizar(self) -> None:
        self._spinner.stop()
        self.close()
