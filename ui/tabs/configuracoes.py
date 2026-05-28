from PySide6.QtCore import Signal, QThread
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QRadioButton, QVBoxLayout, QWidget
)

from auto_update import check_and_update
from license_client import LicenseClient
from ui import settings


class ConfiguracoesTab(QWidget):
    theme_changed = Signal(str)  # "dark" ou "light"

    GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]

    def __init__(self, parent=None):
        super().__init__(parent)
        cfg = settings.load()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Aparência
        g_ap = QGroupBox("Aparência", self)
        ap_layout = QHBoxLayout(g_ap)
        self._rb_dark = QRadioButton("Escuro")
        self._rb_light = QRadioButton("Claro")
        if cfg.get("theme") == "light":
            self._rb_light.setChecked(True)
        else:
            self._rb_dark.setChecked(True)
        self._rb_dark.toggled.connect(lambda on: on and self._set_theme("dark"))
        self._rb_light.toggled.connect(lambda on: on and self._set_theme("light"))
        ap_layout.addWidget(self._rb_dark)
        ap_layout.addWidget(self._rb_light)
        ap_layout.addStretch()
        layout.addWidget(g_ap)

        # IA Gemini — a chave vem do servidor automaticamente; aqui só escolhe o modelo
        g_ai = QGroupBox("IA Gemini", self)
        ai_form = QFormLayout(g_ai)
        self._cb_model = QComboBox()
        self._cb_model.addItems(self.GEMINI_MODELS)
        self._cb_model.setCurrentText(cfg.get("gemini_model", "gemini-2.5-flash"))
        self._cb_model.setEditable(True)  # permite manter um model_id não-listado
        self._cb_model.currentTextChanged.connect(self._save_model)
        ai_form.addRow("Modelo:", self._cb_model)
        row_btn = QHBoxLayout()
        self._btn_modelos = QPushButton("↻ Carregar modelos da API")
        self._btn_modelos.clicked.connect(self._carregar_modelos)
        self._lbl_modelos = QLabel("")
        self._lbl_modelos.setStyleSheet("color: #8b949e; font-size: 9pt;")
        row_btn.addWidget(self._btn_modelos); row_btn.addWidget(self._lbl_modelos); row_btn.addStretch()
        wrap_btn = QWidget(); wrap_btn.setLayout(row_btn)
        ai_form.addRow(wrap_btn)
        nota = QLabel("A chave da API do Gemini é obtida automaticamente do servidor "
                      "(vinculada à sua licença) — não precisa configurar.")
        nota.setWordWrap(True)
        nota.setStyleSheet("color: #8b949e; font-size: 9pt;")
        ai_form.addRow(nota)
        layout.addWidget(g_ai)
        self._modelos_thread = None
        self._modelos_worker = None

        # Licença
        g_lic = QGroupBox("Licença", self)
        lic_layout = QVBoxLayout(g_lic)
        client = LicenseClient()
        try:
            current_key = client.get_saved_key() or "(nenhuma)"
        except Exception:
            current_key = "(nenhuma)"
        masked = current_key[:6] + "…" + current_key[-4:] if len(current_key) > 12 else current_key
        lic_layout.addWidget(QLabel(f"Chave atual: {masked}"))
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

    def _set_theme(self, mode: str):
        settings.save({"theme": mode})
        self.theme_changed.emit(mode)

    def _save_model(self, model: str):
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
        atual = self._cb_model.currentText()
        self._cb_model.blockSignals(True)
        self._cb_model.clear()
        ids = [model_id for _display, model_id in modelos]
        self._cb_model.addItems(ids)
        if atual in ids:
            self._cb_model.setCurrentText(atual)
        self._cb_model.blockSignals(False)
        self._lbl_modelos.setText(f"{len(ids)} modelo(s) carregado(s).")

    def _erro_modelos(self, msg):
        self._lbl_modelos.setText(f"Erro: {msg[:60]}")

    def _modelos_cleanup(self):
        self._btn_modelos.setEnabled(True)
        self._modelos_thread = None
        self._modelos_worker = None

    def _change_license(self):
        from ui.license_dialogs import show_activation_window
        new_key = show_activation_window("Insira a nova chave de licença.")
        if new_key:
            LicenseClient().save_key(new_key)
            QMessageBox.information(self, "Licença", "Chave atualizada. Reinicie o app pra validar.")

    def _check_update(self):
        check_and_update()
        QMessageBox.information(self, "Atualizações", "Verificação concluída (sem atualização ou já atualizado).")
