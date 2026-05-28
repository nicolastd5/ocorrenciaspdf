from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
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

        # API Gemini
        g_ai = QGroupBox("API Gemini", self)
        ai_form = QFormLayout(g_ai)
        self._ed_key = QLineEdit(cfg.get("api_key", ""))
        self._ed_key.setEchoMode(QLineEdit.Password)
        self._cb_model = QComboBox()
        self._cb_model.addItems(self.GEMINI_MODELS)
        self._cb_model.setCurrentText(cfg.get("gemini_model", "gemini-2.5-flash"))
        row = QHBoxLayout()
        self._btn_save_ai = QPushButton("Salvar")
        self._btn_save_ai.clicked.connect(self._save_ai)
        row.addWidget(self._btn_save_ai); row.addStretch()
        ai_form.addRow("Chave:", self._ed_key)
        ai_form.addRow("Modelo:", self._cb_model)
        wrap = QWidget(); wrap.setLayout(row)
        ai_form.addRow(wrap)
        layout.addWidget(g_ai)

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

    def _set_theme(self, mode: str):
        settings.save({"theme": mode})
        self.theme_changed.emit(mode)

    def _save_ai(self):
        err = settings.save({
            "api_key": self._ed_key.text().strip(),
            "gemini_model": self._cb_model.currentText(),
        })
        if err:
            QMessageBox.warning(self, "Erro", f"Falha ao salvar: {err}")
        else:
            QMessageBox.information(self, "OK", "Configurações de IA salvas.")

    def _change_license(self):
        from ui.license_dialogs import show_activation_window
        new_key = show_activation_window("Insira a nova chave de licença.")
        if new_key:
            LicenseClient().save_key(new_key)
            QMessageBox.information(self, "Licença", "Chave atualizada. Reinicie o app pra validar.")

    def _check_update(self):
        check_and_update()
        QMessageBox.information(self, "Atualizações", "Verificação concluída (sem atualização ou já atualizado).")
