"""Processador de Ocorrências v1.64 — entrypoint."""
import sys

from PySide6.QtCore import QEventLoop, QThread, QTimer
from PySide6.QtWidgets import QApplication

from license_client import LicenseClient, LicenseStatus
from ui import settings, theme
from ui import license_dialogs
from ui.main_window import MainWindow
from ui.splash import Splash
from ui.update_worker import UpdateWorker


def _resolver_licenca(client, result) -> bool:
    while True:
        if result.status in (LicenseStatus.VALID, LicenseStatus.OFFLINE_TOLERATED):
            return True
        if result.status == LicenseStatus.NO_KEY:
            new_key = license_dialogs.show_activation_window("Insira sua chave de licença para começar.")
        elif result.status == LicenseStatus.INVALID:
            reason = {
                "not_found": "Chave não reconhecida.",
                "revoked": "Esta chave foi revogada. Entre em contato com o suporte.",
            }.get(result.reason, "Chave inválida.")
            new_key = license_dialogs.show_activation_window(reason)
        elif result.status == LicenseStatus.OFFLINE_EXPIRED:
            license_dialogs.show_error_window(
                "Não foi possível validar sua licença com o servidor e o "
                "período de uso offline expirou. Conecte-se à internet e tente novamente."
            )
            return False
        else:
            return False
        if new_key is None:
            return False
        client.save_key(new_key)
        result = client.validate()


def _run_auto_update(splash: Splash) -> str:
    estado = {"valor": ""}

    thread = QThread()
    worker = UpdateWorker()
    worker.moveToThread(thread)

    def on_progress(baixado, total):
        if total > 0:
            mb_b, mb_t = baixado / 1048576, total / 1048576
            splash.set_progress(baixado / total,
                                f"Baixando atualização... {int(baixado / total * 100)}% — {mb_b:.1f} / {mb_t:.1f} MB")
        else:
            splash.set_progress(None, f"Baixando atualização... {baixado / 1048576:.1f} MB")

    def on_status(e):
        estado["valor"] = e
        if e == "verificando":
            splash.set_status("Procurando atualizações...")

    worker.progress.connect(on_progress)
    worker.status.connect(on_status)

    loop = QEventLoop()
    worker.finished.connect(loop.quit)
    worker.finished.connect(thread.quit)
    thread.started.connect(worker.run)
    thread.start()
    loop.exec()
    thread.wait()
    return estado["valor"]


def main() -> int:
    app = QApplication(sys.argv)
    theme.load_fonts()
    cfg = settings.load()
    theme.apply_theme(app, cfg.get("theme", "dark"))

    splash = Splash(LicenseClient.APP_VERSION)
    splash.show()

    estado = _run_auto_update(splash)
    if estado == "reiniciando":
        splash.set_progress(1.0, "Atualização concluída — reiniciando...")
        QTimer.singleShot(1000, app.quit)
        app.exec()
        return 0
    splash.hide_progress()
    if estado == "erro":
        splash.set_status("Não foi possível atualizar, continuando...")

    splash.set_status("Validando licença...")
    client = LicenseClient()
    result = client.validate()

    if result.status not in (LicenseStatus.VALID, LicenseStatus.OFFLINE_TOLERATED):
        splash.fechar()
        if not _resolver_licenca(client, result):
            return 1
        window = MainWindow()
        window.show()
        return app.exec()

    splash.set_status("Carregando...")
    window = MainWindow()
    QTimer.singleShot(300, lambda: (splash.fechar(), window.show()))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
