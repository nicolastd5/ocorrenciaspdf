from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout
)


def show_activation_window(initial_message: str = "") -> str | None:
    """Modal pra capturar chave. Retorna chave (uppercase, strip) ou None."""
    dialog = QDialog()
    dialog.setWindowTitle("Ativação de licença")
    dialog.setMinimumWidth(460)
    dialog.setModal(True)

    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("<b>Processador de Ocorrências</b>"))
    layout.addWidget(QLabel("Insira sua chave para liberar o aplicativo."))

    if initial_message:
        msg = QLabel(initial_message)
        msg.setStyleSheet("color: #ef4444;")
        msg.setWordWrap(True)
        layout.addWidget(msg)

    layout.addWidget(QLabel("CHAVE DE LICENÇA"))
    edit = QLineEdit()
    edit.setStyleSheet("font-family: 'JetBrains Mono', Consolas, monospace;")
    layout.addWidget(edit)

    btns = QHBoxLayout()
    b_ok = QPushButton("Ativar"); b_ok.setObjectName("primary")
    b_cancel = QPushButton("Sair")
    btns.addWidget(b_ok); btns.addStretch(); btns.addWidget(b_cancel)
    layout.addLayout(btns)

    result = {"key": None}

    def on_ok():
        v = edit.text().strip().upper()
        if v:
            result["key"] = v
            dialog.accept()

    b_ok.clicked.connect(on_ok)
    b_cancel.clicked.connect(dialog.reject)
    edit.returnPressed.connect(on_ok)
    dialog.exec()
    return result["key"]


def show_error_window(message: str) -> None:
    QMessageBox.critical(None, "Erro de licença", message)
