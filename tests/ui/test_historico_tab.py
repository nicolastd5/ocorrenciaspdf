import ui.history as history
import ui.tabs.historico as h


def _entry(**o):
    base = {"timestamp": "2026-05-25T10:00:00", "tipo": "ocorrencias",
            "inputs": ["a.pdf", "b.xlsx"], "output": "out.xlsx", "status": "ok",
            "duration_seconds": 1.2, "rows_processed": 3, "error": None}
    base.update(o)
    return base


def test_model_shows_most_recent_first(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(history, "_HISTORY_PATH", tmp_path / "hist.json")
    history.append(_entry(timestamp="2026-01-01T00:00:00"))
    history.append(_entry(timestamp="2026-12-31T00:00:00"))
    tab = h.HistoricoTab()
    qtbot.addWidget(tab)
    # row 0 = mais recente
    assert tab._model.entry_at(0)["timestamp"] == "2026-12-31T00:00:00"
    assert tab._model.entry_at(1)["timestamp"] == "2026-01-01T00:00:00"
    assert tab._model.rowCount() == 2


def test_model_columns(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(history, "_HISTORY_PATH", tmp_path / "hist.json")
    history.append(_entry())
    tab = h.HistoricoTab()
    qtbot.addWidget(tab)
    assert tab._model.columnCount() == 6
    from PySide6.QtCore import Qt
    idx = tab._model.index(0, 1)
    assert tab._model.data(idx, Qt.DisplayRole) == "ocorrencias"


def test_remove_maps_inverted_index(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(history, "_HISTORY_PATH", tmp_path / "hist.json")
    history.append(_entry(timestamp="OLD"))
    history.append(_entry(timestamp="NEW"))
    tab = h.HistoricoTab()
    qtbot.addWidget(tab)
    # remover a linha visível 0 (a mais recente = NEW) deve apagar NEW, sobrando OLD
    tab._remove(0)
    rest = history.load()
    assert len(rest) == 1 and rest[0]["timestamp"] == "OLD"
