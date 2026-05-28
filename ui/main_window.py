from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QMainWindow, QStatusBar, QTabWidget, QWidget

from ui import history, settings, theme
from ui.tabs import OcorrenciasTab, VTCaixaTab, CodigosTab, HistoricoTab, ConfiguracoesTab


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
        self._tabs.addTab(CodigosTab(self), "Códigos")
        self._historico = HistoricoTab(self)
        self._tabs.addTab(self._historico, "Histórico")
        self._cfg_tab = ConfiguracoesTab(self)
        self._cfg_tab.theme_changed.connect(self._apply_theme_runtime)
        self._tabs.addTab(self._cfg_tab, "Configurações")

        from PySide6.QtWidgets import QVBoxLayout
        central = QWidget(self)
        col = QVBoxLayout(central)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        self._banner = self._criar_banner_update()
        self._banner.setVisible(False)
        col.addWidget(self._banner)
        col.addWidget(self._tabs)
        self.setCentralWidget(central)

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

    def _criar_banner_update(self) -> QWidget:
        from PySide6.QtWidgets import QHBoxLayout, QPushButton
        w = QWidget(self)
        w.setStyleSheet("QWidget { background: #0f1a14; }")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(14, 8, 14, 8)
        self._banner_lbl = QLabel("Nova versão disponível")
        self._banner_lbl.setStyleSheet("color: #2ea043; font-weight: 600;")
        lay.addWidget(self._banner_lbl)
        lay.addStretch()
        btn = QPushButton("Atualizar agora")
        btn.setObjectName("primary")
        btn.clicked.connect(self._aplicar_update)
        lay.addWidget(btn)
        btn_x = QPushButton("✕")
        btn_x.setFixedWidth(28)
        btn_x.clicked.connect(lambda: self._banner.setVisible(False))
        lay.addWidget(btn_x)
        return w

    def _aplicar_update(self):
        from auto_update import check_and_update
        from PySide6.QtWidgets import QMessageBox
        check_and_update()
        QMessageBox.information(
            self, "Atualização",
            "Se houver uma nova versão, ela será baixada e o app reiniciará. "
            "Caso nada aconteça, já está atualizado ou o download está em andamento."
        )

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
        if versao:
            from auto_update import _parse_version
            from license_client import LicenseClient
            if _parse_version(versao) > _parse_version(LicenseClient.APP_VERSION):
                self._banner_lbl.setText(f"Nova versão disponível: v{versao}")
                self._banner.setVisible(True)

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
