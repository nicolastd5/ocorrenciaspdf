"""Atualização manual sem travar a UI: UpdateWorker em QThread + QProgressDialog."""
from PySide6.QtCore import QObject, Qt, QThread
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from ui.update_worker import UpdateWorker


class _DialogRelay(QObject):
    """Recebe os sinais do worker na thread da GUI.

    Conectar os sinais a funções soltas executaria os handlers na thread do
    worker, e o QProgressDialog/QMessageBox seriam tocados de lá (crash
    nativo em Qt6Gui.dll — mesmo bug do _UpdateRelay em app.py).
    """

    def __init__(self, dlg: QProgressDialog, parent_widget, thread: QThread):
        # Parente do thread (QObject da thread principal): mantém o relay
        # vivo até o deleteLater — conexões a métodos são referências fracas.
        super().__init__(thread)
        self._dlg = dlg
        self._parent = parent_widget
        self.estado = ""
        self.worker = None
        self.thread = thread

    def on_progress(self, baixado, total):
        mb_b = baixado / 1048576
        if total > 0:
            self._dlg.setMaximum(100)
            self._dlg.setValue(int(baixado / total * 100))
            self._dlg.setLabelText(f"Baixando atualização... {mb_b:.1f} / {total / 1048576:.1f} MB")
        else:
            self._dlg.setMaximum(0)
            self._dlg.setLabelText(f"Baixando atualização... {mb_b:.1f} MB")

    def on_status(self, e):
        self.estado = e

    def on_done(self):
        self._dlg.close()
        if self.estado == "reiniciando":
            QMessageBox.information(
                self._parent, "Atualização",
                "Atualização baixada — o aplicativo será reiniciado agora.")
            QApplication.instance().quit()
        elif self.estado == "erro":
            QMessageBox.warning(
                self._parent, "Atualização",
                "Não foi possível baixar a atualização. Verifique sua conexão "
                "e tente novamente mais tarde.")
        else:
            QMessageBox.information(self._parent, "Atualização",
                                    "Você já está na versão mais recente.")
        self.worker.deleteLater()
        self.thread.deleteLater()


def run_update_dialog(parent) -> None:
    """Verifica/baixa atualização em segundo plano com diálogo de progresso.

    Se uma versão nova for baixada, avisa e encerra o app (o updater.bat
    relança o exe novo). Sem atualização ou em erro, informa e segue.
    """
    dlg = QProgressDialog("Procurando atualizações...", "Ocultar", 0, 0, parent)
    dlg.setWindowTitle("Atualização")
    dlg.setWindowModality(Qt.WindowModal)
    dlg.setMinimumDuration(0)
    dlg.setAutoClose(False)
    dlg.setAutoReset(False)
    dlg.canceled.connect(dlg.hide)  # "Ocultar" esconde; o download continua

    thread = QThread(parent)
    worker = UpdateWorker()
    worker.moveToThread(thread)

    relay = _DialogRelay(dlg, parent, thread)
    relay.worker = worker

    worker.progress.connect(relay.on_progress, Qt.QueuedConnection)
    worker.status.connect(relay.on_status, Qt.QueuedConnection)
    worker.finished.connect(thread.quit)
    thread.started.connect(worker.run)
    thread.finished.connect(relay.on_done, Qt.QueuedConnection)
    thread.start()
