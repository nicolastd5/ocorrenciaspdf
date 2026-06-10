from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class Panel(QFrame):
    """Painel da coluna direita: cabeçalho com título + corpo com conteúdo.

    Usado para o painel de 'Execução' (resumo + log) nas telas de processamento.
    """

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        head = QFrame(self)
        head.setObjectName("panelHead")
        head_lay = QHBoxLayout(head)
        head_lay.setContentsMargins(14, 11, 14, 11)
        self._title = QLabel(title, head)
        self._title.setObjectName("panelTitle")
        head_lay.addWidget(self._title)
        head_lay.addStretch()
        self._head_lay = head_lay
        outer.addWidget(head)

        self._body = QWidget(self)
        self._body.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._body)
        self._layout.setContentsMargins(14, 14, 14, 14)
        self._layout.setSpacing(12)
        outer.addWidget(self._body, stretch=1)

    def add(self, widget: QWidget, stretch: int = 0) -> None:
        self._layout.addWidget(widget, stretch=stretch)

    def add_header_widget(self, widget: QWidget) -> None:
        self._head_lay.addWidget(widget)

    def set_title(self, title: str) -> None:
        self._title.setText(title)
