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
