from datetime import datetime, timedelta

from app import jobs, users
from app.db import get_connection, init_db


def _create_user(db_path):
    try:
        return users.create_user(db_path, "test@test.com", "Test", "s3nh4forte")
    except ValueError:
        pass


def test_cleanup_apaga_expirados(tmp_path):
    db = str(tmp_path / "t.db")
    init_db(db)
    _create_user(db)
    data_dir = str(tmp_path / "data")

    vencido = jobs.create_job(db, 1, "ocorrencias", {})
    vigente = jobs.create_job(db, 1, "ocorrencias", {})
    d_vencido = jobs.job_dir(data_dir, vencido)
    d_vigente = jobs.job_dir(data_dir, vigente)
    (d_vencido / "in" / "a.pdf").write_bytes(b"x")
    (d_vigente / "in" / "b.pdf").write_bytes(b"x")

    passado = (datetime.utcnow() - timedelta(days=1)).isoformat()
    with get_connection(db) as conn:
        conn.execute("UPDATE jobs SET expires_at = ? WHERE id = ?", (passado, vencido))

    n = jobs.cleanup_expired(db, data_dir)
    assert n == 1
    assert not d_vencido.exists()
    assert d_vigente.exists()
    assert jobs.get_job(db, vencido)["status"] == "expired"
    assert jobs.get_job(db, vigente)["status"] == "queued"
