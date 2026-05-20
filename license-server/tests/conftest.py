import os
from pathlib import Path
import pytest

@pytest.fixture
def temp_db(tmp_path: Path) -> str:
    from app.db import init_db
    db_path = str(tmp_path / "test_licenses.db")
    init_db(db_path)
    return db_path

@pytest.fixture(autouse=True)
def set_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ADMIN_PASSWORD", "test-password")
    monkeypatch.setenv("SECRET_KEY", "0123456789abcdef0123456789abcdef-test-only")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "licenses.db"))
