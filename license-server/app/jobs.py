import json
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from app.db import get_connection

VALID_STATUS = {"queued", "running", "awaiting_review", "done", "error", "expired"}


def create_job(db_path: str, user_id: int, kind: str, params: dict,
               retention_days: int = 7) -> str:
    job_id = uuid.uuid4().hex
    now = datetime.utcnow()
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO jobs (id, user_id, kind, params, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (job_id, user_id, kind, json.dumps(params),
             now.isoformat(), (now + timedelta(days=retention_days)).isoformat()),
        )
    return job_id


def get_job(db_path: str, job_id: str) -> Optional[dict]:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        return None
    j = dict(row)
    j["params"] = json.loads(j["params"]) if j["params"] else {}
    j["result"] = json.loads(j["result"]) if j["result"] else None
    return j


def set_progress(db_path: str, job_id: str, progress: int, message: str) -> None:
    with get_connection(db_path) as conn:
        conn.execute("UPDATE jobs SET progress = ?, message = ? WHERE id = ?",
                     (int(progress), message, job_id))


def set_status(db_path: str, job_id: str, status: str,
               result: Optional[dict] = None, error: Optional[str] = None) -> None:
    assert status in VALID_STATUS, f"Invalid status: {status}"
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE jobs SET status = ?, result = COALESCE(?, result), error = ? WHERE id = ?",
            (status, json.dumps(result) if result is not None else None, error, job_id),
        )


def job_dir(data_dir: str, job_id: str) -> Path:
    d = Path(data_dir) / "jobs" / job_id
    (d / "in").mkdir(parents=True, exist_ok=True)
    (d / "out").mkdir(parents=True, exist_ok=True)
    return d


def cleanup_expired(db_path: str, data_dir: str) -> int:
    now = datetime.utcnow().isoformat()
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT id FROM jobs WHERE expires_at < ? AND status != 'expired'", (now,)
        ).fetchall()
    count = 0
    for row in rows:
        d = Path(data_dir) / "jobs" / row["id"]
        shutil.rmtree(d, ignore_errors=True)
        with get_connection(db_path) as conn:
            conn.execute("UPDATE jobs SET status = 'expired' WHERE id = ?", (row["id"],))
        count += 1
    return count


def make_queue(redis_url: str):
    import redis as redis_lib
    from rq import Queue
    return Queue("default", connection=redis_lib.Redis.from_url(redis_url))


def enqueue_ocorrencias(queue, db_path: str, data_dir: str, job_id: str):
    from app import worker_tasks
    queue.enqueue(worker_tasks.run_ocorrencias, db_path, data_dir, job_id,
                  job_timeout=600)


def enqueue_vt_caixa(queue, db_path: str, data_dir: str, job_id: str):
    from app import worker_tasks
    queue.enqueue(worker_tasks.run_vt_caixa, db_path, data_dir, job_id,
                  job_timeout=600)
