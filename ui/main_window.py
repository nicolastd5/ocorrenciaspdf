from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QMainWindow, QStatusBar, QTabWidget, QWidget

from ui import history, settings, theme
from ui.tabs import OcorrenciasTab, VTCaixaTab, HistoricoTab, ConfiguracoesTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Processador de Ocorrências")
        self.resize(900, 680)
        self._restore_geometry()

        self._tabs = QTabWidget(self)
        oco = OcorrenciasTab(self)
        oco.processed.connect(self._on_processed)
        self._tabs.addTab(oco, "Ocorrências")
        vtc = VTCaixaTab(self)
        vtc.processed.connect(self._on_processed)
        self._tabs.addTab(vtc, "VT-Caixa")
        self._historico = HistoricoTab(self)
        self._tabs.addTab(self._historico, "Histórico")
        self._cfg_tab = ConfiguracoesTab(self)
        self._cfg_tab.theme_changed.connect(self._apply_theme_runtime)
        self._tabs.addTab(self._cfg_tab, "Configurações")
        self.setCentralWidget(self._tabs)

        from license_client import LicenseClient
        sb = QStatusBar(self)
        self.setStatusBar(sb)
        sb.addWidget(QLabel(f"v{LicenseClient.APP_VERSION}"))
        self._conn_pill = QLabel("●  verificando…")
        self._conn_pill.setStyleSheet("color: #8b949e;")
        sb.addPermanentWidget(self._conn_pill)

        self._conn_thread = None
        self._conn_worker = None
        self._conn_timer = QTimer(self)
        self._conn_timer.timeout.connect(self._checar_conexao)
        self._conn_timer.start(60000)  # revalida a cada 60s
        QTimer.singleShot(500, self._checar_conexao)  # primeira checagem logo após abrir

    def _apply_theme_runtime(self, mode: str) -> None:
        from PySide6.QtWidgets import QApplication
        theme.apply_theme(QApplication.instance(), mode)

    def _checar_conexao(self):
        if self._conn_thread is not None:
            return  # checagem em andamento
        from ui.server_config import ConnCheckWorker
        self._conn_thread = QThread(self)
        self._conn_worker = ConnCheckWorker()
        self._conn_worker.moveToThread(self._conn_thread)
        self._conn_thread.started.connect(self._conn_worker.run)
        self._conn_worker.resultado.connect(self._on_conn_resultado)
        self._conn_worker.finished.connect(self._conn_thread.quit)
        self._conn_thread.finished.connect(self._on_conn_thread_done)
        self._conn_thread.start()

    def _on_conn_resultado(self, texto, cor, versao, gemini_ok):
        self._conn_pill.setText(f"●  {texto}")
        self._conn_pill.setStyleSheet(f"color: {cor};")
        self._cfg_tab.atualizar_status(texto, cor, versao=versao or None, gemini_ok=gemini_ok)

    def _on_conn_thread_done(self):
        self._conn_thread = None
        self._conn_worker = None

    def _on_processed(self, entry: dict) -> None:
        history.append(entry)
        self._historico.refresh()

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
        self._conn_timer.stop()
        if self._conn_thread is not None:
            self._conn_thread.quit()
            self._conn_thread.wait()
        g = self.geometry()
        settings.save({"geometry": [g.x(), g.y(), g.width(), g.height()]})
        super().closeEvent(ev)
