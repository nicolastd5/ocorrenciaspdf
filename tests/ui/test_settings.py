import json
from pathlib import Path
import pytest
from ui import settings


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "_CONFIG_PATH", tmp_path / ".ocorrencias_config.json")
    return tmp_path


def test_load_returns_defaults_when_file_missing(fake_home):
    data = settings.load()
    assert data["theme"] == "dark"
    assert data["gemini_model"] == "gemini-2.5-flash"
    assert data["codigos_ocorrencias"]


def test_save_persists_and_load_returns_it(fake_home):
    err = settings.save({"theme": "light"})
    assert err is None
    assert settings.load()["theme"] == "light"


def test_save_merges_with_existing(fake_home):
    settings.save({"theme": "light"})
    settings.save({"gemini_model": "gemini-2.5-pro"})
    data = settings.load()
    assert data["theme"] == "light"
    assert data["gemini_model"] == "gemini-2.5-pro"


def test_load_returns_defaults_on_corrupt_json(fake_home):
    settings.get_path().write_text("{not json", encoding="utf-8")
    data = settings.load()
    assert data == settings.DEFAULTS


def test_save_is_atomic(fake_home):
    settings.save({"theme": "light"})
    tmp = settings.get_path().with_suffix(".json.tmp")
    assert not tmp.exists()
