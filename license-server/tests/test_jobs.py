import pytest
from app import jobs, users
from app.db import init_db


def _create_user(db_path):
    """Create a test user with known id=1 for FK references."""
    try:
        return users.create_user(db_path, "test@test.com", "Test", "s3nh4forte")
    except ValueError:
        return 1


@pytest.fixture
def db_path(tmp_path):
    p = str(tmp_path / "test.db")
    init_db(p)
    _create_user(p)
    return p


def test_create_e_get(db_path):
    jid = jobs.create_job(db_path, user_id=1, kind="ocorrencias",
                          params={"codigos": ["FA", "AT"]})
    j = jobs.get_job(db_path, jid)
    assert j["status"] == "queued"
    assert j["kind"] == "ocorrencias"
    assert j["params"]["codigos"] == ["FA", "AT"]
    assert j["expires_at"] > j["created_at"]


def test_progresso_e_status(db_path):
    jid = jobs.create_job(db_path, 1, "ocorrencias", {})
    jobs.set_progress(db_path, jid, 50, "Cruzando dados...")
    j = jobs.get_job(db_path, jid)
    assert j["progress"] == 50 and j["message"] == "Cruzando dados..."
    jobs.set_status(db_path, jid, "done", result={"matched": 10})
    j = jobs.get_job(db_path, jid)
    assert j["status"] == "done" and j["result"]["matched"] == 10


def test_status_error(db_path):
    jid = jobs.create_job(db_path, 1, "vt_caixa", {})
    jobs.set_status(db_path, jid, "error", error="Colunas não encontradas")
    j = jobs.get_job(db_path, jid)
    assert j["status"] == "error" and "Colunas" in j["error"]


def test_job_dir(tmp_path):
    d = jobs.job_dir(str(tmp_path), "abc123")
    assert d.exists() and (d / "in").exists() and (d / "out").exists()
