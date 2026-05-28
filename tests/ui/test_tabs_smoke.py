def test_ocorrencias_tab_constructs(qtbot, monkeypatch, tmp_path):
    from ui import settings, history
    monkeypatch.setattr(settings, "_CONFIG_PATH", tmp_path / "cfg.json")
    monkeypatch.setattr(history, "_HISTORY_PATH", tmp_path / "hist.json")
    from ui.tabs.ocorrencias import OcorrenciasTab
    tab = OcorrenciasTab()
    qtbot.addWidget(tab)
    assert tab is not None


def test_vt_caixa_tab_constructs(qtbot, monkeypatch, tmp_path):
    from ui import settings, history
    monkeypatch.setattr(settings, "_CONFIG_PATH", tmp_path / "cfg.json")
    monkeypatch.setattr(history, "_HISTORY_PATH", tmp_path / "hist.json")
    from ui.tabs.vt_caixa import VTCaixaTab
    tab = VTCaixaTab()
    qtbot.addWidget(tab)
    assert tab is not None


def test_historico_tab_constructs(qtbot, monkeypatch, tmp_path):
    from ui import history
    monkeypatch.setattr(history, "_HISTORY_PATH", tmp_path / "hist.json")
    from ui.tabs.historico import HistoricoTab
    tab = HistoricoTab()
    qtbot.addWidget(tab)
    assert tab is not None


def test_configuracoes_tab_constructs(qtbot, monkeypatch, tmp_path):
    from ui import settings
    monkeypatch.setattr(settings, "_CONFIG_PATH", tmp_path / "cfg.json")
    from ui.tabs.configuracoes import ConfiguracoesTab
    tab = ConfiguracoesTab()
    qtbot.addWidget(tab)
    assert tab is not None


def test_main_window_constructs(qtbot, monkeypatch, tmp_path):
    from ui import settings, history
    monkeypatch.setattr(settings, "_CONFIG_PATH", tmp_path / "cfg.json")
    monkeypatch.setattr(history, "_HISTORY_PATH", tmp_path / "hist.json")
    import ui.main_window as mw
    # evita checagem de rede real disparada pelo timer no construtor
    monkeypatch.setattr(mw.MainWindow, "_checar_conexao", lambda self: None)
    w = mw.MainWindow()
    qtbot.addWidget(w)
    assert w.windowTitle() == "Processador de Ocorrências"
    assert w._tabs.count() == 4
