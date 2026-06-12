from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
)

from ui import icons


class _NavItem(QPushButton):
    """Item de navegação da sidebar (checkable, com badge de contagem opcional)."""

    def __init__(self, label: str, icon_name: str, parent=None):
        super().__init__(parent)
        self.setObjectName("navItem")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)
        self.setMinimumHeight(38)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(11)

        self._glyph = icons.IconLabel(icon_name, "fg_dim", 17, self)
        self._glyph.setFixedSize(20, 20)
        self._glyph.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._glyph)

        self._lbl = QLabel(label, self)
        self._lbl.setObjectName("navLabel")
        lay.addWidget(self._lbl)
        lay.addStretch()

        self._count = QLabel("", self)
        self._count.setObjectName("navCount")
        self._count.setVisible(False)
        lay.addWidget(self._count)

    def setChecked(self, checked: bool) -> None:
        super().setChecked(checked)
        # ícone acompanha o estado: acento quando ativo, discreto quando não
        self._glyph.set_icon(self._glyph._name, "accent" if checked else "fg_dim")

    def set_count(self, n: int) -> None:
        if n > 0:
            self._count.setText(str(n))
            self._count.setVisible(True)
        else:
            self._count.setVisible(False)


class Sidebar(QFrame):
    """Navegação lateral agrupada (Processamento / Referência) com card de
    licença/servidor fixo no rodapé. Emite `selected(index)`."""

    selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(240)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 14, 12, 14)
        lay.setSpacing(3)

        # Selo da marca (badge no gradiente da identidade visual)
        brand = QHBoxLayout()
        brand.setContentsMargins(4, 0, 4, 10)
        brand.setSpacing(10)
        logo = QLabel(self)
        logo.setObjectName("brandLogo")
        logo.setFixedSize(32, 32)
        logo.setAlignment(Qt.AlignCenter)
        logo.setPixmap(icons.pixmap("zap", "#ffffff", 17))
        brand.addWidget(logo)
        name = QLabel("Processador\nde Ocorrências", self)
        name.setObjectName("brandName")
        brand.addWidget(name)
        brand.addStretch()
        lay.addLayout(brand)

        self._items: list[_NavItem] = []

        groups = [
            ("Processamento", [("Ocorrências", "file-text"), ("VT-Caixa", "table")]),
            ("Referência", [("Códigos", "code"), ("Histórico", "history"),
                            ("Configurações", "settings")]),
        ]
        idx = 0
        for sect_name, entries in groups:
            sect = QLabel(sect_name.upper(), self)
            sect.setObjectName("sideSect")
            lay.addWidget(sect)
            for label, icon_name in entries:
                item = _NavItem(label, icon_name, self)
                item.clicked.connect(lambda _=False, i=idx: self._on_click(i))
                lay.addWidget(item)
                self._items.append(item)
                idx += 1

        lay.addStretch()

        # Card de licença / servidor
        self._licard = QFrame(self)
        self._licard.setObjectName("licard")
        lic_lay = QVBoxLayout(self._licard)
        lic_lay.setContentsMargins(12, 11, 12, 11)
        lic_lay.setSpacing(8)

        row_lic = QHBoxLayout(); row_lic.setSpacing(8)
        k1 = QLabel("Licença"); k1.setObjectName("licardKey")
        self._lic_val = QLabel("—"); self._lic_val.setObjectName("licardVal")
        row_lic.addWidget(k1); row_lic.addStretch(); row_lic.addWidget(self._lic_val)
        lic_lay.addLayout(row_lic)

        row_srv = QHBoxLayout(); row_srv.setSpacing(8)
        self._srv_dot = QLabel("●"); self._srv_dot.setStyleSheet("color: #8590a8;")
        k2 = QLabel("Servidor"); k2.setObjectName("licardKey")
        self._srv_val = QLabel("verificando…"); self._srv_val.setObjectName("licardVal")
        row_srv.addWidget(self._srv_dot); row_srv.addWidget(k2)
        row_srv.addStretch(); row_srv.addWidget(self._srv_val)
        lic_lay.addLayout(row_srv)

        lay.addWidget(self._licard)

        if self._items:
            self._items[0].setChecked(True)

    def _on_click(self, index: int) -> None:
        self.set_current(index)
        self.selected.emit(index)

    def set_current(self, index: int) -> None:
        for i, it in enumerate(self._items):
            it.setChecked(i == index)

    def set_count(self, index: int, n: int) -> None:
        if 0 <= index < len(self._items):
            self._items[index].set_count(n)

    def set_license(self, text: str) -> None:
        # Nome do cliente pode ser longo e a sidebar tem largura fixa.
        fm = self._lic_val.fontMetrics()
        self._lic_val.setText(fm.elidedText(text, Qt.ElideRight, 120))
        self._lic_val.setToolTip(text)

    def set_server(self, text: str, cor: str) -> None:
        fm = self._srv_val.fontMetrics()
        self._srv_val.setText(fm.elidedText(text, Qt.ElideRight, 120))
        self._srv_val.setToolTip(text)
        self._srv_dot.setStyleSheet(f"color: {cor};")
