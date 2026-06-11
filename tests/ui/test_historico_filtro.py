import ui.history as history
import ui.tabs.historico as h


def _entry(**o):
    base = {"timestamp": "2026-05-25T10:00:00", "tipo": "ocorrencias",
            "inputs": ["a.pdf", "b.xlsx"], "output": "out.xlsx", "status": "ok",
            "duration_seconds": 1.2, "rows_processed": 3, "error": None}
    base.update(o)
    return base


def test_filtro_por_status(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(history, "_HISTORY_PATH", tmp_path / "hist.json")
    history.append(_entry(status="ok"))
    history.append(_entry(status="error"))
    tab = h.HistoricoTab()
    qtbot.addWidget(tab)
    assert tab._proxy.rowCount() == 2
    tab._cb_status.setCurrentIndex(2)  # "Erros"
    assert tab._proxy.rowCount() == 1
    tab._cb_status.setCurrentIndex(0)  # "Todos"
    assert tab._proxy.rowCount() == 2


def test_filtro_por_texto_busca_nome_de_arquivo(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(history, "_HISTORY_PATH", tmp_path / "hist.json")
    history.append(_entry(inputs=["jornada_maio.pdf", "pedido.xlsx"]))
    history.append(_entry(inputs=["nautilus.pdf", "cadastro.xls"], tipo="vt_caixa"))
    tab = h.HistoricoTab()
    qtbot.addWidget(tab)
    tab._ed_busca.setText("nautilus")
    assert tab._proxy.rowCount() == 1
    tab._ed_busca.setText("")
    assert tab._proxy.rowCount() == 2


def test_estado_vazio_alterna_com_dados(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(history, "_HISTORY_PATH", tmp_path / "hist.json")
    tab = h.HistoricoTab()
    qtbot.addWidget(tab)
    tab.show()
    assert tab._lbl_vazio.isVisible()
    assert not tab._view.isVisible()
    history.append(_entry())
    tab.refresh()
    assert not tab._lbl_vazio.isVisible()
    assert tab._view.isVisible()
