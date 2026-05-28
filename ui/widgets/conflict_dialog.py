from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QDialog, QDialogButtonBox, QFrame, QLabel, QRadioButton,
    QScrollArea, QVBoxLayout, QHBoxLayout, QWidget
)

_ROTULOS = {"v1": "V1 (tabelas)", "v2": "V2 (texto)", "ia": "IA (Gemini)"}


class ConflictDialog(QDialog):
    """Modal de resolução de conflitos entre camadas de extração.

    conflitos: list de dicts {re, nome, codigo, valores:{camada:int}, sugestao:int}
    Use .resultado() após exec(): lista [(re, codigo, valor), ...] ou None se cancelado.
    """

    def __init__(self, conflitos: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Conflitos encontrados")
        self.setModal(True)
        self.resize(760, 540)
        self._grupos = {}
        self._resultado = None

        outer = QVBoxLayout(self)
        outer.addWidget(QLabel(
            f"<b>Conflitos encontrados — {len(conflitos)} item(s) precisam de revisão</b>"))
        outer.addWidget(QLabel(
            "Selecione o valor correto para cada conflito. A sugestão já está pré-selecionada."))

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        scroll.setWidget(body)
        outer.addWidget(scroll, stretch=1)

        for c in conflitos:
            re_val, nome, cod = c["re"], c["nome"], c["codigo"]
            valores, sug = c["valores"], c["sugestao"]

            card = QFrame()
            card.setObjectName("dropzone")
            card_l = QVBoxLayout(card)
            header = QHBoxLayout()
            header.addWidget(QLabel(f"<b>RE {re_val}  —  {nome}</b>"))
            header.addStretch()
            header.addWidget(QLabel(f"Código: {cod}"))
            card_l.addLayout(header)

            group = QButtonGroup(card)
            self._grupos[(re_val, cod)] = group
            valores_unicos = {}
            for camada, val in valores.items():
                if val is None:
                    continue
                valores_unicos.setdefault(val, []).append(_ROTULOS.get(camada, camada))
            row = QHBoxLayout()
            for val_opcao in sorted(valores_unicos):
                camadas_label = ", ".join(valores_unicos[val_opcao])
                rb = QRadioButton(f"{val_opcao} {cod}  ({camadas_label})")
                rb.setProperty("valor", int(val_opcao))
                if val_opcao == sug:
                    rb.setChecked(True)
                group.addButton(rb)
                row.addWidget(rb)
            row.addStretch()
            card_l.addLayout(row)
            body_layout.addWidget(card)
        body_layout.addStretch()

        btns = QDialogButtonBox(self)
        b_ok = btns.addButton("Confirmar e gravar", QDialogButtonBox.AcceptRole)
        b_ok.setObjectName("primary")
        btns.addButton("Cancelar", QDialogButtonBox.RejectRole)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

    def _on_accept(self):
        escolhas = []
        for (re_val, cod), group in self._grupos.items():
            btn = group.checkedButton()
            if btn is not None:
                escolhas.append((re_val, cod, int(btn.property("valor"))))
        self._resultado = escolhas
        self.accept()

    def resultado(self):
        return self._resultado
