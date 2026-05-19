# Validação de Acesso por Servidor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar sistema de validação de acesso por chave de licença: backend FastAPI + SQLite com painel admin HTML, e cliente embutido no app desktop que valida a cada abertura, com tolerância de 24h offline.

**Architecture:** Dois componentes independentes. Backend (`license-server/`) é projeto separado com FastAPI, SQLite, autenticação por sessão para o painel admin, endpoint público para validação. Cliente embutido em `ocorrenciaspdf/` consiste em `license_client.py` (lógica pura, testável) + `license_ui.py` (tkinter) + modificação no `app.py` para chamar bootstrap antes da janela principal.

**Tech Stack:**
- Backend: Python 3.10+, FastAPI, uvicorn, SQLite, Jinja2, bcrypt, slowapi, starlette-csrf, pytest, httpx
- Cliente: Python 3.10+, requests (HTTP), tkinter (já no app), pytest (já no app)

---

## Referência: spec original

Este plano implementa a spec [docs/superpowers/specs/2026-05-19-validacao-acesso-servidor-design.md](../specs/2026-05-19-validacao-acesso-servidor-design.md). Em caso de dúvida, a spec é a fonte da verdade.

## Estrutura final de arquivos

**Backend novo (`license-server/` — repositório separado, criado em pasta irmã):**

```
license-server/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── db.py
│   ├── models.py
│   ├── licenses.py
│   ├── keygen.py
│   ├── security.py
│   ├── routes_api.py
│   ├── routes_admin.py
│   └── templates/
│       ├── base.html
│       ├── login.html
│       ├── list.html
│       ├── new.html
│       └── detail.html
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_keygen.py
│   ├── test_licenses.py
│   ├── test_security.py
│   ├── test_routes_api.py
│   └── test_routes_admin.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

**Adições em `ocorrenciaspdf/` (repositório atual):**

```
ocorrenciaspdf/
├── license_client.py        (novo)
├── license_ui.py            (novo)
├── app.py                   (modificado)
└── tests/
    └── test_license_client.py   (novo)
```

---

# FASE 1 — Backend (license-server)

A Fase 1 entrega o backend completo rodando localmente. Ao final, é possível subir o servidor com `uvicorn app.main:app --reload`, fazer login no painel admin, criar e revogar chaves, e validar chaves via `curl` no endpoint público.

---

### Task 1: Inicializar projeto license-server

**Files:**
- Create: `../license-server/.gitignore`
- Create: `../license-server/README.md`
- Create: `../license-server/requirements.txt`
- Create: `../license-server/.env.example`
- Create: `../license-server/app/__init__.py`
- Create: `../license-server/tests/__init__.py`

- [ ] **Step 1: Criar diretórios**

```bash
mkdir -p ../license-server/app/templates
mkdir -p ../license-server/tests
```

- [ ] **Step 2: Criar `.gitignore`**

Conteúdo de `../license-server/.gitignore`:

```
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.venv/
venv/
*.db
*.db-journal
.env
.coverage
htmlcov/
```

- [ ] **Step 3: Criar `requirements.txt`**

Conteúdo de `../license-server/requirements.txt`:

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
jinja2==3.1.4
python-multipart==0.0.12
bcrypt==4.2.0
itsdangerous==2.2.0
slowapi==0.1.9
pytest==8.3.3
pytest-asyncio==0.24.0
httpx==0.27.2
```

- [ ] **Step 4: Criar `.env.example`**

Conteúdo de `../license-server/.env.example`:

```
ADMIN_PASSWORD=trocar-em-producao
SECRET_KEY=gerar-com-secrets-token-urlsafe-32-bytes
DB_PATH=licenses.db
```

- [ ] **Step 5: Criar `README.md`**

Conteúdo de `../license-server/README.md`:

````markdown
# License Server

Servidor de validação de licenças para o app Processador de Ocorrências.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -r requirements.txt
cp .env.example .env
# editar .env e definir ADMIN_PASSWORD e SECRET_KEY
```

## Rodar localmente

```bash
uvicorn app.main:app --reload
```

Painel admin: http://localhost:8000/admin/login

## Testes

```bash
pytest -v
```

## Deploy (resumo — executar manualmente quando VPS estiver pronta)

1. Instalar Python 3.10+, nginx, certbot no VPS
2. Configurar subdomínio DuckDNS apontando para IP do VPS
3. Obter certificado Let's Encrypt: `certbot --nginx -d <subdomain>.duckdns.org`
4. Criar systemd unit rodando `uvicorn app.main:app --host 127.0.0.1 --port 8000`
5. Configurar nginx como proxy reverso para 127.0.0.1:8000 com HTTPS
6. Configurar backup periódico: `sqlite3 licenses.db .backup backup.db` via cron
````

- [ ] **Step 6: Criar arquivos `__init__.py` vazios**

```bash
type nul > ../license-server/app/__init__.py
type nul > ../license-server/tests/__init__.py
```

- [ ] **Step 7: Commit inicial**

```bash
cd ../license-server
git init
git add .
git commit -m "chore: estrutura inicial do license-server"
cd ../ocorrenciaspdf
```

---

### Task 2: Geração de chaves (keygen)

**Files:**
- Create: `../license-server/app/keygen.py`
- Create: `../license-server/tests/test_keygen.py`

- [ ] **Step 1: Escrever teste falho**

Conteúdo de `../license-server/tests/test_keygen.py`:

```python
import re
from app.keygen import generate_key


KEY_PATTERN = re.compile(r"^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$")


def test_generate_key_matches_format():
    key = generate_key()
    assert KEY_PATTERN.match(key), f"Chave fora do formato: {key}"


def test_generate_key_uses_only_uppercase_and_digits():
    key = generate_key()
    raw = key.replace("-", "")
    assert all(c.isupper() or c.isdigit() for c in raw)


def test_generate_key_returns_unique_keys():
    keys = {generate_key() for _ in range(1000)}
    assert len(keys) == 1000, "Geração de 1000 chaves produziu duplicatas"
```

- [ ] **Step 2: Rodar teste e verificar que falha**

```bash
cd ../license-server
pytest tests/test_keygen.py -v
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'app.keygen'`

- [ ] **Step 3: Implementar keygen**

Conteúdo de `../license-server/app/keygen.py`:

```python
import secrets

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def generate_key() -> str:
    chars = [secrets.choice(ALPHABET) for _ in range(16)]
    groups = ["".join(chars[i:i + 4]) for i in range(0, 16, 4)]
    return "-".join(groups)
```

- [ ] **Step 4: Rodar teste e verificar que passa**

```bash
pytest tests/test_keygen.py -v
```

Esperado: PASS — 3 tests passed

- [ ] **Step 5: Commit**

```bash
git add app/keygen.py tests/test_keygen.py
git commit -m "feat: geração de chaves de licença formato XXXX-XXXX-XXXX-XXXX"
```

---

### Task 3: Config (carregar env vars)

**Files:**
- Create: `../license-server/app/config.py`

- [ ] **Step 1: Implementar config**

Conteúdo de `../license-server/app/config.py`:

```python
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    admin_password: str
    secret_key: str
    db_path: str


def load_settings() -> Settings:
    admin_password = os.environ.get("ADMIN_PASSWORD")
    secret_key = os.environ.get("SECRET_KEY")
    db_path = os.environ.get("DB_PATH", "licenses.db")

    if not admin_password:
        raise RuntimeError("ADMIN_PASSWORD environment variable is required")
    if not secret_key or len(secret_key) < 32:
        raise RuntimeError("SECRET_KEY environment variable must be at least 32 chars")

    return Settings(
        admin_password=admin_password,
        secret_key=secret_key,
        db_path=db_path,
    )
```

- [ ] **Step 2: Commit**

```bash
git add app/config.py
git commit -m "feat: carregamento de configuração via env vars"
```

> Sem testes próprios — `config.py` é testado indiretamente pelos testes que usam `Settings` via fixture.

---

### Task 4: Modelos de dados

**Files:**
- Create: `../license-server/app/models.py`

- [ ] **Step 1: Implementar modelos**

Conteúdo de `../license-server/app/models.py`:

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class License:
    id: int
    key: str
    client_name: str
    notes: Optional[str]
    revoked: bool
    created_at: str
    revoked_at: Optional[str]


@dataclass
class ValidationLog:
    id: int
    license_id: int
    validated_at: str
    ip: str
    app_version: Optional[str]
```

- [ ] **Step 2: Commit**

```bash
git add app/models.py
git commit -m "feat: dataclasses License e ValidationLog"
```

---

### Task 5: Camada de banco de dados (db.py)

**Files:**
- Create: `../license-server/app/db.py`

- [ ] **Step 1: Implementar db.py**

Conteúdo de `../license-server/app/db.py`:

```python
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS licenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    client_name TEXT NOT NULL,
    notes TEXT,
    revoked INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    revoked_at TEXT
);

CREATE TABLE IF NOT EXISTS validation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_id INTEGER NOT NULL REFERENCES licenses(id),
    validated_at TEXT NOT NULL,
    ip TEXT NOT NULL,
    app_version TEXT
);

CREATE INDEX IF NOT EXISTS idx_validation_log_license_id
    ON validation_log(license_id);
"""


def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


@contextmanager
def get_connection(db_path: str) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

- [ ] **Step 2: Commit**

```bash
git add app/db.py
git commit -m "feat: schema SQLite e helper de conexão"
```

---

### Task 6: Conftest com fixture de DB temporário

**Files:**
- Create: `../license-server/tests/conftest.py`

- [ ] **Step 1: Implementar conftest**

Conteúdo de `../license-server/tests/conftest.py`:

```python
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
    monkeypatch.setenv(
        "SECRET_KEY",
        "0123456789abcdef0123456789abcdef-test-only",
    )
    monkeypatch.setenv("DB_PATH", str(tmp_path / "licenses.db"))
```

- [ ] **Step 2: Commit**

```bash
git add tests/conftest.py
git commit -m "test: fixtures de DB temporário e env vars"
```

---

### Task 7: CRUD de licenças — create

**Files:**
- Create: `../license-server/app/licenses.py`
- Create: `../license-server/tests/test_licenses.py`

- [ ] **Step 1: Escrever teste falho**

Conteúdo inicial de `../license-server/tests/test_licenses.py`:

```python
import pytest

from app.licenses import create_license, get_by_key
from app.models import License


def test_create_license_returns_license_with_id(temp_db):
    lic = create_license(temp_db, key="ABCD-EFGH-IJKL-MNOP", client_name="Cliente A", notes="anotação")
    assert isinstance(lic, License)
    assert lic.id > 0
    assert lic.key == "ABCD-EFGH-IJKL-MNOP"
    assert lic.client_name == "Cliente A"
    assert lic.notes == "anotação"
    assert lic.revoked is False
    assert lic.created_at  # ISO 8601 não vazio
    assert lic.revoked_at is None


def test_create_license_duplicate_key_raises(temp_db):
    create_license(temp_db, key="ABCD-EFGH-IJKL-MNOP", client_name="A", notes=None)
    with pytest.raises(Exception):
        create_license(temp_db, key="ABCD-EFGH-IJKL-MNOP", client_name="B", notes=None)
```

- [ ] **Step 2: Rodar teste e verificar que falha**

```bash
pytest tests/test_licenses.py -v
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'app.licenses'`

- [ ] **Step 3: Implementar `create_license`**

Conteúdo inicial de `../license-server/app/licenses.py`:

```python
from datetime import datetime, timezone
from typing import Optional

from app.db import get_connection
from app.models import License


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row_to_license(row) -> License:
    return License(
        id=row["id"],
        key=row["key"],
        client_name=row["client_name"],
        notes=row["notes"],
        revoked=bool(row["revoked"]),
        created_at=row["created_at"],
        revoked_at=row["revoked_at"],
    )


def create_license(db_path: str, *, key: str, client_name: str, notes: Optional[str]) -> License:
    created_at = _now_iso()
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO licenses (key, client_name, notes, revoked, created_at) "
            "VALUES (?, ?, ?, 0, ?)",
            (key, client_name, notes, created_at),
        )
        license_id = cur.lastrowid
        row = conn.execute(
            "SELECT * FROM licenses WHERE id = ?", (license_id,)
        ).fetchone()
    return _row_to_license(row)


def get_by_key(db_path: str, key: str) -> Optional[License]:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM licenses WHERE key = ?", (key,)
        ).fetchone()
    return _row_to_license(row) if row else None
```

- [ ] **Step 4: Rodar testes e verificar que passam**

```bash
pytest tests/test_licenses.py -v
```

Esperado: PASS — 2 tests passed

- [ ] **Step 5: Commit**

```bash
git add app/licenses.py tests/test_licenses.py
git commit -m "feat: create_license e get_by_key em SQLite"
```

---

### Task 8: CRUD de licenças — revoke / unrevoke / list_all

**Files:**
- Modify: `../license-server/app/licenses.py`
- Modify: `../license-server/tests/test_licenses.py`

- [ ] **Step 1: Adicionar testes falhos**

Adicionar ao final de `../license-server/tests/test_licenses.py`:

```python
from app.licenses import revoke_license, unrevoke_license, list_all_licenses


def test_revoke_marks_license_as_revoked(temp_db):
    lic = create_license(temp_db, key="AAAA-BBBB-CCCC-DDDD", client_name="X", notes=None)
    revoke_license(temp_db, lic.id)
    updated = get_by_key(temp_db, "AAAA-BBBB-CCCC-DDDD")
    assert updated.revoked is True
    assert updated.revoked_at is not None


def test_unrevoke_clears_revoked_flag(temp_db):
    lic = create_license(temp_db, key="EEEE-FFFF-GGGG-HHHH", client_name="Y", notes=None)
    revoke_license(temp_db, lic.id)
    unrevoke_license(temp_db, lic.id)
    updated = get_by_key(temp_db, "EEEE-FFFF-GGGG-HHHH")
    assert updated.revoked is False
    assert updated.revoked_at is None


def test_list_all_returns_all_licenses_ordered_by_created_at_desc(temp_db):
    create_license(temp_db, key="1111-1111-1111-1111", client_name="A", notes=None)
    create_license(temp_db, key="2222-2222-2222-2222", client_name="B", notes=None)
    all_licenses = list_all_licenses(temp_db)
    assert len(all_licenses) == 2
    # Mais recente primeiro
    assert all_licenses[0].key == "2222-2222-2222-2222"
    assert all_licenses[1].key == "1111-1111-1111-1111"
```

- [ ] **Step 2: Rodar testes e verificar que falham**

```bash
pytest tests/test_licenses.py -v
```

Esperado: FAIL com `ImportError: cannot import name 'revoke_license'`

- [ ] **Step 3: Adicionar funções a `app/licenses.py`**

Adicionar ao final de `../license-server/app/licenses.py`:

```python
from typing import List


def revoke_license(db_path: str, license_id: int) -> None:
    revoked_at = _now_iso()
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE licenses SET revoked = 1, revoked_at = ? WHERE id = ?",
            (revoked_at, license_id),
        )


def unrevoke_license(db_path: str, license_id: int) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE licenses SET revoked = 0, revoked_at = NULL WHERE id = ?",
            (license_id,),
        )


def list_all_licenses(db_path: str) -> List[License]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM licenses ORDER BY created_at DESC"
        ).fetchall()
    return [_row_to_license(row) for row in rows]


def get_by_id(db_path: str, license_id: int) -> Optional[License]:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM licenses WHERE id = ?", (license_id,)
        ).fetchone()
    return _row_to_license(row) if row else None
```

- [ ] **Step 4: Rodar testes e verificar que passam**

```bash
pytest tests/test_licenses.py -v
```

Esperado: PASS — 5 tests passed

- [ ] **Step 5: Commit**

```bash
git add app/licenses.py tests/test_licenses.py
git commit -m "feat: revoke/unrevoke/list_all/get_by_id de licenças"
```

---

### Task 9: Log de validação

**Files:**
- Modify: `../license-server/app/licenses.py`
- Modify: `../license-server/tests/test_licenses.py`

- [ ] **Step 1: Adicionar testes falhos**

Adicionar ao final de `../license-server/tests/test_licenses.py`:

```python
from app.licenses import log_validation, list_validations_for_license


def test_log_validation_creates_entry(temp_db):
    lic = create_license(temp_db, key="LOGT-EST1-LOGT-EST1", client_name="L", notes=None)
    log_validation(temp_db, license_id=lic.id, ip="192.168.0.1", app_version="1.34")
    entries = list_validations_for_license(temp_db, lic.id)
    assert len(entries) == 1
    assert entries[0].license_id == lic.id
    assert entries[0].ip == "192.168.0.1"
    assert entries[0].app_version == "1.34"
    assert entries[0].validated_at  # ISO 8601 não vazio
```

- [ ] **Step 2: Rodar teste e verificar que falha**

```bash
pytest tests/test_licenses.py::test_log_validation_creates_entry -v
```

Esperado: FAIL com `ImportError: cannot import name 'log_validation'`

- [ ] **Step 3: Adicionar funções a `app/licenses.py`**

Adicionar ao final de `../license-server/app/licenses.py`:

```python
from app.models import ValidationLog


def _row_to_validation(row) -> ValidationLog:
    return ValidationLog(
        id=row["id"],
        license_id=row["license_id"],
        validated_at=row["validated_at"],
        ip=row["ip"],
        app_version=row["app_version"],
    )


def log_validation(db_path: str, *, license_id: int, ip: str, app_version: Optional[str]) -> None:
    validated_at = _now_iso()
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO validation_log (license_id, validated_at, ip, app_version) "
            "VALUES (?, ?, ?, ?)",
            (license_id, validated_at, ip, app_version),
        )


def list_validations_for_license(db_path: str, license_id: int) -> List[ValidationLog]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM validation_log WHERE license_id = ? "
            "ORDER BY validated_at DESC",
            (license_id,),
        ).fetchall()
    return [_row_to_validation(row) for row in rows]
```

- [ ] **Step 4: Rodar testes e verificar que passam**

```bash
pytest tests/test_licenses.py -v
```

Esperado: PASS — 6 tests passed

- [ ] **Step 5: Commit**

```bash
git add app/licenses.py tests/test_licenses.py
git commit -m "feat: log_validation e list_validations_for_license"
```

---

### Task 10: Segurança — hash de senha

**Files:**
- Create: `../license-server/app/security.py`
- Create: `../license-server/tests/test_security.py`

- [ ] **Step 1: Escrever testes falhos**

Conteúdo de `../license-server/tests/test_security.py`:

```python
from app.security import hash_password, verify_password


def test_hash_password_returns_non_plaintext():
    pw = "minha-senha-super-secreta"
    h = hash_password(pw)
    assert h != pw
    assert len(h) > 20


def test_verify_password_matches_hash():
    pw = "outra-senha-123"
    h = hash_password(pw)
    assert verify_password(pw, h) is True


def test_verify_password_rejects_wrong_password():
    h = hash_password("senha-original")
    assert verify_password("senha-errada", h) is False


def test_hash_password_produces_different_hash_each_time():
    pw = "mesma-senha"
    assert hash_password(pw) != hash_password(pw)
```

- [ ] **Step 2: Rodar testes e verificar que falham**

```bash
pytest tests/test_security.py -v
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'app.security'`

- [ ] **Step 3: Implementar hash/verify**

Conteúdo inicial de `../license-server/app/security.py`:

```python
import bcrypt


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False
```

- [ ] **Step 4: Rodar testes e verificar que passam**

```bash
pytest tests/test_security.py -v
```

Esperado: PASS — 4 tests passed

- [ ] **Step 5: Commit**

```bash
git add app/security.py tests/test_security.py
git commit -m "feat: hash e verify de senha com bcrypt"
```

---

### Task 11: Segurança — CSRF token

**Files:**
- Modify: `../license-server/app/security.py`
- Modify: `../license-server/tests/test_security.py`

- [ ] **Step 1: Adicionar testes falhos**

Adicionar ao final de `../license-server/tests/test_security.py`:

```python
from app.security import generate_csrf_token, verify_csrf_token


def test_generate_csrf_token_is_non_empty_string():
    token = generate_csrf_token()
    assert isinstance(token, str)
    assert len(token) >= 32


def test_verify_csrf_token_accepts_matching_tokens():
    token = generate_csrf_token()
    assert verify_csrf_token(token, token) is True


def test_verify_csrf_token_rejects_mismatch():
    a = generate_csrf_token()
    b = generate_csrf_token()
    assert verify_csrf_token(a, b) is False


def test_verify_csrf_token_rejects_none_or_empty():
    token = generate_csrf_token()
    assert verify_csrf_token(token, None) is False
    assert verify_csrf_token(None, token) is False
    assert verify_csrf_token("", token) is False
```

- [ ] **Step 2: Rodar testes e verificar que falham**

```bash
pytest tests/test_security.py -v
```

Esperado: FAIL com `ImportError: cannot import name 'generate_csrf_token'`

- [ ] **Step 3: Adicionar funções de CSRF**

Adicionar ao final de `../license-server/app/security.py`:

```python
import hmac
import secrets
from typing import Optional


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def verify_csrf_token(session_token: Optional[str], form_token: Optional[str]) -> bool:
    if not session_token or not form_token:
        return False
    return hmac.compare_digest(session_token, form_token)
```

- [ ] **Step 4: Rodar testes e verificar que passam**

```bash
pytest tests/test_security.py -v
```

Esperado: PASS — 8 tests passed

- [ ] **Step 5: Commit**

```bash
git add app/security.py tests/test_security.py
git commit -m "feat: geração e verificação de tokens CSRF"
```

---

### Task 12: Segurança — máscara de chave para logs

**Files:**
- Modify: `../license-server/app/security.py`
- Modify: `../license-server/tests/test_security.py`

- [ ] **Step 1: Adicionar testes falhos**

Adicionar ao final de `../license-server/tests/test_security.py`:

```python
from app.security import mask_key


def test_mask_key_keeps_first_four_chars():
    assert mask_key("A3F2-9K1P-XQ7M-BN4T") == "A3F2-***"


def test_mask_key_handles_short_input():
    assert mask_key("A3") == "***"
    assert mask_key("") == "***"
    assert mask_key(None) == "***"
```

- [ ] **Step 2: Rodar testes e verificar que falham**

```bash
pytest tests/test_security.py -v
```

Esperado: FAIL com `ImportError: cannot import name 'mask_key'`

- [ ] **Step 3: Implementar mask_key**

Adicionar ao final de `../license-server/app/security.py`:

```python
def mask_key(key: Optional[str]) -> str:
    if not key or len(key) < 4:
        return "***"
    return f"{key[:4]}-***"
```

- [ ] **Step 4: Rodar testes e verificar que passam**

```bash
pytest tests/test_security.py -v
```

Esperado: PASS — 10 tests passed

- [ ] **Step 5: Commit**

```bash
git add app/security.py tests/test_security.py
git commit -m "feat: mask_key para logs sem expor chave completa"
```

---

### Task 13: FastAPI app esqueleto

**Files:**
- Create: `../license-server/app/main.py`

- [ ] **Step 1: Implementar app esqueleto**

Conteúdo inicial de `../license-server/app/main.py`:

```python
import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.sessions import SessionMiddleware

from app.config import load_settings
from app.db import init_db


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("license-server")


def create_app() -> FastAPI:
    settings = load_settings()
    init_db(settings.db_path)

    limiter = Limiter(key_func=get_remote_address)
    fastapi_app = FastAPI(title="License Server")
    fastapi_app.state.limiter = limiter
    fastapi_app.state.settings = settings

    fastapi_app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        https_only=False,  # invertido para True quando deployar com HTTPS
        same_site="lax",
        max_age=7 * 24 * 60 * 60,
    )

    @fastapi_app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request, exc):
        return JSONResponse(
            status_code=429,
            content={"error": "rate_limit_exceeded"},
        )

    @fastapi_app.get("/")
    async def root():
        return {"service": "license-server", "status": "ok"}

    return fastapi_app


app = create_app()
```

- [ ] **Step 2: Verificar que app inicia**

```bash
set ADMIN_PASSWORD=teste-local && set SECRET_KEY=0123456789abcdef0123456789abcdef-test-only && set DB_PATH=test.db && python -c "from app.main import app; print('OK')"
```

Esperado: `OK` impresso. Sem stack trace.

- [ ] **Step 3: Limpar arquivo de DB de teste**

```bash
del test.db
```

- [ ] **Step 4: Commit**

```bash
git add app/main.py
git commit -m "feat: esqueleto do app FastAPI com middleware de sessão e rate limit"
```

---

### Task 14: Endpoint público `/api/validate`

**Files:**
- Create: `../license-server/app/routes_api.py`
- Create: `../license-server/tests/test_routes_api.py`
- Modify: `../license-server/app/main.py`

- [ ] **Step 1: Escrever testes falhos**

Conteúdo de `../license-server/tests/test_routes_api.py`:

```python
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, tmp_path):
    db_path = str(tmp_path / "licenses.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("ADMIN_PASSWORD", "test-password")
    monkeypatch.setenv(
        "SECRET_KEY",
        "0123456789abcdef0123456789abcdef-test-only",
    )
    # Re-importar para que create_app rode com env atualizada
    import importlib
    import app.main
    importlib.reload(app.main)
    return TestClient(app.main.app), db_path


def test_validate_unknown_key_returns_valid_false(client):
    c, _ = client
    resp = c.post("/api/validate", json={"key": "ZZZZ-ZZZZ-ZZZZ-ZZZZ", "app_version": "1.34"})
    assert resp.status_code == 200
    assert resp.json() == {"valid": False, "reason": "not_found"}


def test_validate_active_key_returns_valid_true(client):
    c, db_path = client
    from app.licenses import create_license
    create_license(db_path, key="VALI-DKEY-VALI-DKEY", client_name="Fulano", notes=None)
    resp = c.post("/api/validate", json={"key": "VALI-DKEY-VALI-DKEY", "app_version": "1.34"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["client_name"] == "Fulano"


def test_validate_revoked_key_returns_revoked(client):
    c, db_path = client
    from app.licenses import create_license, revoke_license
    lic = create_license(db_path, key="REVO-KEDK-REVO-KEDK", client_name="X", notes=None)
    revoke_license(db_path, lic.id)
    resp = c.post("/api/validate", json={"key": "REVO-KEDK-REVO-KEDK", "app_version": "1.34"})
    assert resp.status_code == 200
    assert resp.json() == {"valid": False, "reason": "revoked"}


def test_validate_invalid_format_returns_not_found(client):
    c, _ = client
    resp = c.post("/api/validate", json={"key": "formato-errado", "app_version": "1.34"})
    assert resp.status_code == 200
    assert resp.json() == {"valid": False, "reason": "not_found"}


def test_validate_logs_successful_validation(client):
    c, db_path = client
    from app.licenses import create_license, list_validations_for_license
    lic = create_license(db_path, key="LOGM-EVAL-LOGM-EVAL", client_name="Y", notes=None)
    c.post("/api/validate", json={"key": "LOGM-EVAL-LOGM-EVAL", "app_version": "1.34"})
    entries = list_validations_for_license(db_path, lic.id)
    assert len(entries) == 1
    assert entries[0].app_version == "1.34"


def test_validate_does_not_log_failed_validation(client):
    c, db_path = client
    from app.licenses import create_license, list_validations_for_license, revoke_license
    lic = create_license(db_path, key="REVO-LOGM-REVO-LOGM", client_name="Z", notes=None)
    revoke_license(db_path, lic.id)
    c.post("/api/validate", json={"key": "REVO-LOGM-REVO-LOGM", "app_version": "1.34"})
    entries = list_validations_for_license(db_path, lic.id)
    assert len(entries) == 0


def test_validate_malformed_body_returns_not_found(client):
    c, _ = client
    resp = c.post("/api/validate", json={"foo": "bar"})
    # Pydantic devolve 422 para body inválido; aceitamos isso
    # OU implementação intercepta e converte; ambos são defesa em profundidade.
    # Aqui assumimos a conversão explícita para reason=not_found:
    assert resp.status_code in (200, 422)
    if resp.status_code == 200:
        assert resp.json() == {"valid": False, "reason": "not_found"}
```

- [ ] **Step 2: Rodar testes e verificar que falham**

```bash
pytest tests/test_routes_api.py -v
```

Esperado: FAIL — endpoint `/api/validate` não existe (404)

- [ ] **Step 3: Implementar `routes_api.py`**

Conteúdo de `../license-server/app/routes_api.py`:

```python
import logging
import re
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, ValidationError

from app.licenses import get_by_key, log_validation
from app.security import mask_key


router = APIRouter(prefix="/api")
logger = logging.getLogger("license-server.api")

KEY_PATTERN = re.compile(r"^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$")


class ValidateBody(BaseModel):
    key: str
    app_version: Optional[str] = None


def _client_ip(request: Request) -> str:
    if request.client:
        return request.client.host
    return "unknown"


@router.post("/validate")
async def validate(request: Request) -> dict:
    try:
        raw = await request.json()
        body = ValidateBody(**raw)
    except (ValidationError, ValueError, TypeError):
        logger.info("validate: body inválido de %s", _client_ip(request))
        return {"valid": False, "reason": "not_found"}

    if not KEY_PATTERN.match(body.key):
        logger.info("validate: formato inválido %s de %s", mask_key(body.key), _client_ip(request))
        return {"valid": False, "reason": "not_found"}

    settings = request.app.state.settings
    lic = get_by_key(settings.db_path, body.key)
    if lic is None:
        logger.info("validate: not_found %s de %s", mask_key(body.key), _client_ip(request))
        return {"valid": False, "reason": "not_found"}

    if lic.revoked:
        logger.info("validate: revoked %s de %s", mask_key(body.key), _client_ip(request))
        return {"valid": False, "reason": "revoked"}

    log_validation(
        settings.db_path,
        license_id=lic.id,
        ip=_client_ip(request),
        app_version=body.app_version,
    )
    logger.info("validate: OK %s de %s", mask_key(body.key), _client_ip(request))
    return {"valid": True, "client_name": lic.client_name}
```

- [ ] **Step 4: Registrar router em `main.py`**

Modificar `../license-server/app/main.py` para incluir o router. Adicionar `from app.routes_api import router as api_router` no topo (junto aos imports) e, dentro de `create_app()`, após adicionar o middleware de sessão, antes do `@fastapi_app.get("/")`:

```python
    fastapi_app.include_router(api_router)
```

O arquivo `main.py` completo ficará:

```python
import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.sessions import SessionMiddleware

from app.config import load_settings
from app.db import init_db
from app.routes_api import router as api_router


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("license-server")


def create_app() -> FastAPI:
    settings = load_settings()
    init_db(settings.db_path)

    limiter = Limiter(key_func=get_remote_address)
    fastapi_app = FastAPI(title="License Server")
    fastapi_app.state.limiter = limiter
    fastapi_app.state.settings = settings

    fastapi_app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        https_only=False,
        same_site="lax",
        max_age=7 * 24 * 60 * 60,
    )

    fastapi_app.include_router(api_router)

    @fastapi_app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request, exc):
        return JSONResponse(
            status_code=429,
            content={"error": "rate_limit_exceeded"},
        )

    @fastapi_app.get("/")
    async def root():
        return {"service": "license-server", "status": "ok"}

    return fastapi_app


app = create_app()
```

- [ ] **Step 5: Rodar testes e verificar que passam**

```bash
pytest tests/test_routes_api.py -v
```

Esperado: PASS — 7 tests passed

- [ ] **Step 6: Commit**

```bash
git add app/routes_api.py app/main.py tests/test_routes_api.py
git commit -m "feat: endpoint POST /api/validate com defesa contra enumeração"
```

---

### Task 15: Rate limit no `/api/validate`

**Files:**
- Modify: `../license-server/app/routes_api.py`
- Modify: `../license-server/tests/test_routes_api.py`

- [ ] **Step 1: Adicionar teste de rate limit**

Adicionar ao final de `../license-server/tests/test_routes_api.py`:

```python
def test_validate_rate_limit_blocks_after_60_per_minute(client):
    c, _ = client
    # Primeiras 60 devem passar
    for _ in range(60):
        resp = c.post("/api/validate", json={"key": "ZZZZ-ZZZZ-ZZZZ-ZZZZ", "app_version": "x"})
        assert resp.status_code == 200
    # 61ª deve ser bloqueada
    resp = c.post("/api/validate", json={"key": "ZZZZ-ZZZZ-ZZZZ-ZZZZ", "app_version": "x"})
    assert resp.status_code == 429
```

- [ ] **Step 2: Rodar teste e verificar que falha**

```bash
pytest tests/test_routes_api.py::test_validate_rate_limit_blocks_after_60_per_minute -v
```

Esperado: FAIL — todas as 61 retornam 200

- [ ] **Step 3: Aplicar decorator de rate limit**

Modificar o endpoint em `../license-server/app/routes_api.py` para usar o limiter. Adicionar import e decorator:

```python
from slowapi.util import get_remote_address


@router.post("/validate")
async def validate(request: Request) -> dict:
    ...
```

Substituir pela versão com limite:

```python
@router.post("/validate")
async def validate(request: Request) -> dict:
    limiter = request.app.state.limiter
    limit_decorator = limiter.limit("60/minute")
    # slowapi exige aplicação via decorator no nível da rota — usamos middleware approach abaixo
    ...
```

**Abordagem correta**: slowapi requer o decorator na função. Reescrever o endpoint:

Substituir TODO o conteúdo de `../license-server/app/routes_api.py` por:

```python
import logging
import re
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, ValidationError
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.licenses import get_by_key, log_validation
from app.security import mask_key


router = APIRouter(prefix="/api")
logger = logging.getLogger("license-server.api")
limiter = Limiter(key_func=get_remote_address)

KEY_PATTERN = re.compile(r"^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$")


class ValidateBody(BaseModel):
    key: str
    app_version: Optional[str] = None


def _client_ip(request: Request) -> str:
    if request.client:
        return request.client.host
    return "unknown"


@router.post("/validate")
@limiter.limit("60/minute")
async def validate(request: Request) -> dict:
    try:
        raw = await request.json()
        body = ValidateBody(**raw)
    except (ValidationError, ValueError, TypeError):
        logger.info("validate: body inválido de %s", _client_ip(request))
        return {"valid": False, "reason": "not_found"}

    if not KEY_PATTERN.match(body.key):
        logger.info("validate: formato inválido %s de %s", mask_key(body.key), _client_ip(request))
        return {"valid": False, "reason": "not_found"}

    settings = request.app.state.settings
    lic = get_by_key(settings.db_path, body.key)
    if lic is None:
        logger.info("validate: not_found %s de %s", mask_key(body.key), _client_ip(request))
        return {"valid": False, "reason": "not_found"}

    if lic.revoked:
        logger.info("validate: revoked %s de %s", mask_key(body.key), _client_ip(request))
        return {"valid": False, "reason": "revoked"}

    log_validation(
        settings.db_path,
        license_id=lic.id,
        ip=_client_ip(request),
        app_version=body.app_version,
    )
    logger.info("validate: OK %s de %s", mask_key(body.key), _client_ip(request))
    return {"valid": True, "client_name": lic.client_name}
```

Substituir `../license-server/app/main.py` — trocar a criação do limiter para usar o do router_api. Substituir conteúdo de `main.py`:

```python
import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from app.config import load_settings
from app.db import init_db
from app.routes_api import router as api_router, limiter as api_limiter


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("license-server")


def create_app() -> FastAPI:
    settings = load_settings()
    init_db(settings.db_path)

    fastapi_app = FastAPI(title="License Server")
    fastapi_app.state.limiter = api_limiter
    fastapi_app.state.settings = settings

    fastapi_app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        https_only=False,
        same_site="lax",
        max_age=7 * 24 * 60 * 60,
    )

    fastapi_app.include_router(api_router)

    @fastapi_app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request, exc):
        return JSONResponse(
            status_code=429,
            content={"error": "rate_limit_exceeded"},
        )

    @fastapi_app.get("/")
    async def root():
        return {"service": "license-server", "status": "ok"}

    return fastapi_app


app = create_app()
```

- [ ] **Step 4: Rodar todos os testes da API**

```bash
pytest tests/test_routes_api.py -v
```

Esperado: PASS — 8 tests passed (todos incluindo o rate limit)

- [ ] **Step 5: Commit**

```bash
git add app/routes_api.py app/main.py tests/test_routes_api.py
git commit -m "feat: rate limit 60/min/IP em /api/validate"
```

---

### Task 16: Auth helpers para painel admin

**Files:**
- Modify: `../license-server/app/security.py`

- [ ] **Step 1: Implementar dependency de auth**

Adicionar ao final de `../license-server/app/security.py`:

```python
from fastapi import HTTPException, Request, status
from fastapi.responses import RedirectResponse


def is_authenticated(request: Request) -> bool:
    return request.session.get("admin_authenticated") is True


def require_admin(request: Request):
    if not is_authenticated(request):
        # FastAPI vai converter HTTPException em response;
        # aqui preferimos redirect, então levantamos exceção customizada tratada na rota
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/admin/login"},
        )


def get_or_create_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = generate_csrf_token()
        request.session["csrf_token"] = token
    return token
```

- [ ] **Step 2: Commit**

```bash
git add app/security.py
git commit -m "feat: helpers de autenticação e CSRF para painel admin"
```

> Testes dessas funções vêm com os testes de rotas admin na Task 18.

---

### Task 17: Templates HTML do painel admin

**Files:**
- Create: `../license-server/app/templates/base.html`
- Create: `../license-server/app/templates/login.html`
- Create: `../license-server/app/templates/list.html`
- Create: `../license-server/app/templates/new.html`
- Create: `../license-server/app/templates/detail.html`

- [ ] **Step 1: Criar `base.html`**

Conteúdo de `../license-server/app/templates/base.html`:

```html
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>{% block title %}License Server{% endblock %}</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
               max-width: 900px; margin: 2em auto; padding: 0 1em; color: #222; }
        h1 { border-bottom: 2px solid #333; padding-bottom: .3em; }
        nav { margin-bottom: 1.5em; }
        nav a { margin-right: 1em; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: .5em; border-bottom: 1px solid #ddd; text-align: left; }
        th { background: #f5f5f5; }
        .revoked { color: #b00; }
        .active { color: #060; }
        .btn { display: inline-block; padding: .4em .8em; background: #333; color: #fff;
               text-decoration: none; border: none; cursor: pointer; font-size: 1em; }
        .btn-danger { background: #b00; }
        .btn-secondary { background: #888; }
        .key { font-family: "Courier New", monospace; background: #f0f0f0; padding: .2em .4em; }
        .error { color: #b00; margin: 1em 0; }
        .success { color: #060; margin: 1em 0; }
        form.inline { display: inline; }
        input[type=text], input[type=password], textarea {
            font-size: 1em; padding: .4em; width: 100%; max-width: 400px;
            box-sizing: border-box; }
        label { display: block; margin-top: 1em; font-weight: bold; }
    </style>
</head>
<body>
    {% if request.session.get("admin_authenticated") %}
    <nav>
        <a href="/admin">Licenças</a>
        <a href="/admin/new">Nova licença</a>
        <form method="post" action="/admin/logout" class="inline">
            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
            <button class="btn btn-secondary">Sair</button>
        </form>
    </nav>
    {% endif %}
    {% block content %}{% endblock %}
</body>
</html>
```

- [ ] **Step 2: Criar `login.html`**

Conteúdo de `../license-server/app/templates/login.html`:

```html
{% extends "base.html" %}
{% block title %}Login — License Server{% endblock %}
{% block content %}
<h1>Login do administrador</h1>
{% if error %}
<p class="error">{{ error }}</p>
{% endif %}
<form method="post" action="/admin/login">
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
    <label>Senha:
        <input type="password" name="password" autofocus required>
    </label>
    <p><button type="submit" class="btn">Entrar</button></p>
</form>
{% endblock %}
```

- [ ] **Step 3: Criar `list.html`**

Conteúdo de `../license-server/app/templates/list.html`:

```html
{% extends "base.html" %}
{% block title %}Licenças — License Server{% endblock %}
{% block content %}
<h1>Licenças</h1>
{% if message %}<p class="success">{{ message }}</p>{% endif %}
<table>
    <thead>
        <tr>
            <th>Chave</th><th>Cliente</th><th>Status</th>
            <th>Criada em</th><th>Última validação</th><th>Ações</th>
        </tr>
    </thead>
    <tbody>
        {% for row in rows %}
        <tr>
            <td><a href="/admin/{{ row.license.id }}"><span class="key">{{ row.license.key }}</span></a></td>
            <td>{{ row.license.client_name }}</td>
            <td class="{{ 'revoked' if row.license.revoked else 'active' }}">
                {{ 'Revogada' if row.license.revoked else 'Ativa' }}
            </td>
            <td>{{ row.license.created_at }}</td>
            <td>{{ row.last_validation or '—' }}</td>
            <td>
                {% if row.license.revoked %}
                <form method="post" action="/admin/{{ row.license.id }}/unrevoke" class="inline">
                    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                    <button class="btn">Reativar</button>
                </form>
                {% else %}
                <form method="post" action="/admin/{{ row.license.id }}/revoke" class="inline">
                    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                    <button class="btn btn-danger">Revogar</button>
                </form>
                {% endif %}
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% endblock %}
```

- [ ] **Step 4: Criar `new.html`**

Conteúdo de `../license-server/app/templates/new.html`:

```html
{% extends "base.html" %}
{% block title %}Nova licença{% endblock %}
{% block content %}
<h1>Nova licença</h1>
<form method="post" action="/admin/new">
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
    <label>Nome do cliente:
        <input type="text" name="client_name" required>
    </label>
    <label>Notas (opcional):
        <textarea name="notes" rows="3"></textarea>
    </label>
    <p>
        <button type="submit" class="btn">Gerar chave</button>
        <a href="/admin" class="btn btn-secondary">Cancelar</a>
    </p>
</form>
{% endblock %}
```

- [ ] **Step 5: Criar `detail.html`**

Conteúdo de `../license-server/app/templates/detail.html`:

```html
{% extends "base.html" %}
{% block title %}Licença {{ license.client_name }}{% endblock %}
{% block content %}
<h1>Licença — {{ license.client_name }}</h1>
<p><strong>Chave:</strong> <span class="key">{{ license.key }}</span></p>
<p><strong>Status:</strong>
    <span class="{{ 'revoked' if license.revoked else 'active' }}">
        {{ 'Revogada' if license.revoked else 'Ativa' }}
    </span>
</p>
<p><strong>Criada em:</strong> {{ license.created_at }}</p>
{% if license.revoked_at %}
<p><strong>Revogada em:</strong> {{ license.revoked_at }}</p>
{% endif %}
{% if license.notes %}
<p><strong>Notas:</strong> {{ license.notes }}</p>
{% endif %}

<h2>Histórico de validações ({{ validations|length }})</h2>
<table>
    <thead><tr><th>Data</th><th>IP</th><th>Versão do app</th></tr></thead>
    <tbody>
        {% for v in validations %}
        <tr>
            <td>{{ v.validated_at }}</td>
            <td>{{ v.ip }}</td>
            <td>{{ v.app_version or '—' }}</td>
        </tr>
        {% endfor %}
    </tbody>
</table>

<p>
    {% if license.revoked %}
    <form method="post" action="/admin/{{ license.id }}/unrevoke" class="inline">
        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
        <button class="btn">Reativar</button>
    </form>
    {% else %}
    <form method="post" action="/admin/{{ license.id }}/revoke" class="inline">
        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
        <button class="btn btn-danger">Revogar</button>
    </form>
    {% endif %}
    <a href="/admin" class="btn btn-secondary">Voltar</a>
</p>
{% endblock %}
```

- [ ] **Step 6: Commit**

```bash
git add app/templates/
git commit -m "feat: templates HTML do painel admin"
```

---

### Task 18: Rotas do painel admin

**Files:**
- Create: `../license-server/app/routes_admin.py`
- Create: `../license-server/tests/test_routes_admin.py`
- Modify: `../license-server/app/main.py`

- [ ] **Step 1: Escrever testes falhos**

Conteúdo de `../license-server/tests/test_routes_admin.py`:

```python
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, tmp_path):
    db_path = str(tmp_path / "licenses.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("ADMIN_PASSWORD", "test-password")
    monkeypatch.setenv(
        "SECRET_KEY",
        "0123456789abcdef0123456789abcdef-test-only",
    )
    import importlib
    import app.main
    importlib.reload(app.main)
    return TestClient(app.main.app), db_path


def _login(client_obj):
    # Pega csrf token da página de login
    resp = client_obj.get("/admin/login")
    assert resp.status_code == 200
    import re
    m = re.search(r'name="csrf_token" value="([^"]+)"', resp.text)
    assert m, "csrf token não encontrado na página de login"
    csrf = m.group(1)
    resp = client_obj.post(
        "/admin/login",
        data={"csrf_token": csrf, "password": "test-password"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    return csrf


def _csrf_from(client_obj, path):
    resp = client_obj.get(path)
    assert resp.status_code == 200
    import re
    m = re.search(r'name="csrf_token" value="([^"]+)"', resp.text)
    assert m, f"csrf token não encontrado em {path}"
    return m.group(1)


def test_admin_index_requires_auth(client):
    c, _ = client
    resp = c.get("/admin", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/admin/login" in resp.headers["location"]


def test_login_with_correct_password_creates_session(client):
    c, _ = client
    _login(c)
    resp = c.get("/admin", follow_redirects=False)
    assert resp.status_code == 200
    assert "Licenças" in resp.text


def test_login_with_wrong_password_shows_error(client):
    c, _ = client
    csrf = _csrf_from(c, "/admin/login")
    resp = c.post(
        "/admin/login",
        data={"csrf_token": csrf, "password": "senha-errada"},
    )
    assert resp.status_code == 200
    assert "Senha incorreta" in resp.text


def test_create_license_via_admin_form(client):
    c, db_path = client
    _login(c)
    csrf = _csrf_from(c, "/admin/new")
    resp = c.post(
        "/admin/new",
        data={"csrf_token": csrf, "client_name": "Cliente Novo", "notes": "primeiro"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    from app.licenses import list_all_licenses
    licenses = list_all_licenses(db_path)
    assert len(licenses) == 1
    assert licenses[0].client_name == "Cliente Novo"
    assert licenses[0].notes == "primeiro"


def test_revoke_license(client):
    c, db_path = client
    from app.licenses import create_license, get_by_id
    lic = create_license(db_path, key="REVO-FROM-ADMI-NTST", client_name="X", notes=None)
    _login(c)
    csrf = _csrf_from(c, f"/admin/{lic.id}")
    resp = c.post(
        f"/admin/{lic.id}/revoke",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert get_by_id(db_path, lic.id).revoked is True


def test_unrevoke_license(client):
    c, db_path = client
    from app.licenses import create_license, revoke_license, get_by_id
    lic = create_license(db_path, key="UNRE-VOKE-FROM-ADMI", client_name="Y", notes=None)
    revoke_license(db_path, lic.id)
    _login(c)
    csrf = _csrf_from(c, f"/admin/{lic.id}")
    resp = c.post(
        f"/admin/{lic.id}/unrevoke",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert get_by_id(db_path, lic.id).revoked is False


def test_revoke_without_csrf_is_rejected(client):
    c, db_path = client
    from app.licenses import create_license, get_by_id
    lic = create_license(db_path, key="NOCS-RFTO-KENT-EST1", client_name="Z", notes=None)
    _login(c)
    resp = c.post(
        f"/admin/{lic.id}/revoke",
        data={"csrf_token": "token-falso"},
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert get_by_id(db_path, lic.id).revoked is False


def test_logout_clears_session(client):
    c, _ = client
    _login(c)
    csrf = _csrf_from(c, "/admin")
    c.post("/admin/logout", data={"csrf_token": csrf}, follow_redirects=False)
    resp = c.get("/admin", follow_redirects=False)
    assert resp.status_code in (302, 303)
```

- [ ] **Step 2: Rodar testes e verificar que falham**

```bash
pytest tests/test_routes_admin.py -v
```

Esperado: FAIL — endpoints `/admin/*` não existem

- [ ] **Step 3: Implementar `routes_admin.py`**

Conteúdo de `../license-server/app/routes_admin.py`:

```python
import logging
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.keygen import generate_key
from app.licenses import (
    create_license,
    get_by_id,
    list_all_licenses,
    list_validations_for_license,
    revoke_license,
    unrevoke_license,
)
from app.security import (
    get_or_create_csrf_token,
    is_authenticated,
    verify_csrf_token,
    verify_password,
    hash_password,
)


router = APIRouter(prefix="/admin")
logger = logging.getLogger("license-server.admin")
limiter = Limiter(key_func=get_remote_address)

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Hash da senha gerado uma vez na inicialização (ADMIN_PASSWORD é env var)
# Armazenado em variável de módulo para evitar hashear a cada request
_admin_password_hash: str | None = None


def _get_admin_hash(request: Request) -> str:
    global _admin_password_hash
    if _admin_password_hash is None:
        _admin_password_hash = hash_password(request.app.state.settings.admin_password)
    return _admin_password_hash


def _check_csrf(request: Request, form_token: str) -> None:
    session_token = request.session.get("csrf_token")
    if not verify_csrf_token(session_token, form_token):
        raise HTTPException(status_code=400, detail="csrf_invalid")


def _require_auth_or_redirect(request: Request):
    if not is_authenticated(request):
        return RedirectResponse("/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    return None


@router.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    csrf = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "csrf_token": csrf, "error": None},
    )


@router.post("/login")
@limiter.limit("5/minute")
async def login_post(
    request: Request,
    csrf_token: str = Form(...),
    password: str = Form(...),
):
    _check_csrf(request, csrf_token)
    admin_hash = _get_admin_hash(request)
    if not verify_password(password, admin_hash):
        logger.info("login: senha incorreta de %s", request.client.host if request.client else "?")
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "csrf_token": csrf_token, "error": "Senha incorreta"},
        )
    request.session["admin_authenticated"] = True
    return RedirectResponse("/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout")
async def logout(request: Request, csrf_token: str = Form(...)):
    _check_csrf(request, csrf_token)
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=status.HTTP_303_SEE_OTHER)


@router.get("", response_class=HTMLResponse)
async def list_view(request: Request):
    redirect = _require_auth_or_redirect(request)
    if redirect:
        return redirect

    settings = request.app.state.settings
    licenses = list_all_licenses(settings.db_path)
    rows = []
    for lic in licenses:
        validations = list_validations_for_license(settings.db_path, lic.id)
        last = validations[0].validated_at if validations else None
        rows.append({"license": lic, "last_validation": last})

    csrf = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        "list.html",
        {"request": request, "rows": rows, "csrf_token": csrf, "message": None},
    )


@router.get("/new", response_class=HTMLResponse)
async def new_get(request: Request):
    redirect = _require_auth_or_redirect(request)
    if redirect:
        return redirect
    csrf = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        "new.html",
        {"request": request, "csrf_token": csrf},
    )


@router.post("/new")
async def new_post(
    request: Request,
    csrf_token: str = Form(...),
    client_name: str = Form(...),
    notes: str = Form(""),
):
    redirect = _require_auth_or_redirect(request)
    if redirect:
        return redirect
    _check_csrf(request, csrf_token)

    settings = request.app.state.settings
    key = generate_key()
    create_license(
        settings.db_path,
        key=key,
        client_name=client_name.strip(),
        notes=notes.strip() or None,
    )
    return RedirectResponse("/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{license_id}", response_class=HTMLResponse)
async def detail_view(request: Request, license_id: int):
    redirect = _require_auth_or_redirect(request)
    if redirect:
        return redirect

    settings = request.app.state.settings
    lic = get_by_id(settings.db_path, license_id)
    if lic is None:
        raise HTTPException(status_code=404)
    validations = list_validations_for_license(settings.db_path, license_id)
    csrf = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        "detail.html",
        {"request": request, "license": lic, "validations": validations, "csrf_token": csrf},
    )


@router.post("/{license_id}/revoke")
async def revoke_post(
    request: Request,
    license_id: int,
    csrf_token: str = Form(...),
):
    redirect = _require_auth_or_redirect(request)
    if redirect:
        return redirect
    _check_csrf(request, csrf_token)

    settings = request.app.state.settings
    revoke_license(settings.db_path, license_id)
    return RedirectResponse("/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{license_id}/unrevoke")
async def unrevoke_post(
    request: Request,
    license_id: int,
    csrf_token: str = Form(...),
):
    redirect = _require_auth_or_redirect(request)
    if redirect:
        return redirect
    _check_csrf(request, csrf_token)

    settings = request.app.state.settings
    unrevoke_license(settings.db_path, license_id)
    return RedirectResponse("/admin", status_code=status.HTTP_303_SEE_OTHER)
```

- [ ] **Step 4: Registrar router em `main.py`**

Substituir `../license-server/app/main.py` por:

```python
import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from app.config import load_settings
from app.db import init_db
from app.routes_api import router as api_router, limiter as api_limiter
from app.routes_admin import router as admin_router, limiter as admin_limiter


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("license-server")


def create_app() -> FastAPI:
    settings = load_settings()
    init_db(settings.db_path)

    fastapi_app = FastAPI(title="License Server")
    # Usa um único limiter compartilhado (slowapi suporta múltiplos decorators
    # com chaves diferentes mas state.limiter espera um instance)
    fastapi_app.state.limiter = api_limiter
    fastapi_app.state.settings = settings

    fastapi_app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        https_only=False,
        same_site="lax",
        max_age=7 * 24 * 60 * 60,
    )

    fastapi_app.include_router(api_router)
    fastapi_app.include_router(admin_router)

    # slowapi handler precisa estar registrado
    @fastapi_app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request, exc):
        return JSONResponse(
            status_code=429,
            content={"error": "rate_limit_exceeded"},
        )

    @fastapi_app.get("/")
    async def root():
        return {"service": "license-server", "status": "ok"}

    return fastapi_app


app = create_app()
```

- [ ] **Step 5: Rodar todos os testes do admin**

```bash
pytest tests/test_routes_admin.py -v
```

Esperado: PASS — 8 tests passed

- [ ] **Step 6: Rodar TODA a suíte de testes do backend**

```bash
pytest -v
```

Esperado: PASS — todos os testes (keygen + licenses + security + routes_api + routes_admin) verdes.

- [ ] **Step 7: Commit**

```bash
git add app/routes_admin.py app/main.py tests/test_routes_admin.py
git commit -m "feat: painel admin HTML com login/CRUD/CSRF"
```

---

### Task 19: Smoke test manual do backend

**Files:** nenhum — verificação manual

- [ ] **Step 1: Subir servidor localmente**

```bash
cd ../license-server
set ADMIN_PASSWORD=admin123 && set SECRET_KEY=0123456789abcdef0123456789abcdef-local-dev && uvicorn app.main:app --reload
```

Esperado: servidor escutando em `http://localhost:8000`

- [ ] **Step 2: Abrir painel admin no navegador**

Abrir `http://localhost:8000/admin/login`. Logar com senha `admin123`. Esperado: lista vazia de licenças.

- [ ] **Step 3: Criar uma licença**

Clicar "Nova licença", preencher "Cliente Teste", "primeira chave manual", submeter. Esperado: redireciona para lista e aparece 1 licença com chave gerada.

- [ ] **Step 4: Validar a chave via curl**

Copiar a chave gerada e rodar (substituir `<CHAVE>`):

```bash
curl -X POST http://localhost:8000/api/validate -H "Content-Type: application/json" -d "{\"key\":\"<CHAVE>\",\"app_version\":\"smoke-test\"}"
```

Esperado: `{"valid":true,"client_name":"Cliente Teste"}`

- [ ] **Step 5: Revogar e validar de novo**

Clicar "Revogar" na lista. Rodar o mesmo curl. Esperado: `{"valid":false,"reason":"revoked"}`

- [ ] **Step 6: Encerrar servidor**

`Ctrl+C` no terminal do uvicorn.

- [ ] **Step 7: Tag de release**

```bash
git tag v0.1.0
```

Backend pronto. Voltar ao diretório do app principal:

```bash
cd ../ocorrenciaspdf
```

---

# FASE 2 — Cliente embutido no app desktop

A Fase 2 adiciona o módulo de cliente ao app `ocorrenciaspdf`. Como o cliente é testado contra um servidor mockado, ele pode ser desenvolvido independente da Fase 1 estar rodando — basta importar `license_client.py` e mockar `requests`.

---

### Task 20: Adicionar dependência `requests` (se ainda não existir)

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Verificar se `requests` está em requirements**

```bash
type requirements.txt | findstr /I requests
```

- [ ] **Step 2: Se não estiver, adicionar**

Se o comando acima retornar vazio, adicionar `requests>=2.31.0` a `requirements.txt`. Se já estiver listado, pular esta task inteira.

- [ ] **Step 3: Instalar dependência**

```bash
pip install -r requirements.txt
```

- [ ] **Step 4: Commit (apenas se modificou)**

```bash
git add requirements.txt
git commit -m "chore: adicionar requests para validação de licença"
```

---

### Task 21: Esqueleto do `LicenseClient` — enums e dataclass

**Files:**
- Create: `license_client.py`
- Create: `tests/test_license_client.py`

- [ ] **Step 1: Escrever testes falhos**

Conteúdo inicial de `tests/test_license_client.py`:

```python
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from license_client import LicenseClient, LicenseStatus, ValidationResult


def test_status_enum_has_expected_values():
    assert LicenseStatus.VALID.value == "valid"
    assert LicenseStatus.INVALID.value == "invalid"
    assert LicenseStatus.OFFLINE_TOLERATED.value == "offline_tolerated"
    assert LicenseStatus.OFFLINE_EXPIRED.value == "offline_expired"
    assert LicenseStatus.NO_KEY.value == "no_key"


def test_validation_result_has_status_reason_client_name():
    r = ValidationResult(status=LicenseStatus.VALID, reason=None, client_name="Foo")
    assert r.status == LicenseStatus.VALID
    assert r.reason is None
    assert r.client_name == "Foo"


def test_validate_no_key_when_config_missing(tmp_path):
    config_path = tmp_path / "config.json"
    client = LicenseClient(config_path=config_path)
    result = client.validate()
    assert result.status == LicenseStatus.NO_KEY
```

- [ ] **Step 2: Rodar teste e verificar que falha**

```bash
pytest tests/test_license_client.py -v
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'license_client'`

- [ ] **Step 3: Implementar esqueleto**

Conteúdo inicial de `license_client.py`:

```python
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

import requests


logger = logging.getLogger("license_client")


class LicenseStatus(Enum):
    VALID = "valid"
    INVALID = "invalid"
    OFFLINE_TOLERATED = "offline_tolerated"
    OFFLINE_EXPIRED = "offline_expired"
    NO_KEY = "no_key"


@dataclass
class ValidationResult:
    status: LicenseStatus
    reason: Optional[str] = None
    client_name: Optional[str] = None


DEFAULT_CONFIG_PATH = Path.home() / ".ocorrencias_config.json"


class LicenseClient:
    SERVER_URL = "https://meuapp.duckdns.org"   # placeholder — substituir ao deployar VPS
    OFFLINE_TOLERANCE_HOURS = 24
    TIMEOUT_SECONDS = 10
    APP_VERSION = "1.35"

    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH):
        self.config_path = config_path

    def _read_config(self) -> dict:
        if not self.config_path.exists():
            return {}
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("Config file inválido em %s — tratando como vazio", self.config_path)
            return {}

    def _write_config(self, data: dict) -> None:
        self.config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_saved_key(self) -> Optional[str]:
        return self._read_config().get("license_key")

    def save_key(self, key: str) -> None:
        cfg = self._read_config()
        cfg["license_key"] = key
        self._write_config(cfg)

    def clear_key(self) -> None:
        cfg = self._read_config()
        cfg.pop("license_key", None)
        cfg.pop("last_validated_at", None)
        self._write_config(cfg)

    def validate(self, key: Optional[str] = None) -> ValidationResult:
        if key is None:
            key = self.get_saved_key()
        if not key:
            return ValidationResult(status=LicenseStatus.NO_KEY)
        # implementação completa nas próximas tasks
        return ValidationResult(status=LicenseStatus.NO_KEY)
```

- [ ] **Step 4: Rodar testes e verificar que passam**

```bash
pytest tests/test_license_client.py -v
```

Esperado: PASS — 3 tests passed

- [ ] **Step 5: Commit**

```bash
git add license_client.py tests/test_license_client.py
git commit -m "feat: esqueleto do LicenseClient com enums e leitura de config"
```

---

### Task 22: `LicenseClient.validate()` — caminho de sucesso (chave válida)

**Files:**
- Modify: `license_client.py`
- Modify: `tests/test_license_client.py`

- [ ] **Step 1: Adicionar testes falhos**

Adicionar ao final de `tests/test_license_client.py`:

```python
from unittest.mock import patch, MagicMock


def _make_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


def test_validate_with_valid_key_returns_valid(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"license_key": "ABCD-EFGH-IJKL-MNOP"}), encoding="utf-8")

    client = LicenseClient(config_path=config_path)
    fake_response = _make_response(200, {"valid": True, "client_name": "Fulano"})

    with patch("license_client.requests.post", return_value=fake_response) as mock_post:
        result = client.validate()

    assert result.status == LicenseStatus.VALID
    assert result.client_name == "Fulano"
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert "/api/validate" in call_args[0][0]
    assert call_args[1]["json"]["key"] == "ABCD-EFGH-IJKL-MNOP"


def test_validate_with_valid_key_updates_last_validated_at(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"license_key": "ABCD-EFGH-IJKL-MNOP"}), encoding="utf-8")

    client = LicenseClient(config_path=config_path)
    fake_response = _make_response(200, {"valid": True, "client_name": "Fulano"})

    with patch("license_client.requests.post", return_value=fake_response):
        client.validate()

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert "last_validated_at" in saved
    # Verifica formato ISO 8601
    datetime.fromisoformat(saved["last_validated_at"])
```

- [ ] **Step 2: Rodar testes e verificar que falham**

```bash
pytest tests/test_license_client.py -v
```

Esperado: FAIL — `result.status` é `NO_KEY`, esperado `VALID`

- [ ] **Step 3: Implementar caminho de sucesso**

Substituir o método `validate` em `license_client.py` por:

```python
    def validate(self, key: Optional[str] = None) -> ValidationResult:
        if key is None:
            key = self.get_saved_key()
        if not key:
            return ValidationResult(status=LicenseStatus.NO_KEY)

        url = f"{self.SERVER_URL}/api/validate"
        payload = {"key": key, "app_version": self.APP_VERSION}

        try:
            resp = requests.post(url, json=payload, timeout=self.TIMEOUT_SECONDS)
        except requests.RequestException as e:
            logger.info("Erro de rede validando licença: %s", e)
            return self._offline_result()

        if resp.status_code != 200:
            logger.info("Servidor respondeu %d — tratando como offline", resp.status_code)
            return self._offline_result()

        try:
            data = resp.json()
        except ValueError:
            logger.info("Resposta do servidor não é JSON válido — tratando como offline")
            return self._offline_result()

        if data.get("valid") is True:
            self._update_last_validated()
            return ValidationResult(
                status=LicenseStatus.VALID,
                client_name=data.get("client_name"),
            )

        return ValidationResult(
            status=LicenseStatus.INVALID,
            reason=data.get("reason"),
        )

    def _update_last_validated(self) -> None:
        cfg = self._read_config()
        cfg["last_validated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._write_config(cfg)

    def _offline_result(self) -> ValidationResult:
        # Implementado na próxima task — por enquanto retorna OFFLINE_EXPIRED
        return ValidationResult(status=LicenseStatus.OFFLINE_EXPIRED)
```

- [ ] **Step 4: Rodar testes e verificar que passam**

```bash
pytest tests/test_license_client.py -v
```

Esperado: PASS — 5 tests passed

- [ ] **Step 5: Commit**

```bash
git add license_client.py tests/test_license_client.py
git commit -m "feat: LicenseClient.validate caminho de sucesso (valid=true)"
```

---

### Task 23: `LicenseClient.validate()` — chave inválida (not_found / revoked)

**Files:**
- Modify: `tests/test_license_client.py`

- [ ] **Step 1: Adicionar testes**

Adicionar ao final de `tests/test_license_client.py`:

```python
def test_validate_returns_invalid_with_reason_not_found(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"license_key": "ABCD-EFGH-IJKL-MNOP"}), encoding="utf-8")
    client = LicenseClient(config_path=config_path)
    fake = _make_response(200, {"valid": False, "reason": "not_found"})
    with patch("license_client.requests.post", return_value=fake):
        result = client.validate()
    assert result.status == LicenseStatus.INVALID
    assert result.reason == "not_found"


def test_validate_returns_invalid_with_reason_revoked(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"license_key": "ABCD-EFGH-IJKL-MNOP"}), encoding="utf-8")
    client = LicenseClient(config_path=config_path)
    fake = _make_response(200, {"valid": False, "reason": "revoked"})
    with patch("license_client.requests.post", return_value=fake):
        result = client.validate()
    assert result.status == LicenseStatus.INVALID
    assert result.reason == "revoked"


def test_validate_invalid_does_not_clear_saved_key(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"license_key": "ABCD-EFGH-IJKL-MNOP"}), encoding="utf-8")
    client = LicenseClient(config_path=config_path)
    fake = _make_response(200, {"valid": False, "reason": "revoked"})
    with patch("license_client.requests.post", return_value=fake):
        client.validate()
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved.get("license_key") == "ABCD-EFGH-IJKL-MNOP"
```

- [ ] **Step 2: Rodar e verificar que passam (o caminho INVALID já foi implementado na Task 22)**

```bash
pytest tests/test_license_client.py -v
```

Esperado: PASS — 8 tests passed

- [ ] **Step 3: Commit**

```bash
git add tests/test_license_client.py
git commit -m "test: cobertura para chaves inválidas (not_found/revoked)"
```

---

### Task 24: `LicenseClient.validate()` — tolerância offline

**Files:**
- Modify: `license_client.py`
- Modify: `tests/test_license_client.py`

- [ ] **Step 1: Adicionar testes falhos**

Adicionar ao final de `tests/test_license_client.py`:

```python
def _config_with(license_key, last_validated_at):
    return {"license_key": license_key, "last_validated_at": last_validated_at}


def test_validate_offline_recent_validation_returns_tolerated(tmp_path):
    recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds")
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(_config_with("ABCD-EFGH-IJKL-MNOP", recent)),
        encoding="utf-8",
    )
    client = LicenseClient(config_path=config_path)
    with patch("license_client.requests.post", side_effect=requests.ConnectionError()):
        result = client.validate()
    assert result.status == LicenseStatus.OFFLINE_TOLERATED


def test_validate_offline_old_validation_returns_expired(tmp_path):
    old = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(timespec="seconds")
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(_config_with("ABCD-EFGH-IJKL-MNOP", old)),
        encoding="utf-8",
    )
    client = LicenseClient(config_path=config_path)
    with patch("license_client.requests.post", side_effect=requests.ConnectionError()):
        result = client.validate()
    assert result.status == LicenseStatus.OFFLINE_EXPIRED


def test_validate_offline_no_prior_validation_returns_expired(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"license_key": "ABCD-EFGH-IJKL-MNOP"}),
        encoding="utf-8",
    )
    client = LicenseClient(config_path=config_path)
    with patch("license_client.requests.post", side_effect=requests.Timeout()):
        result = client.validate()
    assert result.status == LicenseStatus.OFFLINE_EXPIRED


def test_validate_offline_corrupt_timestamp_returns_expired(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"license_key": "ABCD-EFGH-IJKL-MNOP", "last_validated_at": "lixo"}),
        encoding="utf-8",
    )
    client = LicenseClient(config_path=config_path)
    with patch("license_client.requests.post", side_effect=requests.ConnectionError()):
        result = client.validate()
    assert result.status == LicenseStatus.OFFLINE_EXPIRED


def test_validate_offline_non_200_response_uses_offline_path(tmp_path):
    recent = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(timespec="seconds")
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(_config_with("ABCD-EFGH-IJKL-MNOP", recent)),
        encoding="utf-8",
    )
    client = LicenseClient(config_path=config_path)
    fake = _make_response(503, None)
    with patch("license_client.requests.post", return_value=fake):
        result = client.validate()
    assert result.status == LicenseStatus.OFFLINE_TOLERATED


def test_validate_offline_invalid_json_uses_offline_path(tmp_path):
    recent = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(timespec="seconds")
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(_config_with("ABCD-EFGH-IJKL-MNOP", recent)),
        encoding="utf-8",
    )
    client = LicenseClient(config_path=config_path)
    bad_resp = MagicMock()
    bad_resp.status_code = 200
    bad_resp.json.side_effect = ValueError("invalid json")
    with patch("license_client.requests.post", return_value=bad_resp):
        result = client.validate()
    assert result.status == LicenseStatus.OFFLINE_TOLERATED
```

- [ ] **Step 2: Rodar e verificar que falham (os 3 primeiros)**

```bash
pytest tests/test_license_client.py -v
```

Esperado: FAIL — `test_validate_offline_recent_validation_returns_tolerated` falha porque `_offline_result()` sempre retorna `OFFLINE_EXPIRED`.

- [ ] **Step 3: Implementar `_offline_result` corretamente**

Substituir o método `_offline_result` em `license_client.py` por:

```python
    def _offline_result(self) -> ValidationResult:
        cfg = self._read_config()
        last_str = cfg.get("last_validated_at")
        if not last_str:
            return ValidationResult(status=LicenseStatus.OFFLINE_EXPIRED)
        try:
            last = datetime.fromisoformat(last_str)
        except ValueError:
            return ValidationResult(status=LicenseStatus.OFFLINE_EXPIRED)

        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)

        delta = datetime.now(timezone.utc) - last
        if delta < timedelta(hours=self.OFFLINE_TOLERANCE_HOURS):
            return ValidationResult(status=LicenseStatus.OFFLINE_TOLERATED)
        return ValidationResult(status=LicenseStatus.OFFLINE_EXPIRED)
```

- [ ] **Step 4: Rodar todos os testes do client e verificar que passam**

```bash
pytest tests/test_license_client.py -v
```

Esperado: PASS — 14 tests passed

- [ ] **Step 5: Commit**

```bash
git add license_client.py tests/test_license_client.py
git commit -m "feat: tolerância offline de 24h em LicenseClient"
```

---

### Task 25: Config corrompido — teste

**Files:**
- Modify: `tests/test_license_client.py`

- [ ] **Step 1: Adicionar teste**

Adicionar ao final de `tests/test_license_client.py`:

```python
def test_validate_corrupt_config_is_treated_as_no_key(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text("{ não é json válido", encoding="utf-8")
    client = LicenseClient(config_path=config_path)
    result = client.validate()
    assert result.status == LicenseStatus.NO_KEY
```

- [ ] **Step 2: Rodar e verificar que passa (o tratamento já existe em `_read_config`)**

```bash
pytest tests/test_license_client.py::test_validate_corrupt_config_is_treated_as_no_key -v
```

Esperado: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_license_client.py
git commit -m "test: config corrompido tratado como sem chave"
```

---

### Task 26: UI tkinter — `license_ui.py`

**Files:**
- Create: `license_ui.py`

- [ ] **Step 1: Implementar UI**

Conteúdo de `license_ui.py`:

```python
"""Telas tkinter para ativação de licença e erros bloqueantes.

Testes automatizados não são incluídos — tkinter é difícil de testar em CI
sem display. Verificação é manual (ver Task 28 — smoke test do cliente).
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional


def show_activation_window(initial_message: str = "") -> Optional[str]:
    """Abre janela modal pedindo chave de licença.

    Retorna a chave digitada (str) ou None se o usuário fechou/cancelou.
    """
    result: dict = {"key": None}

    root = tk.Tk()
    root.title("Ativação de licença")
    root.geometry("420x220")
    root.resizable(False, False)

    # Centralizar
    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    frm = ttk.Frame(root, padding=20)
    frm.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frm, text="Processador de Ocorrências", font=("Segoe UI", 12, "bold")).pack()

    if initial_message:
        ttk.Label(frm, text=initial_message, foreground="#a00", wraplength=380).pack(pady=(8, 0))

    ttk.Label(frm, text="Chave de licença:").pack(anchor=tk.W, pady=(12, 4))
    entry = ttk.Entry(frm, width=40)
    entry.pack(fill=tk.X)
    entry.focus_set()

    def on_activate():
        value = entry.get().strip().upper()
        if value:
            result["key"] = value
            root.destroy()

    def on_cancel():
        result["key"] = None
        root.destroy()

    btn_frame = ttk.Frame(frm)
    btn_frame.pack(fill=tk.X, pady=(16, 0))
    ttk.Button(btn_frame, text="Ativar", command=on_activate).pack(side=tk.LEFT)
    ttk.Button(btn_frame, text="Sair", command=on_cancel).pack(side=tk.RIGHT)

    root.bind("<Return>", lambda e: on_activate())
    root.bind("<Escape>", lambda e: on_cancel())
    root.protocol("WM_DELETE_WINDOW", on_cancel)

    root.mainloop()
    return result["key"]


def show_error_window(message: str) -> None:
    """Mostra diálogo de erro bloqueante. Retorna quando usuário fecha."""
    root = tk.Tk()
    root.title("Erro de licença")
    root.geometry("420x180")
    root.resizable(False, False)

    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    frm = ttk.Frame(root, padding=20)
    frm.pack(fill=tk.BOTH, expand=True)
    ttk.Label(frm, text=message, wraplength=380).pack(expand=True)
    ttk.Button(frm, text="OK", command=root.destroy).pack(pady=(12, 0))

    root.bind("<Return>", lambda e: root.destroy())
    root.bind("<Escape>", lambda e: root.destroy())

    root.mainloop()
```

- [ ] **Step 2: Smoke test manual rápido**

```bash
python -c "from license_ui import show_activation_window; print(show_activation_window('teste de tela'))"
```

Esperado: abre uma janela, você digita "ABCD-EFGH-IJKL-MNOP" e clica Ativar → console imprime `ABCD-EFGH-IJKL-MNOP`. Fechar a janela sem ativar → imprime `None`.

```bash
python -c "from license_ui import show_error_window; show_error_window('Erro de teste — clique OK para fechar')"
```

Esperado: abre janela com a mensagem, botão OK fecha.

- [ ] **Step 3: Commit**

```bash
git add license_ui.py
git commit -m "feat: telas tkinter de ativação e erro de licença"
```

---

### Task 27: Integrar bootstrap em `app.py`

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Identificar ponto de entrada**

Antes de editar, abrir `app.py` no editor e localizar onde a janela principal é criada (geralmente uma chamada `Tk()` ou `App().run()` dentro de `if __name__ == "__main__":`).

- [ ] **Step 2: Adicionar função `bootstrap_license` no topo de `app.py`**

Adicionar logo após os imports existentes no início de `app.py`:

```python
from license_client import LicenseClient, LicenseStatus
from license_ui import show_activation_window, show_error_window


def bootstrap_license() -> bool:
    """Valida licença antes de abrir o app. Retorna True se app deve continuar."""
    client = LicenseClient()

    while True:
        result = client.validate()

        if result.status == LicenseStatus.VALID:
            return True

        if result.status == LicenseStatus.OFFLINE_TOLERATED:
            return True

        if result.status == LicenseStatus.NO_KEY:
            new_key = show_activation_window("Insira sua chave de licença para começar.")
        elif result.status == LicenseStatus.INVALID:
            reason_msg = {
                "not_found": "Chave não reconhecida.",
                "revoked": "Esta chave foi revogada. Entre em contato com o suporte.",
            }.get(result.reason, "Chave inválida.")
            new_key = show_activation_window(reason_msg)
        elif result.status == LicenseStatus.OFFLINE_EXPIRED:
            show_error_window(
                "Não foi possível validar sua licença com o servidor e o "
                "período de uso offline expirou. Conecte-se à internet e tente novamente."
            )
            return False
        else:
            return False

        if new_key is None:
            return False

        client.save_key(new_key)
```

- [ ] **Step 3: Chamar `bootstrap_license()` no entry point**

Localizar a guarda `if __name__ == "__main__":` (ou função `main()`) no final de `app.py`. Modificar para chamar `bootstrap_license()` antes de criar a janela principal. Exemplo de transformação:

**Antes:**

```python
if __name__ == "__main__":
    app = App()
    app.mainloop()
```

**Depois:**

```python
if __name__ == "__main__":
    import sys
    if not bootstrap_license():
        sys.exit(0)
    app = App()
    app.mainloop()
```

**Se o entry point for diferente** (ex: já existe função `main()`), adicionar a chamada `if not bootstrap_license(): return` no início da `main()`, antes de qualquer criação de janela.

- [ ] **Step 4: Testar manualmente — sem chave salva**

```bash
del /Q "%USERPROFILE%\.ocorrencias_config.json" 2>nul
python app.py
```

Esperado: abre tela de ativação (porque não há chave). Clicar "Sair" → app encerra sem mostrar janela principal.

- [ ] **Step 5: Testar manualmente — com chave inválida**

Rodar novamente:

```bash
python app.py
```

Digitar uma chave inválida (ex: `XXXX-XXXX-XXXX-XXXX`). Como não há servidor configurado e a URL é placeholder, a request vai falhar → cliente tenta caminho offline → sem `last_validated_at` → `OFFLINE_EXPIRED` → janela de erro aparece. Clicar OK → app encerra.

> **Nota:** com o backend ainda não deployado, o app sempre cairá em offline. Isso é esperado nesta etapa — o teste real do caminho VALID é manual com servidor local rodando (Task 28).

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat: integrar bootstrap de licença antes da janela principal"
```

---

### Task 28: Smoke test cliente ↔ servidor local

**Files:** nenhum — teste manual de integração

- [ ] **Step 1: Subir backend local em terminal separado**

```bash
cd ../license-server
set ADMIN_PASSWORD=admin123 && set SECRET_KEY=0123456789abcdef0123456789abcdef-local-dev && uvicorn app.main:app --reload
```

- [ ] **Step 2: Criar chave via painel admin**

Abrir http://localhost:8000/admin/login no navegador, logar com `admin123`, criar licença para "Smoke Test Cliente". Anotar a chave gerada.

- [ ] **Step 3: Apontar cliente para localhost**

Editar temporariamente `ocorrenciaspdf/license_client.py`:

```python
class LicenseClient:
    SERVER_URL = "http://localhost:8000"   # TEMPORÁRIO — voltar a HTTPS antes de deployar
```

**Atenção:** alterar `https` → `http` aqui. Esta mudança é apenas para o smoke test local; será revertida antes do release.

- [ ] **Step 4: Rodar app**

```bash
cd ../ocorrenciaspdf
del /Q "%USERPROFILE%\.ocorrencias_config.json" 2>nul
python app.py
```

Esperado:
- Abre tela de ativação
- Colar a chave criada no painel admin
- Clicar "Ativar"
- A tela de licença fecha e a janela principal do app aparece

- [ ] **Step 5: Verificar `validation_log` no painel admin**

Voltar ao painel admin → clicar na chave criada → ver "Histórico de validações" com 1 entrada (IP 127.0.0.1, app_version 1.35).

- [ ] **Step 6: Testar revogação**

No painel admin: revogar a chave. Fechar o app. Rodar `python app.py` novamente.

Esperado:
- Tela de ativação aparece com mensagem "Esta chave foi revogada. Entre em contato com o suporte."
- Clicar "Sair" → app encerra

- [ ] **Step 7: Reverter URL temporária**

Editar `license_client.py` de volta:

```python
class LicenseClient:
    SERVER_URL = "https://meuapp.duckdns.org"   # placeholder — substituir ao deployar VPS
```

- [ ] **Step 8: Verificar git status — apenas reversão da URL**

```bash
git diff license_client.py
```

Esperado: diff vazio (a URL foi revertida ao original).

- [ ] **Step 9: Encerrar uvicorn**

`Ctrl+C` no terminal do backend.

- [ ] **Step 10: Rodar suíte completa de testes do cliente**

```bash
pytest tests/test_license_client.py -v
```

Esperado: PASS — 15 tests passed (todos)

- [ ] **Step 11: Tag de release do app**

```bash
git tag v1.35
```

---

### Task 29: README e bump de versão

**Files:**
- Modify: `README.md`
- Modify: `processador.py` (ou onde a versão for declarada — verificar primeiro)

- [ ] **Step 1: Localizar onde a versão atual `1.34` é declarada**

```bash
grep -r "1.34" --include="*.py" .
```

Identificar o arquivo principal onde a constante de versão vive. Pelos arquivos `.spec`, a versão é incrementada em arquivos `.spec` — o arquivo `ProcessadorOcorrencias-v1.35.spec` precisará ser criado seguindo o padrão dos anteriores.

- [ ] **Step 2: Criar `ProcessadorOcorrencias-v1.35.spec`**

Copiar `ProcessadorOcorrencias-v1.34.spec` para `ProcessadorOcorrencias-v1.35.spec`:

```bash
copy ProcessadorOcorrencias-v1.34.spec ProcessadorOcorrencias-v1.35.spec
```

Abrir `ProcessadorOcorrencias-v1.35.spec` e procurar referências à versão antiga (`1.34`) e atualizar para `1.35`. Em particular: o nome do executável final e quaisquer strings de versão.

Também adicionar `license_client.py` e `license_ui.py` aos arquivos incluídos pelo PyInstaller — procurar a seção `Analysis(...)` e a lista de scripts/datas. Os arquivos `.py` no diretório do projeto são incluídos automaticamente se importados por `app.py`, portanto nenhuma mudança adicional é geralmente necessária.

- [ ] **Step 3: Atualizar `README.md`**

Adicionar nova seção entre "Como usar" e "Configuração" no `README.md`:

```markdown
## Ativação de licença

A partir da versão 1.35, o app exige uma chave de licença válida para abrir.

- Na primeira abertura, uma tela pede a chave de licença
- A chave é validada com o servidor a cada abertura do app
- Sem internet, o app permite uso por até 24 horas após a última validação bem-sucedida
- Chaves revogadas pelo administrador bloqueiam o acesso imediatamente
- Validações registram seu IP no servidor para fins de auditoria

Para obter uma chave, entre em contato com o autor (ver seção Autor abaixo).
```

Atualizar a linha de versão no final do README:

```markdown
Versão atual: **1.35**
```

- [ ] **Step 4: Commit**

```bash
git add README.md ProcessadorOcorrencias-v1.35.spec
git commit -m "docs: README e spec do PyInstaller para v1.35 com validação de licença"
```

---

## Self-Review do plano

### Cobertura do spec

| Requisito do spec | Task(s) |
|---|---|
| Backend FastAPI + SQLite | Tasks 1-19 |
| Painel admin HTML com login | Tasks 16-18 |
| Tabela `licenses` | Task 5 |
| Tabela `validation_log` | Tasks 5, 9 |
| Formato de chave `XXXX-XXXX-XXXX-XXXX` | Task 2 |
| Endpoint público `/api/validate` | Tasks 14, 15 |
| Defesa contra enumeração (sempre 200) | Task 14 |
| Rate limits (60/min API, 5/min login) | Tasks 15, 18 |
| Auth admin via cookie de sessão + bcrypt | Tasks 16, 18 |
| CSRF nos POSTs do painel | Tasks 11, 18 |
| Máscara de chave nos logs | Tasks 12, 14, 18 |
| `LicenseClient` no app desktop | Tasks 21-25 |
| Status enum (VALID/INVALID/OFFLINE_TOLERATED/OFFLINE_EXPIRED/NO_KEY) | Task 21 |
| Tolerância offline de 24h | Task 24 |
| Tela tkinter de ativação | Task 26 |
| Bootstrap no `app.py` antes da janela principal | Task 27 |
| Smoke test integrado | Tasks 19, 28 |
| README do servidor com passos de deploy | Task 1 |
| README do app com seção de licença | Task 29 |
| Bump de versão para 1.35 | Task 29 |

Todas as seções do spec têm task correspondente.

### Placeholders

`SERVER_URL = "https://meuapp.duckdns.org"` é placeholder explícito documentado tanto no código quanto no spec — esperado, será resolvido no deploy. **Não é "TBD escondido".**

Todos os outros steps contêm código completo ou comando exato.

### Consistência de tipos

- `LicenseClient`, `LicenseStatus`, `ValidationResult` consistentes entre Tasks 21-27
- `create_license`, `revoke_license`, `unrevoke_license`, `list_all_licenses`, `get_by_id`, `get_by_key`, `log_validation`, `list_validations_for_license` consistentes entre Tasks 7-9 e usos posteriores
- `bootstrap_license` é mencionado na spec, no plan header e na Task 27 — mesma assinatura `() -> bool`
- `show_activation_window(initial_message: str = "") -> Optional[str]` e `show_error_window(message: str) -> None` consistentes entre Tasks 26 e 27

Plano consistente. Pronto para execução.
