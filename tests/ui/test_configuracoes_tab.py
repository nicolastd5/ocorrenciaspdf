import ui.settings as settings
import ui.tabs.configuracoes as cfgmod


def test_constructs_and_reflects_theme(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "_CONFIG_PATH", tmp_path / "cfg.json")
    settings.save({"theme": "light"})
    tab = cfgmod.ConfiguracoesTab()
    qtbot.addWidget(tab)
    assert tab._rb_light.isChecked()
    assert not tab._rb_dark.isChecked()


def test_save_model_persists(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "_CONFIG_PATH", tmp_path / "cfg.json")
    tab = cfgmod.ConfiguracoesTab()
    qtbot.addWidget(tab)
    tab._cb_model.setCurrentText("gemini-2.5-pro")
    assert settings.load()["gemini_model"] == "gemini-2.5-pro"


def test_theme_toggle_emits_signal(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "_CONFIG_PATH", tmp_path / "cfg.json")
    tab = cfgmod.ConfiguracoesTab()
    qtbot.addWidget(tab)
    with qtbot.waitSignal(tab.theme_changed, timeout=1000) as bl:
        tab._rb_light.setChecked(True)
    assert bl.args[0] == "light"


def test_atualizar_status(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "_CONFIG_PATH", tmp_path / "cfg.json")
    tab = cfgmod.ConfiguracoesTab()
    qtbot.addWidget(tab)
    tab.atualizar_status("Conectado", "#238636", versao="1.64", gemini_ok=True)
    assert tab._lbl_conexao.text() == "Conectado"
    assert tab._lbl_versao.text() == "v1.64"
    assert tab._lbl_gemini.text() == "configurada"
