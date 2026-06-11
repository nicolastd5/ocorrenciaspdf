from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMainWindow, QStackedWidget, QStatusBar, QVBoxLayout, QWidget
)

from ui import history, settings, theme
from ui.tabs import OcorrenciasTab, VTCaixaTab, CodigosTab, HistoricoTab, ConfiguracoesTab
from ui.widgets import Sidebar

# Ordem das páginas casa com a ordem da Sidebar (Processamento + Referência)
_PAGE_OCORRENCIAS = 0
_PAGE_VTCAIXA = 1
_PAGE_CODIGOS = 2
_PAGE_HISTORICO = 3
_PAGE_CONFIG = 4


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Processador de Ocorrências")
        self.setMinimumSize(1024, 640)
        self.resize(1280, 760)
        self._restore_geometry()
        self._session_runs = 0
        self._banner_version = ""

        # ---- páginas ----
        self._stack = QStackedWidget(self)
        oco = OcorrenciasTab(self)
        oco.processed.connect(self._on_processed)
        self._stack.addWidget(oco)                                   # 0
        vtc = VTCaixaTab(self)
        vtc.processed.connect(self._on_processed)
        self._stack.addWidget(vtc)                                   # 1
        self._stack.addWidget(CodigosTab(self))                      # 2
        self._historico = HistoricoTab(self)
        self._stack.addWidget(self._historico)                      # 3
        self._cfg_tab = ConfiguracoesTab(self)
        self._cfg_tab.theme_changed.connect(self._apply_theme_runtime)
        self._cfg_tab.license_changed.connect(self._checar_conexao)
        self._stack.addWidget(self._cfg_tab)                        # 4

        # ---- sidebar ----
        self._sidebar = Sidebar(self)
        self._sidebar.selected.connect(self._stack.setCurrentIndex)
        self._sidebar.set_count(_PAGE_HISTORICO, len(history.load()))

        # Estado real (válida/inválida/offline) chega via ConnCheckWorker;
        # até lá mostra apenas se existe chave salva.
        from license_client import LicenseClient
        try:
            client = LicenseClient()
            self._sidebar.set_license("verificando…" if client.get_saved_key() else "—")
        except Exception:
            self._sidebar.set_license("—")

        # ---- corpo: banner em cima, sidebar + stack abaixo ----
        central = QWidget(self)
        col = QVBoxLayout(central)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        self._banner = self._criar_banner_update()
        self._banner.setVisible(False)
        col.addWidget(self._banner)

        body = QWidget(central)
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)
        body_lay.addWidget(self._sidebar)
        body_lay.addWidget(self._stack, stretch=1)
        col.addWidget(body, stretch=1)
        self.setCentralWidget(central)

        # ---- status bar ----
        sb = QStatusBar(self)
        self.setStatusBar(sb)
        sb.addWidget(QLabel(f"v{LicenseClient.APP_VERSION}"))
        self._lbl_sessao = QLabel("0 processamento(s) nesta sessão")
        sb.addWidget(self._lbl_sessao)
        self._conn_pill = QLabel("●  verificando…")
        self._conn_pill.setStyleSheet(f"color: {theme.token('fg_dim')};")
        sb.addPermanentWidget(self._conn_pill)

        # ---- atalhos: Ctrl+1..5 navegam entre as páginas ----
        for i in range(self._stack.count()):
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self,
                      activated=lambda i=i: self._goto_page(i))

        # ---- checagem de conexão ----
        self._conn_thread = None
        self._conn_worker = None
        self._conn_timer = QTimer(self)
        self._conn_timer.timeout.connect(self._checar_conexao)
        self._conn_timer.start(60000)  # revalida a cada 60s
        QTimer.singleShot(500, self._checar_conexao)  # primeira checagem logo após abrir

    def _goto_page(self, index: int) -> None:
        self._sidebar.set_current(index)
        self._stack.setCurrentIndex(index)

    def _apply_theme_runtime(self, mode: str) -> None:
        from PySide6.QtWidgets import QApplication
        theme.apply_theme(QApplication.instance(), mode)

    def _criar_banner_update(self) -> QWidget:
        from PySide6.QtWidgets import QHBoxLayout, QPushButton
        w = QWidget(self)
        w.setObjectName("updateBanner")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(14, 8, 14, 8)
        self._banner_lbl = QLabel("Nova versão disponível")
        self._banner_lbl.setObjectName("updateBannerLbl")
        lay.addWidget(self._banner_lbl)
        lay.addStretch()
        btn = QPushButton("Atualizar agora")
        btn.setObjectName("primary")
        btn.clicked.connect(self._aplicar_update)
        lay.addWidget(btn)
        btn_x = QPushButton("✕")
        btn_x.setObjectName("ghost")
        btn_x.setFixedWidth(28)
        btn_x.setToolTip("Dispensar este aviso até a próxima versão")
        btn_x.clicked.connect(self._dispensar_banner)
        lay.addWidget(btn_x)
        return w

    def _dispensar_banner(self):
        self._banner.setVisible(False)
        if self._banner_version:
            settings.save({"update_banner_dismissed": self._banner_version})

    def _aplicar_update(self):
        from ui.update_dialog import run_update_dialog
        run_update_dialog(self)

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

    def _on_conn_resultado(self, texto, cor, versao, gemini_ok, licenca):
        self._conn_pill.setText(f"●  {texto}")
        self._conn_pill.setStyleSheet(f"color: {cor};")
        self._sidebar.set_server(texto, cor)
        self._sidebar.set_license(licenca)
        self._cfg_tab.atualizar_status(texto, cor, versao=versao or None, gemini_ok=gemini_ok)
        if versao:
            from auto_update import _parse_version
            from license_client import LicenseClient
            dispensada = settings.load().get("update_banner_dismissed", "")
            if (_parse_version(versao) > _parse_version(LicenseClient.APP_VERSION)
                    and versao != dispensada):
                self._banner_version = versao
                self._banner_lbl.setText(f"Nova versão disponível: v{versao}")
                self._banner.setVisible(True)

    def _on_conn_thread_done(self):
        self._conn_thread = None
        self._conn_worker = None

    def _on_processed(self, entry: dict) -> None:
        history.append(entry)
        self._historico.refresh()
        self._sidebar.set_count(_PAGE_HISTORICO, len(history.load()))
        self._session_runs += 1
        self._lbl_sessao.setText(f"{self._session_runs} processamento(s) nesta sessão")

    def _restore_geometry(self) -> None:
        screen = QGuiApplication.primaryScreen().availableGeometry()
        geo = settings.load().get("geometry")
        if geo and isinstance(geo, list) and len(geo) == 4:
            x, y, w, h = geo
            # Geometrias salvas por versões antigas eram estreitas (980px);
            # alarga até um mínimo confortável, sem estourar a tela.
            w = min(max(w, 1180), screen.width())
            h = min(max(h, 700), screen.height())
            x = max(screen.left(), min(x, screen.right() - w))
            y = max(screen.top(), min(y, screen.bottom() - h))
            self.setGeometry(x, y, w, h)
        else:
            w = min(1280, screen.width() - 80)
            h = min(760, screen.height() - 80)
            self.resize(w, h)
            self.move(screen.left() + (screen.width() - w) // 2,
                      screen.top() + (screen.height() - h) // 2)

    def closeEvent(self, ev):
        self._conn_timer.stop()
        if self._conn_thread is not None:
            self._conn_thread.quit()
            self._conn_thread.wait()
        g = self.geometry()
        settings.save({"geometry": [g.x(), g.y(), g.width(), g.height()]})
        super().closeEvent(ev)
