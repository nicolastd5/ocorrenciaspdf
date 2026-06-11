from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout


class KpiTile(QFrame):
    """Tile de métrica: número grande em mono + rótulo + sub-rótulo opcional.

    `accent` colore o número via QSS (propriedade dinâmica, acompanha o tema):
    None (padrão), 'ok' (verde), 'warn' (âmbar), 'accent' (azul).
    `clickable=True` habilita o sinal `clicked` (cursor de mão).
    """

    clicked = Signal()

    _ACCENTS = ("ok", "warn", "accent")

    def __init__(self, label: str, value: str = "—", sub: str = "", accent=None,
                 clickable: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("kpi")
        self._clickable = clickable
        if clickable:
            self.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(13, 12, 13, 12)
        lay.setSpacing(6)

        self._lbl = QLabel(label, self)
        self._lbl.setObjectName("kpiLabel")
        lay.addWidget(self._lbl)

        self._num = QLabel(value, self)
        self._num.setObjectName("kpiNum")
        if accent in self._ACCENTS:
            self._num.setProperty("accent", accent)
        lay.addWidget(self._num)

        self._sub = QLabel(sub, self)
        self._sub.setObjectName("kpiSub")
        self._sub.setVisible(bool(sub))
        lay.addWidget(self._sub)

    def set_value(self, value: str, sub: str = None) -> None:
        self._num.setText(value)
        if sub is not None:
            self._sub.setText(sub)
            self._sub.setVisible(bool(sub))

    def mousePressEvent(self, ev):
        if self._clickable and ev.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(ev)


class KpiStrip(QFrame):
    """Linha horizontal de KpiTiles igualmente distribuídos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(12)

    def add(self, tile: KpiTile) -> None:
        self._lay.addWidget(tile, stretch=1)
