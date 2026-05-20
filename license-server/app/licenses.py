from datetime import datetime, timezone
from typing import List, Optional
from app.db import get_connection
from app.models import License, ValidationLog

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _row_to_license(row) -> License:
    return License(
        id=row["id"], key=row["key"], client_name=row["client_name"],
        notes=row["notes"], revoked=bool(row["revoked"]),
        created_at=row["created_at"], revoked_at=row["revoked_at"],
    )

def create_license(db_path: str, *, key: str, client_name: str, notes: Optional[str]) -> License:
    created_at = _now_iso()
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO licenses (key, client_name, notes, revoked, created_at) VALUES (?, ?, ?, 0, ?)",
            (key, client_name, notes, created_at),
        )
        license_id = cur.lastrowid
        row = conn.execute("SELECT * FROM licenses WHERE id = ?", (license_id,)).fetchone()
    return _row_to_license(row)

def get_by_key(db_path: str, key: str) -> Optional[License]:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM licenses WHERE key = ?", (key,)).fetchone()
    return _row_to_license(row) if row else None

def revoke_license(db_path: str, license_id: int) -> None:
    revoked_at = _now_iso()
    with get_connection(db_path) as conn:
        conn.execute("UPDATE licenses SET revoked = 1, revoked_at = ? WHERE id = ?", (revoked_at, license_id))

def unrevoke_license(db_path: str, license_id: int) -> None:
    with get_connection(db_path) as conn:
        conn.execute("UPDATE licenses SET revoked = 0, revoked_at = NULL WHERE id = ?", (license_id,))

def list_all_licenses(db_path: str) -> List[License]:
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM licenses ORDER BY created_at DESC, id DESC").fetchall()
    return [_row_to_license(row) for row in rows]

def get_by_id(db_path: str, license_id: int) -> Optional[License]:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM licenses WHERE id = ?", (license_id,)).fetchone()
    return _row_to_license(row) if row else None

def _row_to_validation(row) -> ValidationLog:
    return ValidationLog(
        id=row["id"], license_id=row["license_id"],
        validated_at=row["validated_at"], ip=row["ip"], app_version=row["app_version"],
    )

def log_validation(db_path: str, *, license_id: int, ip: str, app_version: Optional[str]) -> None:
    validated_at = _now_iso()
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO validation_log (license_id, validated_at, ip, app_version) VALUES (?, ?, ?, ?)",
            (license_id, validated_at, ip, app_version),
        )

def list_validations_for_license(db_path: str, license_id: int) -> List[ValidationLog]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM validation_log WHERE license_id = ? ORDER BY validated_at DESC",
            (license_id,),
        ).fetchall()
    return [_row_to_validation(row) for row in rows]
