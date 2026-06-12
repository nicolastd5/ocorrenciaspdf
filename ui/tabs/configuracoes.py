from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QVBoxLayout, QWidget
)

from license_client import LicenseClient
from ui import settings


def _mask_key(key: str) -> str:
    if not key:
        return "(nenhuma)"
    return key[:6] + "…" + key[-4:] if len(key) > 12 else key


class _NoWheelComboBox(QComboBox):
    """Só aceita a roda do mouse com foco — rolar a página por cima do combo
    não pode trocar o modelo selecionado sem querer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, ev):
        if self.hasFocus():
            super().wheelEvent(ev)
        else:
            ev.ignore()


class ConfiguracoesTab(QWidget):
    theme_changed = Signal(str)    # "dark" ou "light"
    license_changed = Signal()     # chave trocada — dispara revalidação

    GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]

    def __init__(self, parent=None):
        super().__init__(parent)
        cfg = settings.load()

        # Conteúdo rolável: em janelas baixas os cards não estouram a tela.
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        scroll.setWidget(page)

        # Limita a largura dos cards: linhas de texto curtas leem melhor em
        # janelas largas; o espaço extra fica à direita.
        outer = QHBoxLayout(page)
        outer.setContentsMargins(28, 24, 28, 28)
        col = QWidget(page)
        col.setStyleSheet("background: transparent;")
        col.setMaximumWidth(860)
        outer.addWidget(col)
        outer.addStretch()

        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        head = QVBoxLayout(); head.setSpacing(3)
        t = QLabel("Configurações"); t.setObjectName("pageTitle")
        s = QLabel("Aparência, IA, licença e atualizações.")
        s.setObjectName("pageSub")
        head.addWidget(t); head.addWidget(s)
        head_wrap = QWidget(); head_wrap.setStyleSheet("background: transparent;"); head_wrap.setLayout(head)
        layout.addWidget(head_wrap)

        # Aparência — toggle segmentado Escuro/Claro
        g_ap = QGroupBox("Aparência", self)
        ap_layout = QHBoxLayout(g_ap)
        seg = QFrame(g_ap); seg.setObjectName("seg")
        seg_lay = QHBoxLayout(seg); seg_lay.setContentsMargins(3, 3, 3, 3); seg_lay.setSpacing(3)
        self._rb_dark = QPushButton("Escuro"); self._rb_dark.setObjectName("segBtn")
        self._rb_light = QPushButton("Claro"); self._rb_light.setObjectName("segBtn")
        for b in (self._rb_dark, self._rb_light):
            b.setCheckable(True); b.setCursor(Qt.PointingHandCursor); b.setAutoExclusive(True)
            seg_lay.addWidget(b)
        if cfg.get("theme") == "light":
            self._rb_light.setChecked(True)
        else:
            self._rb_dark.setChecked(True)
        self._rb_dark.toggled.connect(lambda on: on and self._set_theme("dark"))
        self._rb_light.toggled.connect(lambda on: on and self._set_theme("light"))
        ap_layout.addWidget(seg)
        ap_layout.addStretch()
        layout.addWidget(g_ap)

        # IA Gemini — a chave vem do servidor; os modelos compatíveis são
        # buscados automaticamente na API (sem digitação manual).
        g_ai = QGroupBox("IA Gemini", self)
        ai_form = QFormLayout(g_ai)
        saved_model = cfg.get("gemini_model", "gemini-2.5-flash")
        self._cb_model = _NoWheelComboBox()
        for mid in dict.fromkeys([saved_model] + self.GEMINI_MODELS):
            self._cb_model.addItem(mid, mid)
        self._cb_model.setCurrentIndex(self._cb_model.findData(saved_model))
        self._cb_model.currentIndexChanged.connect(self._save_model)
        ai_form.addRow("Modelo:", self._cb_model)
        row_btn = QHBoxLayout()
        self._btn_modelos = QPushButton("Atualizar lista")
        from ui import icons, theme
        self._btn_modelos.setIcon(icons.icon("refresh", theme.token("fg"), 14))
        self._btn_modelos.clicked.connect(self._carregar_modelos)
        self._lbl_modelos = QLabel("")
        self._lbl_modelos.setObjectName("helpText")
        row_btn.addWidget(self._btn_modelos); row_btn.addWidget(self._lbl_modelos); row_btn.addStretch()
        wrap_btn = QWidget(); wrap_btn.setLayout(row_btn)
        ai_form.addRow(wrap_btn)
        nota = QLabel("A lista mostra apenas modelos compatíveis, buscados direto da API. "
                      "A chave do Gemini é obtida automaticamente do servidor "
                      "(vinculada à sua licença) — não precisa configurar.")
        nota.setWordWrap(True)
        nota.setObjectName("helpText")
        ai_form.addRow(nota)
        layout.addWidget(g_ai)
        self._modelos_thread = None
        self._modelos_worker = None
        self._modelos_buscados = False

        # Licença
        g_lic = QGroupBox("Licença", self)
        lic_layout = QVBoxLayout(g_lic)
        try:
            current_key = LicenseClient().get_saved_key() or ""
        except Exception:
            current_key = ""
        self._lbl_chave = QLabel(f"Chave atual: {_mask_key(current_key)}")
        lic_layout.addWidget(self._lbl_chave)
        btn_change = QPushButton("Trocar chave")
        btn_change.clicked.connect(self._change_license)
        lic_layout.addWidget(btn_change)
        layout.addWidget(g_lic)

        # Status do servidor
        g_srv = QGroupBox("Status do servidor", self)
        srv_form = QFormLayout(g_srv)
        self._lbl_conexao = QLabel("Verificando…")
        self._lbl_versao = QLabel("—")
        self._lbl_gemini = QLabel("—")
        srv_form.addRow("Conexão:", self._lbl_conexao)
        srv_form.addRow("Versão mais recente:", self._lbl_versao)
        srv_form.addRow("API Gemini:", self._lbl_gemini)
        layout.addWidget(g_srv)

        # Atualizações
        g_up = QGroupBox("Atualizações", self)
        up_layout = QHBoxLayout(g_up)
        up_layout.addWidget(QLabel(f"Versão atual: {LicenseClient.APP_VERSION}"))
        btn_check = QPushButton("Verificar agora")
        btn_check.clicked.connect(self._check_update)
        up_layout.addWidget(btn_check); up_layout.addStretch()
        layout.addWidget(g_up)

        # Sobre
        g_about = QGroupBox("Sobre", self)
        about_layout = QVBoxLayout(g_about)
        about_layout.addWidget(QLabel(
            f"Processador de Ocorrências v{LicenseClient.APP_VERSION}\n"
            "Autor: Nicolas Almeida Hader Dias"
        ))
        layout.addWidget(g_about)

        layout.addStretch()

    def atualizar_status(self, conexao: str, cor: str, versao: str = None, gemini_ok: bool = None):
        """Chamado pela MainWindow após cada checagem de conexão."""
        self._lbl_conexao.setText(conexao)
        self._lbl_conexao.setStyleSheet(f"color: {cor}; font-weight: 600;")
        if versao:
            self._lbl_versao.setText(f"v{versao}")
        if gemini_ok is not None:
            self._lbl_gemini.setText("configurada" if gemini_ok else "indisponível")

    def showEvent(self, ev):
        # Primeira visita à página: busca os modelos compatíveis na API
        # em segundo plano — o usuário só escolhe, não digita.
        super().showEvent(ev)
        if not self._modelos_buscados:
            self._modelos_buscados = True
            self._carregar_modelos()

    def _set_theme(self, mode: str):
        settings.save({"theme": mode})
        self.theme_changed.emit(mode)

    def _save_model(self, _index: int):
        model = self._cb_model.currentData()
        if model:
            settings.save({"gemini_model": model})

    def _carregar_modelos(self):
        if self._modelos_thread is not None:
            return
        from ui.server_config import ModelosWorker
        self._btn_modelos.setEnabled(False)
        self._lbl_modelos.setText("Buscando modelos…")
        self._modelos_thread = QThread(self)
        self._modelos_worker = ModelosWorker()
        self._modelos_worker.moveToThread(self._modelos_thread)
        self._modelos_thread.started.connect(self._modelos_worker.run)
        self._modelos_worker.ok.connect(self._popular_modelos)
        self._modelos_worker.erro.connect(self._erro_modelos)
        self._modelos_worker.finished.connect(self._modelos_thread.quit)
        self._modelos_thread.finished.connect(self._modelos_cleanup)
        self._modelos_thread.start()

    def _popular_modelos(self, modelos):
        atual = self._cb_model.currentData()
        self._cb_model.blockSignals(True)
        self._cb_model.clear()
        for display, model_id in modelos:
            self._cb_model.addItem(f"{display}  ({model_id})", model_id)
        idx = self._cb_model.findData(atual)
        if idx >= 0:
            self._cb_model.setCurrentIndex(idx)
        else:
            # modelo salvo não está mais na lista: mantém como opção extra
            self._cb_model.addItem(atual, atual)
            self._cb_model.setCurrentIndex(self._cb_model.count() - 1)
        self._cb_model.blockSignals(False)
        self._lbl_modelos.setText(f"{len(modelos)} modelo(s) compatível(is) encontrado(s).")

    def _erro_modelos(self, msg):
        self._lbl_modelos.setText(f"Não foi possível buscar os modelos: {msg[:60]}")

    def _modelos_cleanup(self):
        self._btn_modelos.setEnabled(True)
        self._modelos_thread = None
        self._modelos_worker = None

    def _change_license(self):
        from ui.license_dialogs import show_activation_window
        new_key = show_activation_window("Insira a nova chave de licença.")
        if new_key:
            LicenseClient().save_key(new_key)
            self._lbl_chave.setText(f"Chave atual: {_mask_key(new_key)}")
            self._lbl_conexao.setText("Validando…")
            # MainWindow revalida em segundo plano e atualiza sidebar/status.
            self.license_changed.emit()

    def _check_update(self):
        from ui.update_dialog import run_update_dialog
        run_update_dialog(self)
