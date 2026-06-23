from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton


class PrimaryButton(QPushButton):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setObjectName("primary")
        self.setProperty("mode", "primary")
        self.setCursor(Qt.PointingHandCursor)

    def set_mode(self, mode: str) -> None:
        # Propriedade dinâmica em vez de trocar objectName: o Qt reavalia
        # seletores de atributo no unpolish/polish, mas NÃO re-casa regras
        # de #objectName mudadas em runtime — por isso o "Cancelar" não
        # ficava vermelho antes. objectName fica fixo em "primary".
        self.setProperty("mode", mode)
        self.style().unpolish(self)
        self.style().polish(self)
