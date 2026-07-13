import json
from datetime import datetime
from typing import Optional

from app.db import get_connection


def add(db_path: str, user_id: int, job_id: str, kind: str, status: str,
        input_names: list[str], counts: dict) -> int:
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO history (user_id, job_id, kind, status, input_names, counts, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, job_id, kind, status, json.dumps(input_names),
             json.dumps(counts), datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def list_for_user(db_path: str, user_id: int, q: str = "",
                  status: str = "") -> list[dict]:
    sql = "SELECT * FROM history WHERE user_id = ?"
    args: list = [user_id]
    if status:
        sql += " AND status = ?"
        args.append(status)
    if q:
        sql += " AND input_names LIKE ?"
        args.append(f"%{q}%")
    sql += " ORDER BY created_at DESC LIMIT 500"
    with get_connection(db_path) as conn:
        rows = conn.execute(sql, args).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["input_names"] = json.loads(d["input_names"] or "[]")
        d["counts"] = json.loads(d["counts"] or "{}")
        out.append(d)
    return out
