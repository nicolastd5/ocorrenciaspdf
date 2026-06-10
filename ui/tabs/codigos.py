from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QGroupBox, QHeaderView, QLabel, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget
)

from vt_caixa_processador import ProcessadorVTCaixa


class CodigosTab(QWidget):
    """Tela de referência (somente leitura) com os códigos do VT-Caixa.

    Duas tabelas: Operadora → Código de Benefício e Substituições de Departamento.
    Clicar/dar Enter numa linha copia o código/substituto para a área de transferência.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 22, 24)
        layout.setSpacing(14)

        head = QVBoxLayout(); head.setSpacing(3)
        t = QLabel("Códigos"); t.setObjectName("pageTitle")
        dica = QLabel("Tabelas de referência usadas no processamento do VT-Caixa. "
                      "Clique numa linha para copiar o código/substituto.")
        dica.setObjectName("pageSub")
        dica.setWordWrap(True)
        head.addWidget(t); head.addWidget(dica)
        head_wrap = QWidget(); head_wrap.setStyleSheet("background: transparent;"); head_wrap.setLayout(head)
        layout.addWidget(head_wrap)

        # Operadora -> Código de Benefício
        g_cod = QGroupBox("Operadora → Código de Benefício", self)
        cod_layout = QVBoxLayout(g_cod)
        codigos = ProcessadorVTCaixa._CODIGOS_BENEFICIO
        self._tbl_cod = self._make_table(
            ["Operadora", "Valor Unitário", "Código"],
            [(op, valor or "qualquer", cod) for op, valor, cod in codigos],
            copy_col=2,
        )
        cod_layout.addWidget(self._tbl_cod)
        layout.addWidget(g_cod, stretch=3)

        # Substituições de Departamento
        g_dep = QGroupBox("Substituições de Departamento", self)
        dep_layout = QVBoxLayout(g_dep)
        depart = ProcessadorVTCaixa._DEPART_MAP
        self._tbl_dep = self._make_table(
            ["Departamento original", "Substituto"],
            list(depart.items()),
            copy_col=1,
        )
        dep_layout.addWidget(self._tbl_dep)
        layout.addWidget(g_dep, stretch=2)

    def _make_table(self, headers, rows, copy_col):
        tbl = QTableWidget(len(rows), len(headers), self)
        tbl.setHorizontalHeaderLabels(headers)
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, len(headers)):
            tbl.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                if c == copy_col:
                    from PySide6.QtGui import QColor
                    item.setForeground(QColor("#58a6ff"))
                tbl.setItem(r, c, item)
        tbl.cellClicked.connect(lambda r, _c, t=tbl, cc=copy_col: self._copiar(t, r, cc))
        return tbl

    def _copiar(self, tbl, row, col):
        item = tbl.item(row, col)
        if item is None:
            return
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(item.text())
