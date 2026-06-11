"""Diálogo de texto somente leitura — relatórios de IA, detalhes do histórico etc."""
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout
)


def show_text_dialog(parent, title: str, text: str, size=(620, 440)) -> None:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.resize(*size)
    lay = QVBoxLayout(dlg)
    txt = QPlainTextEdit(dlg)
    txt.setReadOnly(True)
    txt.setObjectName("log")
    txt.setPlainText(text)
    lay.addWidget(txt)
    row = QHBoxLayout()
    b_copy = QPushButton("Copiar")
    b_copy.clicked.connect(lambda: QApplication.clipboard().setText(txt.toPlainText()))
    row.addWidget(b_copy)
    row.addStretch()
    b = QPushButton("Fechar")
    b.clicked.connect(dlg.accept)
    row.addWidget(b)
    lay.addLayout(row)
    dlg.exec()
