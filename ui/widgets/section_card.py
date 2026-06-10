from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class SectionCard(QFrame):
    """Card numerado do wizard.

    Cabeçalho com badge de passo (vira ✓ verde quando concluído) + título;
    corpo abaixo. Ex.: passo 1 · 'PDF de jornada'.
    """

    def __init__(self, number: int, title: str, parent=None, optional: bool = False):
        super().__init__(parent)
        self.setObjectName("card")
        self._number = number

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        head = QFrame(self)
        head.setObjectName("cardHead")
        head_lay = QHBoxLayout(head)
        head_lay.setContentsMargins(14, 10, 14, 10)
        head_lay.setSpacing(11)

        self._step = QLabel(str(number), head)
        self._step.setObjectName("step")
        self._step.setAlignment(Qt.AlignCenter)
        head_lay.addWidget(self._step)

        title_lbl = QLabel(title, head)
        title_lbl.setObjectName("cardTitle")
        head_lay.addWidget(title_lbl)
        head_lay.addStretch()

        if optional:
            opt = QLabel("opcional", head)
            opt.setObjectName("cardOpt")
            head_lay.addWidget(opt)

        outer.addWidget(head)

        self._body = QWidget(self)
        self._body.setObjectName("cardBody")
        self._layout = QVBoxLayout(self._body)
        self._layout.setContentsMargins(14, 14, 14, 14)
        self._layout.setSpacing(11)
        outer.addWidget(self._body)

    def add(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)

    def set_done(self, done: bool) -> None:
        """Marca o passo como concluído (badge verde ✓) ou pendente (número)."""
        if done:
            self._step.setObjectName("stepDone")
            self._step.setText("✓")  # ✓
        else:
            self._step.setObjectName("step")
            self._step.setText(str(self._number))
        self._step.style().unpolish(self._step)
        self._step.style().polish(self._step)
