"""Processador de Ocorrências v1.64 — entrypoint."""
import sys

from PySide6.QtWidgets import QApplication

from license_client import LicenseClient
from auto_update import check_and_update
from ui import settings, theme
from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    theme.load_fonts()
    cfg = settings.load()
    theme.apply_theme(app, cfg.get("theme", "dark"))

    check_and_update()  # noop em dev (sys.frozen). Task 11 troca por splash + worker QThread.

    # TODO Task 11: splash com spinner/progresso + auto-update via QThread + bootstrap de licença
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
