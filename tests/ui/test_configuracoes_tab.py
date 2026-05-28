import ui.settings as settings
import ui.tabs.configuracoes as cfgmod


def test_constructs_and_reflects_theme(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "_CONFIG_PATH", tmp_path / "cfg.json")
    settings.save({"theme": "light"})
    tab = cfgmod.ConfiguracoesTab()
    qtbot.addWidget(tab)
    assert tab._rb_light.isChecked()
    assert not tab._rb_dark.isChecked()


def test_save_ai_persists(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "_CONFIG_PATH", tmp_path / "cfg.json")
    # QMessageBox.information é modal e bloquearia o teste — neutraliza
    monkeypatch.setattr(cfgmod.QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(cfgmod.QMessageBox, "warning", lambda *a, **k: None)
    tab = cfgmod.ConfiguracoesTab()
    qtbot.addWidget(tab)
    tab._ed_key.setText("SECRET")
    tab._cb_model.setCurrentText("gemini-2.5-pro")
    tab._save_ai()
    data = settings.load()
    assert data["api_key"] == "SECRET"
    assert data["gemini_model"] == "gemini-2.5-pro"


def test_theme_toggle_emits_signal(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "_CONFIG_PATH", tmp_path / "cfg.json")
    tab = cfgmod.ConfiguracoesTab()
    qtbot.addWidget(tab)
    with qtbot.waitSignal(tab.theme_changed, timeout=1000) as bl:
        tab._rb_light.setChecked(True)
    assert bl.args[0] == "light"
