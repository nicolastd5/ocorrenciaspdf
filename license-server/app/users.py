import sqlite3
from datetime import datetime

from typing import Optional

from app.db import get_connection
from app.security import hash_password, verify_password


def create_user(db_path: str, email: str, name: str, password: str) -> int:
    email = email.strip().lower()
    try:
        with get_connection(db_path) as conn:
            cur = conn.execute(
                "INSERT INTO users (email, name, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (email, name.strip(), hash_password(password), datetime.utcnow().isoformat()),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError(f"email já cadastrado: {email}")


def authenticate(db_path: str, email: str, password: str) -> Optional[dict]:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ? AND active = 1",
            (email.strip().lower(),),
        ).fetchone()
    if row and verify_password(password, row["password_hash"]):
        return {"id": row["id"], "email": row["email"], "name": row["name"]}
    return None


def get_user(db_path: str, user_id: int) -> Optional[dict]:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def list_users(db_path: str) -> list[dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def set_active(db_path: str, user_id: int, active: bool) -> None:
    with get_connection(db_path) as conn:
        conn.execute("UPDATE users SET active = ? WHERE id = ?", (1 if active else 0, user_id))


def set_password(db_path: str, user_id: int, password: str) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(password), user_id),
        )


def mark_tutorial_seen(db_path: str, user_id: int) -> None:
    with get_connection(db_path) as conn:
        conn.execute("UPDATE users SET tutorial_seen = 1 WHERE id = ?", (user_id,))
