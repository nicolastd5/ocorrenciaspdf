from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QMainWindow, QStatusBar, QTabWidget, QWidget

from ui import settings, theme


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Processador de Ocorrências")
        self.resize(900, 680)
        self._restore_geometry()

        self._tabs = QTabWidget(self)
        self._tabs.addTab(self._placeholder("Ocorrências"), "Ocorrências")
        self._tabs.addTab(self._placeholder("VT-Caixa"), "VT-Caixa")
        self._tabs.addTab(self._placeholder("Histórico"), "Histórico")
        self._tabs.addTab(self._placeholder("Configurações"), "Configurações")
        self.setCentralWidget(self._tabs)

        sb = QStatusBar(self)
        self.setStatusBar(sb)
        from license_client import LicenseClient
        sb.showMessage(f"v{LicenseClient.APP_VERSION}  ·  licença OK")

    def _placeholder(self, name: str) -> QWidget:
        from PySide6.QtWidgets import QVBoxLayout
        w = QWidget()
        lbl = QLabel(f"[{name}] em construção", w)
        lbl.setAlignment(Qt.AlignCenter)
        layout = QVBoxLayout(w)
        layout.addWidget(lbl)
        return w

    def _restore_geometry(self) -> None:
        geo = settings.load().get("geometry")
        if geo and isinstance(geo, list) and len(geo) == 4:
            x, y, w, h = geo
            self.setGeometry(x, y, w, h)
        else:
            screen = QGuiApplication.primaryScreen().availableGeometry()
            self.move((screen.width() - self.width()) // 2,
                      (screen.height() - self.height()) // 2)

    def closeEvent(self, ev):
        g = self.geometry()
        settings.save({"geometry": [g.x(), g.y(), g.width(), g.height()]})
        super().closeEvent(ev)
