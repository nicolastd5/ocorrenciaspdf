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
