from pathlib import Path
import pytest
from ui import history


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "_HISTORY_PATH", tmp_path / ".ocorrencias_history.json")
    return tmp_path


def _entry(**over):
    base = {
        "timestamp": "2026-05-25T14:32:11",
        "tipo": "ocorrencias",
        "inputs": ["a.pdf", "b.xlsx"],
        "output": "out.xlsx",
        "status": "ok",
        "duration_seconds": 1.0,
        "rows_processed": 1,
        "error": None,
    }
    base.update(over)
    return base


def test_load_empty_when_missing(fake_home):
    assert history.load() == []


def test_append_persists(fake_home):
    assert history.append(_entry()) is None
    assert len(history.load()) == 1


def test_append_caps_at_max_entries_fifo(fake_home):
    for i in range(history.MAX_ENTRIES + 50):
        history.append(_entry(timestamp=str(i)))
    data = history.load()
    assert len(data) == history.MAX_ENTRIES
    assert data[0]["timestamp"] == "50"
    assert data[-1]["timestamp"] == str(history.MAX_ENTRIES + 49)


def test_remove_by_index(fake_home):
    history.append(_entry(timestamp="a"))
    history.append(_entry(timestamp="b"))
    history.remove(0)
    data = history.load()
    assert len(data) == 1
    assert data[0]["timestamp"] == "b"


def test_clear(fake_home):
    history.append(_entry())
    history.clear()
    assert history.load() == []


def test_load_returns_empty_on_corrupt(fake_home):
    history.get_path().write_text("not json", encoding="utf-8")
    assert history.load() == []
