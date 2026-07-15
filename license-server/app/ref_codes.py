"""Códigos de benefício e substituições de departamento criados pelos usuários.

Complementam (com precedência) as constantes embutidas
core.vt_caixa_processador.ProcessadorVTCaixa._CODIGOS_BENEFICIO/_DEPART_MAP.
"""
from datetime import datetime

from app.db import get_connection


def list_benefit_codes(db_path: str) -> list[dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM custom_benefit_codes ORDER BY operadora, valor_unitario"
        ).fetchall()
    return [dict(r) for r in rows]


def list_depart_subs(db_path: str) -> list[dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM custom_depart_subs ORDER BY original"
        ).fetchall()
    return [dict(r) for r in rows]


def add_benefit_code(db_path: str, user_id: int, operadora: str,
                     valor_unitario: str, codigo: str) -> int:
    operadora = (operadora or "").strip().upper()
    codigo = (codigo or "").strip()
    valor = (valor_unitario or "").strip() or None
    if not operadora or not codigo:
        raise ValueError("Operadora e código são obrigatórios.")
    with get_connection(db_path) as conn:
        dupe = conn.execute(
            "SELECT 1 FROM custom_benefit_codes "
            "WHERE operadora = ? AND valor_unitario IS ?",
            (operadora, valor),
        ).fetchone()
        if dupe:
            raise ValueError(f"Já existe um código para {operadora} com esse valor.")
        cur = conn.execute(
            "INSERT INTO custom_benefit_codes "
            "(operadora, valor_unitario, codigo, created_by, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (operadora, valor, codigo, user_id, datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def add_depart_sub(db_path: str, user_id: int, original: str, substituto: str) -> int:
    original = (original or "").strip()
    substituto = (substituto or "").strip()
    if not original or not substituto:
        raise ValueError("Departamento original e substituto são obrigatórios.")
    with get_connection(db_path) as conn:
        dupe = conn.execute(
            "SELECT 1 FROM custom_depart_subs WHERE original = ?", (original,)
        ).fetchone()
        if dupe:
            raise ValueError(f"Já existe uma substituição para {original}.")
        cur = conn.execute(
            "INSERT INTO custom_depart_subs "
            "(original, substituto, created_by, created_at) VALUES (?, ?, ?, ?)",
            (original, substituto, user_id, datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def delete_benefit_code(db_path: str, code_id: int) -> None:
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM custom_benefit_codes WHERE id = ?", (code_id,))


def delete_depart_sub(db_path: str, sub_id: int) -> None:
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM custom_depart_subs WHERE id = ?", (sub_id,))


def benefit_tuples(db_path: str) -> list[tuple]:
    """Formato de _CODIGOS_BENEFICIO: (operadora, valor|None, codigo)."""
    return [(r["operadora"], r["valor_unitario"], r["codigo"])
            for r in list_benefit_codes(db_path)]


def depart_dict(db_path: str) -> dict:
    """Formato de _DEPART_MAP: {original: substituto}."""
    return {r["original"]: r["substituto"] for r in list_depart_subs(db_path)}


# ── Ocorrência ──

def list_occurrence_codes(db_path: str) -> list[dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM custom_occurrence_codes ORDER BY codigo"
        ).fetchall()
    return [dict(r) for r in rows]


def add_occurrence_code(db_path: str, user_id: int, codigo: str,
                        descricao: str, com_quantidade: bool) -> int:
    from core.processador import ProcessadorOcorrencias

    codigo = (codigo or "").strip().upper()
    descricao = (descricao or "").strip()
    if not codigo or not descricao:
        raise ValueError("Código e descrição são obrigatórios.")
    if len(codigo) > 4:
        raise ValueError("O código deve ter no máximo 4 caracteres.")
    if codigo in ProcessadorOcorrencias.TODOS_CODIGOS:
        raise ValueError(f"{codigo} já é um código embutido do sistema.")
    with get_connection(db_path) as conn:
        dupe = conn.execute(
            "SELECT 1 FROM custom_occurrence_codes WHERE codigo = ?", (codigo,)
        ).fetchone()
        if dupe:
            raise ValueError(f"Já existe um código de ocorrência {codigo}.")
        cur = conn.execute(
            "INSERT INTO custom_occurrence_codes "
            "(codigo, descricao, com_quantidade, created_by, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (codigo, descricao, 1 if com_quantidade else 0,
             user_id, datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def delete_occurrence_code(db_path: str, code_id: int) -> None:
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM custom_occurrence_codes WHERE id = ?", (code_id,))


def occurrence_config(db_path: str) -> list[dict]:
    """Formato consumido por ProcessadorOcorrencias (config_extras)."""
    return [{"codigo": r["codigo"], "com_quantidade": bool(r["com_quantidade"])}
            for r in list_occurrence_codes(db_path)]
