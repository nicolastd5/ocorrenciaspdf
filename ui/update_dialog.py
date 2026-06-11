"""Atualização manual sem travar a UI: UpdateWorker em QThread + QProgressDialog."""
from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from ui.update_worker import UpdateWorker


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

    estado = {"valor": ""}
    thread = QThread(parent)
    worker = UpdateWorker()
    worker.moveToThread(thread)

    def on_progress(baixado, total):
        mb_b = baixado / 1048576
        if total > 0:
            dlg.setMaximum(100)
            dlg.setValue(int(baixado / total * 100))
            dlg.setLabelText(f"Baixando atualização... {mb_b:.1f} / {total / 1048576:.1f} MB")
        else:
            dlg.setMaximum(0)
            dlg.setLabelText(f"Baixando atualização... {mb_b:.1f} MB")

    def on_status(e):
        estado["valor"] = e

    worker.progress.connect(on_progress)
    worker.status.connect(on_status)
    worker.finished.connect(thread.quit)
    thread.started.connect(worker.run)

    def on_done():
        dlg.close()
        e = estado["valor"]
        if e == "reiniciando":
            QMessageBox.information(
                parent, "Atualização",
                "Atualização baixada — o aplicativo será reiniciado agora.")
            QApplication.instance().quit()
        elif e == "erro":
            QMessageBox.warning(
                parent, "Atualização",
                "Não foi possível baixar a atualização. Verifique sua conexão "
                "e tente novamente mais tarde.")
        else:
            QMessageBox.information(parent, "Atualização",
                                    "Você já está na versão mais recente.")
        worker.deleteLater()
        thread.deleteLater()

    thread.finished.connect(on_done)
    thread.start()
