# Migração Web do Processador de Ocorrências — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o app desktop PySide6 por uma web app (área logada) dentro do license-server FastAPI existente, com processamento em fila Redis+RQ, na VPS atual (`nicolasapp.duckdns.org`).

**Architecture:** O `license-server/` vira a aplicação única: FastAPI + Jinja2 + HTMX servem as telas; os núcleos `processador.py` e `vt_caixa_processador.py` migram para um pacote `core/` sem IA; jobs são enfileirados no Redis e executados por um worker RQ que grava progresso no SQLite; conflitos V1×V2 são resolvidos numa tela de revisão antes do download.

**Tech Stack:** Python 3.10+, FastAPI, Jinja2, HTMX (vendorizado), SQLite, Redis + RQ, fakeredis (testes), pdfplumber, openpyxl, xlrd, nginx + systemd na VPS.

## Global Constraints

- Todo o trabalho acontece dentro de `license-server/` (o app desktop na raiz não é tocado até a Fase 5).
- **Nenhum código de IA/Gemini** entra no `core/` nem nas rotas novas; a dependência `google-genai`, `pypdfium2` e `pillow` não entram no requirements do servidor.
- Espelhar o estilo existente do license-server: rotas síncronas (`def`, não `async def`), SQLite via `app/db.py:get_connection`, CSRF via `app/security.py`, templates Jinja2 em `app/templates/`.
- Sessões: usuário comum usa `request.session["user_id"]`; admin continua com `admin_authenticated` (não misturar).
- Datas no banco sempre `datetime.utcnow().isoformat()` (padrão já usado nas tabelas existentes).
- Uploads: máx. 50 MB por arquivo; extensões válidas: `.pdf`, `.xlsx`, `.xls`.
- Retenção de arquivos de job: **7 dias** (`expires_at`).
- Comandos de teste rodam de dentro de `license-server/`: `python -m pytest tests -q`.
- Commits frequentes, mensagens em português no padrão do repo (`feat:`, `fix:`, `docs:`).

---

## Estrutura de arquivos (visão geral)

```
license-server/
  core/
    __init__.py
    processador.py            # movido da raiz, sem verificar_com_ia
    vt_caixa_processador.py   # movido da raiz, sem IA
  app/
    config.py                 # + data_dir, redis_url (− gemini_api_key na Fase 5)
    db.py                     # + tabelas users, jobs, history
    users.py                  # NOVO: CRUD usuários
    jobs.py                   # NOVO: persistência/estado de jobs + enfileiramento
    worker_tasks.py           # NOVO: funções executadas pelo worker RQ
    history.py                # NOVO: histórico por usuário
    routes_auth.py            # NOVO: login/logout usuário
    routes_app.py             # NOVO: páginas da área do usuário
    routes_jobs.py            # NOVO: upload/status/conflitos/download
    routes_admin.py           # + CRUD de usuários
    security.py               # + require_user / current_user_id
    templates/
      app_base.html           # NOVO: layout da área do usuário
      user_login.html         # NOVO
      ocorrencias.html        # NOVO
      vt_caixa.html           # NOVO
      codigos.html            # NOVO
      historico.html          # NOVO
      job_fragment.html       # NOVO: fragmento HTMX de progresso
      conflitos.html          # NOVO: tela de revisão V1×V2
      users_list.html         # NOVO (admin)
      users_new.html          # NOVO (admin)
    static/htmx.min.js        # NOVO: vendorizado
  tests/
    core/                     # testes dos núcleos migrados
    test_users.py, test_routes_auth.py, test_jobs.py,
    test_worker_tasks.py, test_routes_jobs.py, test_history.py,
    test_retention.py, test_routes_app.py
  deploy/
    ocorrencias-web.service   # NOVO: systemd do app (referência)
    ocorrencias-worker.service# NOVO: systemd do worker RQ
```

---

## FASE 1 — Core

### Task 1: Mover `processador.py` para `core/` sem IA

**Files:**
- Create: `license-server/core/__init__.py`
- Create: `license-server/core/processador.py` (cópia de `processador.py` da raiz, menos `verificar_com_ia`)
- Test: `license-server/tests/core/test_processador.py`
- Modify: `license-server/requirements.txt`

**Interfaces:**
- Produces: `core.processador.ProcessadorOcorrencias` com métodos `extrair_ocorrencias(pdf_path, codigos_alvo)`, `extrair_ocorrencias_texto(pdf_path, codigos_alvo)`, `reconciliar(resultados, codigos_alvo)`, `montar_motivo(ocorrencias, codigos_selecionados)`, `processar(pdf_path, xlsx_path, output_path, codigos, progress_cb=None, dias_mes=None, colunas_qt_sel=None, dados_externos=None)` — assinaturas idênticas às atuais em `processador.py` da raiz.

- [ ] **Step 1: Criar pacote e copiar o módulo**

Criar `license-server/core/__init__.py` vazio e `license-server/tests/core/__init__.py` vazio. Copiar `processador.py` (raiz do repo) para `license-server/core/processador.py` e **deletar o método `verificar_com_ia` inteiro** (linhas do método completo, de `def verificar_com_ia` até o `return None` do `except`). Nada mais muda no arquivo.

- [ ] **Step 2: Adicionar dependências de processamento ao requirements do servidor**

Em `license-server/requirements.txt`, acrescentar:

```
pdfplumber~=0.11.9
openpyxl~=3.1.5
xlrd~=2.0.2
```

Rodar: `pip install -r requirements.txt` (na venv do license-server).

- [ ] **Step 3: Escrever testes do núcleo**

Se existir suíte do núcleo em `tests/` da raiz do repo, copiar os testes de processador para `license-server/tests/core/test_processador.py` ajustando o import para `from core.processador import ProcessadorOcorrencias` e removendo testes de `verificar_com_ia`. Se não existir, criar com este conteúdo mínimo:

```python
from core.processador import ProcessadorOcorrencias


def test_montar_motivo_ordena_e_quantifica():
    p = ProcessadorOcorrencias()
    ocorr = {'AT': 2, 'FA': 1, 'AP': 3}
    assert p.montar_motivo(ocorr, ['FA', 'AT', 'AP']) == 'FA, 2 AT, AP'


def test_reconciliar_concordantes_e_conflitos():
    p = ProcessadorOcorrencias()
    v1 = {'12345': {'nome': 'ANA', 'ocorrencias': {'FA': 1, 'AT': 2}}}
    v2 = {'12345': {'nome': 'ANA', 'ocorrencias': {'FA': 1, 'AT': 3}}}
    r = p.reconciliar([v1, v2], ['FA', 'AT'])
    assert r['concordantes']['12345']['ocorrencias'] == {'FA': 1}
    assert len(r['conflitos']) == 1
    assert r['conflitos'][0]['codigo'] == 'AT'
    assert r['conflitos'][0]['sugestao'] == 3


def test_ia_removida():
    assert not hasattr(ProcessadorOcorrencias, 'verificar_com_ia')
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/core/test_processador.py -v`
Expected: PASS (3 testes)

- [ ] **Step 5: Commit**

```bash
git add license-server/core license-server/tests/core license-server/requirements.txt
git commit -m "feat(web): core/processador sem IA no license-server"
```

---

### Task 2: Mover `vt_caixa_processador.py` para `core/` sem IA

**Files:**
- Create: `license-server/core/vt_caixa_processador.py` (cópia da raiz, menos IA)
- Test: `license-server/tests/core/test_vt_caixa.py`

**Interfaces:**
- Produces: `core.vt_caixa_processador.ProcessadorVTCaixa` com `processar(fonte_path, xls_path, output_path, progress_cb=None)` (parâmetros `usar_ia`, `api_key`, `model_id` removidos) retornando dict com chaves `total_pdf`, `total_fonte`, `tipo_fonte`, `total_ok`, `nao_encontrados`, `avisos_csv` (chave `alertas_ia` removida). Constantes `_CODIGOS_BENEFICIO` e `_DEPART_MAP` continuam públicas para a tela Códigos.

- [ ] **Step 1: Copiar o módulo e remover IA**

Copiar `vt_caixa_processador.py` (raiz) para `license-server/core/vt_caixa_processador.py`. Remover:
1. Os métodos `listar_modelos` e `verificar_com_ia` inteiros.
2. Na assinatura de `processar`, os parâmetros `usar_ia=False, api_key='', model_id='gemini-2.5-flash'`.
3. O bloco dentro de `processar`:

```python
        alertas_ia = []
        if usar_ia and registros:
            _prog(92, f'Verificando com IA ({model_id})...')
            alertas_ia = self.verificar_com_ia(registros, nao_encontrados, api_key, model_id)
```

4. No dict de retorno, a linha `'alertas_ia': alertas_ia,`.
5. Qualquer `import google.genai`/`genai` remanescente.

- [ ] **Step 2: Escrever testes**

Copiar os testes de VT-Caixa da suíte da raiz (se existirem) para `license-server/tests/core/test_vt_caixa.py`, ajustando import para `from core.vt_caixa_processador import ProcessadorVTCaixa` e removendo testes de IA. Garantir ao menos:

```python
from core.vt_caixa_processador import ProcessadorVTCaixa


def test_ia_removida():
    assert not hasattr(ProcessadorVTCaixa, 'verificar_com_ia')
    assert not hasattr(ProcessadorVTCaixa, 'listar_modelos')


def test_constantes_de_referencia_expostas():
    assert len(ProcessadorVTCaixa._CODIGOS_BENEFICIO) > 0
    assert len(ProcessadorVTCaixa._DEPART_MAP) > 0
```

- [ ] **Step 3: Rodar os testes**

Run: `python -m pytest tests/core -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add license-server/core/vt_caixa_processador.py license-server/tests/core/test_vt_caixa.py
git commit -m "feat(web): core/vt_caixa_processador sem IA"
```

---

## FASE 2 — Autenticação de usuários

### Task 3: Tabela `users` + módulo `users.py`

**Files:**
- Modify: `license-server/app/db.py` (SCHEMA)
- Create: `license-server/app/users.py`
- Test: `license-server/tests/test_users.py`

**Interfaces:**
- Consumes: `app.db.get_connection(db_path)`, `app.security.hash_password/verify_password`.
- Produces:
  - `users.create_user(db_path, email: str, name: str, password: str) -> int` (id; ValueError se email duplicado)
  - `users.authenticate(db_path, email: str, password: str) -> dict | None` (dict com id/email/name se válido E ativo)
  - `users.list_users(db_path) -> list[dict]`
  - `users.set_active(db_path, user_id: int, active: bool) -> None`
  - `users.set_password(db_path, user_id: int, password: str) -> None`
  - `users.get_user(db_path, user_id: int) -> dict | None`

- [ ] **Step 1: Escrever os testes**

`license-server/tests/test_users.py`:

```python
import pytest
from app import users
from app.db import init_db


@pytest.fixture
def db_path(tmp_path):
    p = str(tmp_path / "test.db")
    init_db(p)
    return p


def test_create_e_authenticate(db_path):
    uid = users.create_user(db_path, "ana@ex.com", "Ana", "s3nh4forte")
    u = users.authenticate(db_path, "ana@ex.com", "s3nh4forte")
    assert u is not None and u["id"] == uid and u["name"] == "Ana"


def test_senha_errada_e_inexistente(db_path):
    users.create_user(db_path, "ana@ex.com", "Ana", "s3nh4forte")
    assert users.authenticate(db_path, "ana@ex.com", "errada") is None
    assert users.authenticate(db_path, "nao@existe.com", "x") is None


def test_email_duplicado(db_path):
    users.create_user(db_path, "ana@ex.com", "Ana", "s3nh4forte")
    with pytest.raises(ValueError):
        users.create_user(db_path, "ana@ex.com", "Ana 2", "outra")


def test_usuario_inativo_nao_autentica(db_path):
    uid = users.create_user(db_path, "ana@ex.com", "Ana", "s3nh4forte")
    users.set_active(db_path, uid, False)
    assert users.authenticate(db_path, "ana@ex.com", "s3nh4forte") is None


def test_set_password(db_path):
    uid = users.create_user(db_path, "ana@ex.com", "Ana", "antiga")
    users.set_password(db_path, uid, "nova")
    assert users.authenticate(db_path, "ana@ex.com", "antiga") is None
    assert users.authenticate(db_path, "ana@ex.com", "nova") is not None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_users.py -v`
Expected: FAIL — `ModuleNotFoundError: app.users` (ou tabela inexistente)

- [ ] **Step 3: Implementar**

Em `app/db.py`, acrescentar ao final da string `SCHEMA`:

```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
```

Criar `app/users.py`:

```python
import sqlite3
from datetime import datetime

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


def authenticate(db_path: str, email: str, password: str) -> dict | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ? AND active = 1",
            (email.strip().lower(),),
        ).fetchone()
    if row and verify_password(password, row["password_hash"]):
        return {"id": row["id"], "email": row["email"], "name": row["name"]}
    return None


def get_user(db_path: str, user_id: int) -> dict | None:
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
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_users.py -v`
Expected: PASS (5 testes)

- [ ] **Step 5: Commit**

```bash
git add license-server/app/db.py license-server/app/users.py license-server/tests/test_users.py
git commit -m "feat(web): tabela e CRUD de usuarios"
```

---

### Task 4: Login/logout de usuário + guarda `require_user`

**Files:**
- Modify: `license-server/app/security.py`
- Create: `license-server/app/routes_auth.py`
- Create: `license-server/app/templates/user_login.html`
- Modify: `license-server/app/main.py` (incluir router)
- Test: `license-server/tests/test_routes_auth.py`

**Interfaces:**
- Consumes: `users.authenticate`.
- Produces:
  - `security.current_user_id(request) -> int | None` (lê `request.session["user_id"]`)
  - `security.require_user(request)` — levanta `HTTPException(303, Location=/login)` se não logado
  - Rotas: `GET /login`, `POST /login` (form email+password+csrf), `GET /logout`

- [ ] **Step 1: Escrever os testes**

`license-server/tests/test_routes_auth.py` (seguir o padrão de client/fixtures do `tests/conftest.py` existente — reutilizar a fixture de app/client de `test_routes_admin.py`):

```python
from app import users


def _csrf(client, path="/login"):
    client.get(path)
    return client.cookies is not None  # sessão criada


def test_login_ok_redireciona_para_app(client, db_path):
    users.create_user(db_path, "ana@ex.com", "Ana", "s3nh4forte")
    r = client.get("/login")
    assert r.status_code == 200
    # extrai csrf do form
    import re
    token = re.search(r'name="csrf_token" value="([^"]+)"', r.text).group(1)
    r = client.post("/login", data={"email": "ana@ex.com", "password": "s3nh4forte",
                                    "csrf_token": token}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/app/ocorrencias"


def test_login_senha_errada(client, db_path):
    users.create_user(db_path, "ana@ex.com", "Ana", "s3nh4forte")
    r = client.get("/login")
    import re
    token = re.search(r'name="csrf_token" value="([^"]+)"', r.text).group(1)
    r = client.post("/login", data={"email": "ana@ex.com", "password": "x",
                                    "csrf_token": token})
    assert r.status_code == 200
    assert "inválid" in r.text.lower()


def test_area_do_app_exige_login(client):
    r = client.get("/app/ocorrencias", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_logout(client, db_path, login_user):
    r = client.get("/logout", follow_redirects=False)
    assert r.status_code == 303
    r = client.get("/app/ocorrencias", follow_redirects=False)
    assert r.status_code == 303
```

Adicionar ao `tests/conftest.py` uma fixture `login_user` que cria usuário `ana@ex.com` e faz o POST de login com CSRF (mesma lógica do teste acima, reutilizável).

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_routes_auth.py -v`
Expected: FAIL — 404 nas rotas `/login`

- [ ] **Step 3: Implementar**

Em `app/security.py`, acrescentar:

```python
def current_user_id(request: Request) -> Optional[int]:
    uid = request.session.get("user_id")
    return int(uid) if uid else None


def require_user(request: Request):
    if not current_user_id(request):
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )
```

Criar `app/routes_auth.py` (usar `Jinja2Templates` do mesmo jeito que `routes_admin.py` faz):

```python
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app import users
from app.security import get_or_create_csrf_token, verify_csrf_token

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "user_login.html", {
        "csrf_token": get_or_create_csrf_token(request), "error": None,
    })


@router.post("/login")
def login_submit(request: Request, email: str = Form(...), password: str = Form(...),
                 csrf_token: str = Form(...)):
    if not verify_csrf_token(request.session.get("csrf_token"), csrf_token):
        return RedirectResponse("/login", status_code=303)
    settings = request.app.state.settings
    user = users.authenticate(settings.db_path, email, password)
    if not user:
        return templates.TemplateResponse(request, "user_login.html", {
            "csrf_token": get_or_create_csrf_token(request),
            "error": "E-mail ou senha inválidos.",
        })
    request.session["user_id"] = user["id"]
    request.session["user_name"] = user["name"]
    return RedirectResponse("/app/ocorrencias", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.pop("user_id", None)
    request.session.pop("user_name", None)
    return RedirectResponse("/login", status_code=303)
```

Criar `app/templates/user_login.html` estendendo o padrão visual de `login.html` do admin (copiar estrutura, trocar action para `/login`, campos `email` e `password`, exibir `{{ error }}` quando presente).

Em `app/main.py`: `from app.routes_auth import router as auth_router` e `fastapi_app.include_router(auth_router)`.

Para o teste `test_area_do_app_exige_login` passar já nesta task, criar em `routes_auth.py` uma rota provisória (substituída na Task 6):

```python
from app.security import require_user
from fastapi import Depends


@router.get("/app/ocorrencias", response_class=HTMLResponse)
def ocorrencias_stub(request: Request, _=Depends(require_user)):
    return HTMLResponse("ok")
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_routes_auth.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add license-server/app license-server/tests
git commit -m "feat(web): login/logout de usuario com sessao e csrf"
```

---

### Task 5: CRUD de usuários no painel admin

**Files:**
- Modify: `license-server/app/routes_admin.py`
- Create: `license-server/app/templates/users_list.html`, `users_new.html`
- Modify: `license-server/app/templates/base.html` (link "Usuários" no menu admin)
- Test: `license-server/tests/test_routes_admin_users.py`

**Interfaces:**
- Consumes: `users.create_user/list_users/set_active/set_password`, `security.require_admin`.
- Produces rotas admin: `GET /admin/users`, `GET /admin/users/new`, `POST /admin/users/new`, `POST /admin/users/{id}/toggle`, `POST /admin/users/{id}/password`.

- [ ] **Step 1: Escrever os testes**

`license-server/tests/test_routes_admin_users.py` (reutilizar fixture de admin logado do `test_routes_admin.py` existente — mesma sessão/CSRF):

```python
from app import users


def test_lista_usuarios(admin_client, db_path):
    users.create_user(db_path, "ana@ex.com", "Ana", "x12345678")
    r = admin_client.get("/admin/users")
    assert r.status_code == 200
    assert "ana@ex.com" in r.text


def test_criar_usuario(admin_client, db_path, admin_csrf):
    r = admin_client.post("/admin/users/new", data={
        "email": "novo@ex.com", "name": "Novo", "password": "s3nh4forte",
        "csrf_token": admin_csrf,
    }, follow_redirects=False)
    assert r.status_code == 303
    assert users.authenticate(db_path, "novo@ex.com", "s3nh4forte")


def test_desativar_usuario(admin_client, db_path, admin_csrf):
    uid = users.create_user(db_path, "ana@ex.com", "Ana", "s3nh4forte")
    r = admin_client.post(f"/admin/users/{uid}/toggle", data={"csrf_token": admin_csrf},
                          follow_redirects=False)
    assert r.status_code == 303
    assert users.authenticate(db_path, "ana@ex.com", "s3nh4forte") is None


def test_users_exige_admin(client):
    r = client.get("/admin/users", follow_redirects=False)
    assert r.status_code == 303
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_routes_admin_users.py -v`
Expected: FAIL — 404

- [ ] **Step 3: Implementar**

Em `routes_admin.py`, seguir exatamente o padrão das rotas de licença existentes (dependência `require_admin`, CSRF nos POSTs, redirect 303 após ação):

```python
@router.get("/admin/users", response_class=HTMLResponse)
def users_list(request: Request, _=Depends(require_admin)):
    settings = request.app.state.settings
    return templates.TemplateResponse(request, "users_list.html", {
        "users": users.list_users(settings.db_path),
        "csrf_token": get_or_create_csrf_token(request),
    })


@router.get("/admin/users/new", response_class=HTMLResponse)
def users_new_page(request: Request, _=Depends(require_admin)):
    return templates.TemplateResponse(request, "users_new.html", {
        "csrf_token": get_or_create_csrf_token(request), "error": None,
    })


@router.post("/admin/users/new")
def users_new_submit(request: Request, email: str = Form(...), name: str = Form(...),
                     password: str = Form(...), csrf_token: str = Form(...),
                     _=Depends(require_admin)):
    if not verify_csrf_token(request.session.get("csrf_token"), csrf_token):
        return RedirectResponse("/admin/users", status_code=303)
    settings = request.app.state.settings
    if len(password) < 8:
        return templates.TemplateResponse(request, "users_new.html", {
            "csrf_token": get_or_create_csrf_token(request),
            "error": "Senha deve ter ao menos 8 caracteres.",
        })
    try:
        users.create_user(settings.db_path, email, name, password)
    except ValueError as e:
        return templates.TemplateResponse(request, "users_new.html", {
            "csrf_token": get_or_create_csrf_token(request), "error": str(e),
        })
    return RedirectResponse("/admin/users", status_code=303)


@router.post("/admin/users/{user_id}/toggle")
def users_toggle(request: Request, user_id: int, csrf_token: str = Form(...),
                 _=Depends(require_admin)):
    if verify_csrf_token(request.session.get("csrf_token"), csrf_token):
        settings = request.app.state.settings
        u = users.get_user(settings.db_path, user_id)
        if u:
            users.set_active(settings.db_path, user_id, not u["active"])
    return RedirectResponse("/admin/users", status_code=303)


@router.post("/admin/users/{user_id}/password")
def users_password(request: Request, user_id: int, password: str = Form(...),
                   csrf_token: str = Form(...), _=Depends(require_admin)):
    if verify_csrf_token(request.session.get("csrf_token"), csrf_token) and len(password) >= 8:
        settings = request.app.state.settings
        users.set_password(settings.db_path, user_id, password)
    return RedirectResponse("/admin/users", status_code=303)
```

Templates `users_list.html` (tabela: email, nome, ativo, criado_em; botões toggle e redefinir senha, forms POST com csrf) e `users_new.html` (form email/nome/senha) — copiar estrutura visual de `list.html`/`new.html` existentes. Adicionar link "Usuários" no menu de `base.html`.

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_routes_admin_users.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add license-server/app license-server/tests
git commit -m "feat(web): gestao de usuarios no painel admin"
```

---

### Task 6: Layout base da área do usuário + páginas vazias

**Files:**
- Create: `license-server/app/templates/app_base.html`
- Create: `license-server/app/routes_app.py`
- Create: `license-server/app/static/htmx.min.js` (baixar https://unpkg.com/htmx.org@1.9.12/dist/htmx.min.js)
- Modify: `license-server/app/main.py` (StaticFiles + router)
- Modify: `license-server/app/routes_auth.py` (remover a rota provisória `/app/ocorrencias`)
- Test: `license-server/tests/test_routes_app.py`

**Interfaces:**
- Produces: rotas `GET /app/ocorrencias`, `/app/vt-caixa`, `/app/codigos`, `/app/historico` (todas com `Depends(require_user)`), template `app_base.html` com blocos `{% block content %}` e nav lateral com as 4 páginas + logout. `GET /` redireciona para `/app/ocorrencias`.

- [ ] **Step 1: Escrever os testes**

`license-server/tests/test_routes_app.py`:

```python
import pytest


@pytest.mark.parametrize("path", ["/app/ocorrencias", "/app/vt-caixa",
                                  "/app/codigos", "/app/historico"])
def test_paginas_exigem_login(client, path):
    r = client.get(path, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


@pytest.mark.parametrize("path", ["/app/ocorrencias", "/app/vt-caixa",
                                  "/app/codigos", "/app/historico"])
def test_paginas_carregam_logado(logged_client, path):
    r = logged_client.get(path)
    assert r.status_code == 200


def test_raiz_redireciona(logged_client):
    r = logged_client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/app/ocorrencias"
```

Adicionar fixture `logged_client` no `conftest.py` (cria usuário e faz login, devolvendo o client com sessão).

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_routes_app.py -v`
Expected: FAIL

- [ ] **Step 3: Implementar**

`app/routes_app.py`:

```python
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.security import get_or_create_csrf_token, require_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/app/ocorrencias", response_class=HTMLResponse)
def ocorrencias(request: Request, _=Depends(require_user)):
    return templates.TemplateResponse(request, "ocorrencias.html", {
        "csrf_token": get_or_create_csrf_token(request), "active": "ocorrencias",
    })


@router.get("/app/vt-caixa", response_class=HTMLResponse)
def vt_caixa(request: Request, _=Depends(require_user)):
    return templates.TemplateResponse(request, "vt_caixa.html", {
        "csrf_token": get_or_create_csrf_token(request), "active": "vt_caixa",
    })


@router.get("/app/codigos", response_class=HTMLResponse)
def codigos(request: Request, _=Depends(require_user)):
    from core.vt_caixa_processador import ProcessadorVTCaixa
    cod_rows = [(op, valor or "qualquer", cod)
                for op, valor, cod in ProcessadorVTCaixa._CODIGOS_BENEFICIO]
    return templates.TemplateResponse(request, "codigos.html", {
        "cod_rows": cod_rows, "depart_map": ProcessadorVTCaixa._DEPART_MAP,
        "active": "codigos",
    })


@router.get("/app/historico", response_class=HTMLResponse)
def historico(request: Request, _=Depends(require_user)):
    return templates.TemplateResponse(request, "historico.html", {
        "entries": [], "active": "historico",
    })
```

`app/templates/app_base.html`: HTML com nav lateral (links das 4 páginas, marca `active`, nome do usuário `{{ request.session.user_name }}` e link Sair), `<script src="/static/htmx.min.js"></script>`, bloco `content`. Estilo: CSS embutido simples e escuro, coerente com o tema do app desktop (fundo `#111318`, cartões `#1a1d24`, acento azul `#3b82f6`).

Criar `ocorrencias.html`, `vt_caixa.html`, `codigos.html`, `historico.html` estendendo `app_base.html` — por enquanto só título da página; `codigos.html` já renderiza as duas tabelas com botão "Copiar" por linha (`navigator.clipboard.writeText`).

Em `app/main.py`:

```python
from fastapi.staticfiles import StaticFiles
from app.routes_app import router as app_router
# dentro de create_app():
fastapi_app.mount("/static", StaticFiles(directory="app/static"), name="static")
fastapi_app.include_router(app_router)
```

E trocar a rota `GET /` para `return RedirectResponse("/app/ocorrencias", status_code=303)`.
Remover a rota provisória `/app/ocorrencias` de `routes_auth.py`.

- [ ] **Step 4: Rodar toda a suíte**

Run: `python -m pytest tests -q`
Expected: PASS (as rotas antigas de `/` mudaram — ajustar o teste antigo do root em `test_routes_api.py` se ele verificava o JSON `{"service": ...}`)

- [ ] **Step 5: Commit**

```bash
git add license-server/app license-server/tests
git commit -m "feat(web): layout base da area do usuario + pagina codigos"
```

---

## FASE 3 — Jobs e fluxo Ocorrências

### Task 7: Configuração (data_dir/redis) + tabela e módulo `jobs`

**Files:**
- Modify: `license-server/app/config.py`
- Modify: `license-server/app/db.py` (SCHEMA)
- Create: `license-server/app/jobs.py`
- Modify: `license-server/requirements.txt` (+ `rq~=1.16`, `redis~=5.0`; em requirements de dev/testes: `fakeredis~=2.23`)
- Test: `license-server/tests/test_jobs.py`

**Interfaces:**
- Produces:
  - `Settings` ganha `data_dir: str = "data"` (env `DATA_DIR`) e `redis_url: str = "redis://localhost:6379/0"` (env `REDIS_URL`)
  - `jobs.create_job(db_path, user_id, kind, params: dict, retention_days=7) -> str` (uuid4 hex)
  - `jobs.get_job(db_path, job_id) -> dict | None` (params/result desserializados)
  - `jobs.set_progress(db_path, job_id, progress: int, message: str)`
  - `jobs.set_status(db_path, job_id, status, result: dict | None = None, error: str | None = None)`
  - `jobs.job_dir(data_dir, job_id) -> Path` (`<data_dir>/jobs/<job_id>`; subpastas `in/` e `out/` criadas)
  - Status válidos: `queued`, `running`, `awaiting_review`, `done`, `error`, `expired`

- [ ] **Step 1: Escrever os testes**

`license-server/tests/test_jobs.py`:

```python
import pytest
from app import jobs
from app.db import init_db


@pytest.fixture
def db_path(tmp_path):
    p = str(tmp_path / "test.db")
    init_db(p)
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_jobs.py -v`
Expected: FAIL

- [ ] **Step 3: Implementar**

`app/config.py` — acrescentar campos ao dataclass e ao `load_settings`:

```python
    data_dir: str = "data"
    redis_url: str = "redis://localhost:6379/0"
# em load_settings():
    data_dir = os.environ.get("DATA_DIR", "data")
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
```

`app/db.py` — acrescentar ao SCHEMA:

```sql
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    kind TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    progress INTEGER NOT NULL DEFAULT 0,
    message TEXT,
    params TEXT,
    result TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);
```

`app/jobs.py`:

```python
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

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


def get_job(db_path: str, job_id: str) -> dict | None:
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
               result: dict | None = None, error: str | None = None) -> None:
    assert status in VALID_STATUS, status
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
```

Atualizar `requirements.txt` (+ `rq~=1.16`, `redis~=5.0`) e o arquivo de deps de teste (se `requirements.txt` for único, adicionar `fakeredis~=2.23` nele). Rodar `pip install -r requirements.txt`.

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_jobs.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add license-server/app license-server/tests license-server/requirements.txt
git commit -m "feat(web): tabela jobs, config data_dir/redis e helpers"
```

---

### Task 8: Worker task de Ocorrências (V1+V2 → reconciliar → done/awaiting_review)

**Files:**
- Create: `license-server/app/worker_tasks.py`
- Test: `license-server/tests/test_worker_tasks.py`
- Test fixtures: usar os PDFs/planilhas de exemplo da suíte da raiz se existirem (`tests/fixtures/`); senão gerar xlsx sintético com openpyxl no próprio teste.

**Interfaces:**
- Consumes: `core.processador.ProcessadorOcorrencias`, `app.jobs.*`.
- Produces:
  - `worker_tasks.run_ocorrencias(db_path: str, data_dir: str, job_id: str) -> None`
    - Lê `params` do job: `{"codigos": [...], "dias_mes": int|None, "colunas_qt_sel": [...]|None, "pdf_name": str, "xlsx_name": str}`
    - Entradas em `<job_dir>/in/<pdf_name>` e `<job_dir>/in/<xlsx_name>`; saída `<job_dir>/out/resultado.xlsx`
    - Sem conflitos → roda `processar(..., dados_externos=concordantes)` e `set_status done` com `result` = retorno de `processar` + `{"output_name": "resultado.xlsx"}`
    - Com conflitos → `set_status awaiting_review` com `result = {"concordantes": ..., "conflitos": ...}`
    - Exceção → `set_status error` com mensagem da exceção
  - `worker_tasks.finalizar_ocorrencias(db_path, data_dir, job_id, resolucoes: dict) -> dict`
    - `resolucoes`: `{"<re>|<codigo>": int}` — valores escolhidos pelo usuário
    - Monta `dados_externos` = concordantes + resoluções aplicadas, roda `processar`, grava saída, `set_status done`, retorna o result

- [ ] **Step 1: Escrever os testes**

`license-server/tests/test_worker_tasks.py`. Como PDFs reais são difíceis de sintetizar, **mockar os métodos de extração** e testar a orquestração (o núcleo em si já é testado em `tests/core/`):

```python
import pytest
from openpyxl import Workbook

from app import jobs, worker_tasks
from app.db import init_db


@pytest.fixture
def env(tmp_path):
    db = str(tmp_path / "t.db")
    init_db(db)
    return db, str(tmp_path / "data")


def _make_xlsx(path):
    wb = Workbook()
    ws = wb.active
    ws.append(["Folha RE", "Nome", "MOTIVO"])
    ws.append(["12345", "ANA", ""])
    wb.save(path)


def _setup_job(db, data_dir, params=None):
    p = {"codigos": ["FA", "AT"], "dias_mes": None, "colunas_qt_sel": None,
         "pdf_name": "jornada.pdf", "xlsx_name": "pedido.xlsx"}
    p.update(params or {})
    jid = jobs.create_job(db, 1, "ocorrencias", p)
    d = jobs.job_dir(data_dir, jid)
    (d / "in" / "jornada.pdf").write_bytes(b"%PDF-fake")
    _make_xlsx(d / "in" / "pedido.xlsx")
    return jid


def test_sem_conflito_gera_done(env, monkeypatch):
    db, data_dir = env
    dados = {"12345": {"nome": "ANA", "ocorrencias": {"FA": 1}}}
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias",
                        lambda self, p, c: dados)
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias_texto",
                        lambda self, p, c: dados)
    jid = _setup_job(db, data_dir)
    worker_tasks.run_ocorrencias(db, data_dir, jid)
    j = jobs.get_job(db, jid)
    assert j["status"] == "done"
    assert j["result"]["matched"] == 1
    assert (jobs.job_dir(data_dir, jid) / "out" / "resultado.xlsx").exists()


def test_com_conflito_aguarda_revisao_e_finaliza(env, monkeypatch):
    db, data_dir = env
    v1 = {"12345": {"nome": "ANA", "ocorrencias": {"AT": 2}}}
    v2 = {"12345": {"nome": "ANA", "ocorrencias": {"AT": 3}}}
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias",
                        lambda self, p, c: v1)
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias_texto",
                        lambda self, p, c: v2)
    jid = _setup_job(db, data_dir)
    worker_tasks.run_ocorrencias(db, data_dir, jid)
    j = jobs.get_job(db, jid)
    assert j["status"] == "awaiting_review"
    assert j["result"]["conflitos"][0]["codigo"] == "AT"

    res = worker_tasks.finalizar_ocorrencias(db, data_dir, jid, {"12345|AT": 3})
    j = jobs.get_job(db, jid)
    assert j["status"] == "done"
    assert res["matched"] == 1
    assert (jobs.job_dir(data_dir, jid) / "out" / "resultado.xlsx").exists()


def test_erro_marca_job(env, monkeypatch):
    db, data_dir = env
    def boom(self, p, c):
        raise ValueError("PDF ilegível")
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias", boom)
    jid = _setup_job(db, data_dir)
    worker_tasks.run_ocorrencias(db, data_dir, jid)
    j = jobs.get_job(db, jid)
    assert j["status"] == "error" and "PDF ilegível" in j["error"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_worker_tasks.py -v`
Expected: FAIL — módulo inexistente

- [ ] **Step 3: Implementar**

`app/worker_tasks.py`:

```python
"""Funções executadas pelo worker RQ. Recebem apenas tipos serializáveis."""
import logging

from app import jobs
from core.processador import ProcessadorOcorrencias

logger = logging.getLogger("worker")


def _progress_cb(db_path, job_id):
    def cb(pct, msg):
        jobs.set_progress(db_path, job_id, pct, msg)
    return cb


def run_ocorrencias(db_path: str, data_dir: str, job_id: str) -> None:
    try:
        job = jobs.get_job(db_path, job_id)
        params = job["params"]
        d = jobs.job_dir(data_dir, job_id)
        pdf = str(d / "in" / params["pdf_name"])
        codigos = params["codigos"]

        jobs.set_status(db_path, job_id, "running")
        cb = _progress_cb(db_path, job_id)

        p = ProcessadorOcorrencias()
        cb(10, "Lendo PDF (1ª varredura)...")
        v1 = p.extrair_ocorrencias(pdf, codigos)
        cb(30, "Lendo PDF (2ª varredura)...")
        v2 = p.extrair_ocorrencias_texto(pdf, codigos)
        rec = p.reconciliar([v1, v2], codigos)

        if rec["conflitos"]:
            jobs.set_progress(db_path, job_id, 45,
                              f"{len(rec['conflitos'])} divergência(s) aguardando revisão")
            jobs.set_status(db_path, job_id, "awaiting_review", result=rec)
            return

        result = _processar_final(db_path, data_dir, job_id, rec["concordantes"])
        jobs.set_status(db_path, job_id, "done", result=result)
    except Exception as e:
        logger.exception("job %s falhou", job_id)
        jobs.set_status(db_path, job_id, "error", error=str(e))


def finalizar_ocorrencias(db_path: str, data_dir: str, job_id: str,
                          resolucoes: dict) -> dict:
    job = jobs.get_job(db_path, job_id)
    rec = job["result"]
    dados = {re_val: dict(info) for re_val, info in rec["concordantes"].items()}
    for c in rec["conflitos"]:
        chave = f"{c['re']}|{c['codigo']}"
        valor = int(resolucoes.get(chave, c["sugestao"]))
        entry = dados.setdefault(c["re"], {"nome": c["nome"], "ocorrencias": {}})
        if valor > 0:
            entry["ocorrencias"][c["codigo"]] = valor
    result = _processar_final(db_path, data_dir, job_id, dados)
    jobs.set_status(db_path, job_id, "done", result=result)
    return result


def _processar_final(db_path: str, data_dir: str, job_id: str, dados: dict) -> dict:
    job = jobs.get_job(db_path, job_id)
    params = job["params"]
    d = jobs.job_dir(data_dir, job_id)
    out = d / "out" / "resultado.xlsx"
    p = ProcessadorOcorrencias()
    result = p.processar(
        pdf_path=None,
        xlsx_path=str(d / "in" / params["xlsx_name"]),
        output_path=str(out),
        codigos=params["codigos"],
        progress_cb=_progress_cb(db_path, job_id),
        dias_mes=params.get("dias_mes"),
        colunas_qt_sel=params.get("colunas_qt_sel"),
        dados_externos=dados,
    )
    result["output_name"] = "resultado.xlsx"
    return result
```

Nota: `processar` já aceita `dados_externos` (pula a extração do PDF), então `pdf_path=None` é seguro nesse caminho.

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_worker_tasks.py -v`
Expected: PASS (3 testes)

- [ ] **Step 5: Commit**

```bash
git add license-server/app/worker_tasks.py license-server/tests/test_worker_tasks.py
git commit -m "feat(web): worker task de ocorrencias com revisao de conflitos"
```

---

### Task 9: Upload de Ocorrências + enfileiramento RQ

**Files:**
- Create: `license-server/app/routes_jobs.py`
- Modify: `license-server/app/jobs.py` (enfileiramento)
- Modify: `license-server/app/main.py` (incluir router; criar fila no `app.state`)
- Modify: `license-server/tests/conftest.py` (fila fake síncrona)
- Test: `license-server/tests/test_routes_jobs.py`

**Interfaces:**
- Consumes: `jobs.create_job/job_dir`, `worker_tasks.run_ocorrencias`, `require_user`.
- Produces:
  - `jobs.make_queue(redis_url) -> rq.Queue` (nome `default`)
  - `jobs.enqueue_ocorrencias(queue, db_path, data_dir, job_id)` → `queue.enqueue(worker_tasks.run_ocorrencias, db_path, data_dir, job_id, job_timeout=600)`
  - `POST /app/ocorrencias` (multipart: `pdf`, `xlsx`, `codigos` múltiplo, `dias_mes` opcional, `colunas_qt` múltiplo opcional, `csrf_token`) → cria job, salva uploads, enfileira, redireciona 303 para `/app/jobs/{id}`
  - Validações: extensão (`.pdf` para pdf; `.xlsx`/`.xls` para planilha), tamanho ≤ 50 MB, ao menos 1 código → erro 400 renderizado na própria página com mensagem

- [ ] **Step 1: Configurar fila fake nos testes**

No `tests/conftest.py`, construir o app de teste com uma fila RQ síncrona sobre fakeredis e guardar em `app.state.queue`:

```python
import fakeredis
from rq import Queue

# na fixture que cria o app:
fake_conn = fakeredis.FakeStrictRedis()
test_app.state.queue = Queue("default", connection=fake_conn, is_async=False)
```

(`is_async=False` executa o job na hora, no mesmo processo — perfeito para testes.)

- [ ] **Step 2: Escrever os testes**

`license-server/tests/test_routes_jobs.py`:

```python
import io


def _upload(logged_client, csrf, pdf_name="jornada.pdf", xlsx_bytes=None):
    from openpyxl import Workbook
    if xlsx_bytes is None:
        wb = Workbook(); ws = wb.active
        ws.append(["Folha RE", "Nome", "MOTIVO"]); ws.append(["12345", "ANA", ""])
        buf = io.BytesIO(); wb.save(buf); xlsx_bytes = buf.getvalue()
    return logged_client.post("/app/ocorrencias", data={
        "codigos": ["FA", "AT"], "csrf_token": csrf,
    }, files={
        "pdf": (pdf_name, b"%PDF-fake", "application/pdf"),
        "xlsx": ("pedido.xlsx", xlsx_bytes,
                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }, follow_redirects=False)


def test_upload_cria_job_e_redireciona(logged_client, user_csrf, monkeypatch):
    dados = {"12345": {"nome": "ANA", "ocorrencias": {"FA": 1}}}
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias",
                        lambda self, p, c: dados)
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias_texto",
                        lambda self, p, c: dados)
    r = _upload(logged_client, user_csrf)
    assert r.status_code == 303
    assert r.headers["location"].startswith("/app/jobs/")


def test_upload_extensao_invalida(logged_client, user_csrf):
    r = _upload(logged_client, user_csrf, pdf_name="jornada.txt")
    assert r.status_code == 400
    assert "PDF" in r.text


def test_upload_sem_login(client):
    r = client.post("/app/ocorrencias", follow_redirects=False)
    assert r.status_code == 303
```

Fixture `user_csrf` no conftest: GET numa página logada e extrair o token do HTML (mesma regex da Task 4).

- [ ] **Step 3: Rodar e ver falhar**

Run: `python -m pytest tests/test_routes_jobs.py -v`
Expected: FAIL — 404/405

- [ ] **Step 4: Implementar**

Em `app/jobs.py`, acrescentar:

```python
def make_queue(redis_url: str):
    import redis as redis_lib
    from rq import Queue
    return Queue("default", connection=redis_lib.Redis.from_url(redis_url))


def enqueue_ocorrencias(queue, db_path: str, data_dir: str, job_id: str):
    from app import worker_tasks
    queue.enqueue(worker_tasks.run_ocorrencias, db_path, data_dir, job_id,
                  job_timeout=600)
```

Criar `app/routes_jobs.py`:

```python
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app import jobs
from app.security import current_user_id, get_or_create_csrf_token, require_user, verify_csrf_token

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

MAX_UPLOAD = 50 * 1024 * 1024


def _erro(request, template, msg, status_code=400):
    return templates.TemplateResponse(request, template, {
        "csrf_token": get_or_create_csrf_token(request), "error": msg,
        "active": template.split(".")[0],
    }, status_code=status_code)


def _salvar_upload(up: UploadFile, destino) -> Optional[str]:
    """Salva o arquivo; retorna mensagem de erro ou None."""
    data = up.file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        return "Arquivo excede 50 MB."
    destino.write_bytes(data)
    return None


@router.post("/app/ocorrencias")
def ocorrencias_submit(request: Request,
                       pdf: UploadFile = File(...),
                       xlsx: UploadFile = File(...),
                       codigos: list[str] = Form(...),
                       dias_mes: Optional[int] = Form(None),
                       colunas_qt: Optional[list[str]] = Form(None),
                       csrf_token: str = Form(...),
                       _=Depends(require_user)):
    if not verify_csrf_token(request.session.get("csrf_token"), csrf_token):
        return RedirectResponse("/app/ocorrencias", status_code=303)
    if not pdf.filename.lower().endswith(".pdf"):
        return _erro(request, "ocorrencias.html", "O arquivo de jornada deve ser PDF.")
    if not xlsx.filename.lower().endswith((".xlsx", ".xls")):
        return _erro(request, "ocorrencias.html", "A planilha de pedido deve ser Excel.")
    if not codigos:
        return _erro(request, "ocorrencias.html", "Selecione ao menos um código.")

    settings = request.app.state.settings
    uid = current_user_id(request)
    params = {"codigos": codigos, "dias_mes": dias_mes,
              "colunas_qt_sel": colunas_qt,
              "pdf_name": "jornada.pdf", "xlsx_name": "pedido.xlsx"}
    job_id = jobs.create_job(settings.db_path, uid, "ocorrencias", params)
    d = jobs.job_dir(settings.data_dir, job_id)
    for up, nome, msg in ((pdf, "jornada.pdf", "PDF"), (xlsx, "pedido.xlsx", "planilha")):
        err = _salvar_upload(up, d / "in" / nome)
        if err:
            return _erro(request, "ocorrencias.html", err)
    jobs.enqueue_ocorrencias(request.app.state.queue, settings.db_path,
                             settings.data_dir, job_id)
    return RedirectResponse(f"/app/jobs/{job_id}", status_code=303)
```

Em `app/main.py`, dentro de `create_app()`:

```python
from app import jobs as jobs_module
from app.routes_jobs import router as jobs_router
# ...
if not hasattr(fastapi_app.state, "queue") or fastapi_app.state.queue is None:
    fastapi_app.state.queue = jobs_module.make_queue(settings.redis_url)
fastapi_app.include_router(jobs_router)
```

Para os testes poderem injetar a fila fake ANTES da conexão real ser criada, `create_app()` deve aceitar `queue=None` como parâmetro opcional: `def create_app(queue=None)` e usar `queue or jobs_module.make_queue(...)`. Ajustar conftest para `create_app(queue=fake_queue)`.

Atualizar `ocorrencias.html` com o form real: dropzone/`<input type=file>` para PDF e Excel, checkboxes dos códigos (`FA, AT, A-, SD, LC, AA, AP, LM, FE, 14, 13` — iterar `ProcessadorOcorrencias.TODOS_CODIGOS` passado pelo GET da página), campo `dias_mes`, checkboxes `colunas_qt` (`qt va`, `qt vr`, `qt vt`), `{{ error }}` e botão Processar.

- [ ] **Step 5: Rodar e ver passar**

Run: `python -m pytest tests/test_routes_jobs.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add license-server/app license-server/tests
git commit -m "feat(web): upload de ocorrencias e enfileiramento rq"
```

---

### Task 10: Página do job com progresso (polling HTMX)

**Files:**
- Modify: `license-server/app/routes_jobs.py`
- Create: `license-server/app/templates/job.html`, `job_fragment.html`
- Test: `license-server/tests/test_routes_jobs.py` (acrescentar)

**Interfaces:**
- Produces:
  - `GET /app/jobs/{job_id}` → página com o fragmento embutido
  - `GET /app/jobs/{job_id}/fragment` → HTML parcial com estado atual; usado pelo HTMX (`hx-get`, `hx-trigger="every 1s"`); quando status é terminal (`done`/`error`/`awaiting_review`) o fragmento **não** inclui mais o atributo de polling
  - Ambas retornam 404 se o job não for do usuário logado

- [ ] **Step 1: Escrever os testes** (acrescentar em `test_routes_jobs.py`)

```python
def test_pagina_do_job_e_fragmento(logged_client, user_csrf, monkeypatch):
    dados = {"12345": {"nome": "ANA", "ocorrencias": {"FA": 1}}}
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias",
                        lambda self, p, c: dados)
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias_texto",
                        lambda self, p, c: dados)
    r = _upload(logged_client, user_csrf)
    job_url = r.headers["location"]
    r = logged_client.get(job_url)
    assert r.status_code == 200
    r = logged_client.get(job_url + "/fragment")
    assert r.status_code == 200
    # fila síncrona: job já está done → fragmento oferece download e não faz mais polling
    assert "download" in r.text.lower()
    assert "every 1s" not in r.text


def test_job_de_outro_usuario_404(logged_client, second_logged_client, user_csrf, monkeypatch):
    dados = {"12345": {"nome": "ANA", "ocorrencias": {"FA": 1}}}
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias",
                        lambda self, p, c: dados)
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias_texto",
                        lambda self, p, c: dados)
    r = _upload(logged_client, user_csrf)
    job_url = r.headers["location"]
    r = second_logged_client.get(job_url)
    assert r.status_code == 404
```

Fixture `second_logged_client` no conftest: segundo client com usuário `bia@ex.com` logado.

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_routes_jobs.py -v`
Expected: FAIL — 404 nas rotas novas

- [ ] **Step 3: Implementar**

Em `routes_jobs.py`:

```python
from fastapi import HTTPException


def _job_do_usuario(request: Request, job_id: str) -> dict:
    settings = request.app.state.settings
    job = jobs.get_job(settings.db_path, job_id)
    if not job or job["user_id"] != current_user_id(request):
        raise HTTPException(status_code=404)
    return job


@router.get("/app/jobs/{job_id}", response_class=HTMLResponse)
def job_page(request: Request, job_id: str, _=Depends(require_user)):
    job = _job_do_usuario(request, job_id)
    return templates.TemplateResponse(request, "job.html", {
        "job": job, "csrf_token": get_or_create_csrf_token(request),
        "active": job["kind"],
    })


@router.get("/app/jobs/{job_id}/fragment", response_class=HTMLResponse)
def job_fragment(request: Request, job_id: str, _=Depends(require_user)):
    job = _job_do_usuario(request, job_id)
    return templates.TemplateResponse(request, "job_fragment.html", {
        "job": job, "csrf_token": get_or_create_csrf_token(request),
    })
```

`job.html` (estende `app_base.html`):

```html
{% extends "app_base.html" %}
{% block content %}
<h1>Processamento</h1>
<div id="job-box">{% include "job_fragment.html" %}</div>
{% endblock %}
```

`job_fragment.html`:

```html
{% if job.status in ("queued", "running") %}
<div hx-get="/app/jobs/{{ job.id }}/fragment" hx-trigger="every 1s"
     hx-target="#job-box" hx-swap="innerHTML">
  <progress value="{{ job.progress }}" max="100"></progress>
  <p>{{ job.message or "Na fila..." }}</p>
</div>
{% elif job.status == "awaiting_review" %}
<p>{{ job.result.conflitos | length }} divergência(s) precisam de revisão.</p>
<a class="btn" href="/app/jobs/{{ job.id }}/conflitos">Revisar divergências</a>
{% elif job.status == "done" %}
<p>Concluído — {{ job.result.matched }} registro(s) atualizados,
   {{ job.result.nao_encontrados | length }} não localizados.</p>
<a class="btn" href="/app/jobs/{{ job.id }}/download">Baixar resultado</a>
{% elif job.status == "error" %}
<p class="error">Falhou: {{ job.error }}</p>
<a class="btn" href="/app/{{ 'ocorrencias' if job.kind == 'ocorrencias' else 'vt-caixa' }}">Tentar novamente</a>
{% elif job.status == "expired" %}
<p>Este processamento expirou (arquivos são mantidos por 7 dias).</p>
{% endif %}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_routes_jobs.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add license-server/app license-server/tests
git commit -m "feat(web): pagina de job com progresso via htmx"
```

---

### Task 11: Tela de revisão de conflitos + finalização

**Files:**
- Modify: `license-server/app/routes_jobs.py`
- Create: `license-server/app/templates/conflitos.html`
- Test: `license-server/tests/test_routes_jobs.py` (acrescentar)

**Interfaces:**
- Consumes: `worker_tasks.finalizar_ocorrencias(db_path, data_dir, job_id, resolucoes)`.
- Produces:
  - `GET /app/jobs/{job_id}/conflitos` → tabela com um input numérico por conflito (name=`res_<re>|<codigo>`, value=sugestão) mostrando os valores v1/v2
  - `POST /app/jobs/{job_id}/conflitos` → monta `resolucoes` a partir dos campos `res_*`, chama `finalizar_ocorrencias`, redireciona 303 para `/app/jobs/{id}`
  - Ambas 404 se o job não for do usuário ou status ≠ `awaiting_review`

- [ ] **Step 1: Escrever os testes** (acrescentar em `test_routes_jobs.py`)

```python
def _upload_com_conflito(logged_client, user_csrf, monkeypatch):
    v1 = {"12345": {"nome": "ANA", "ocorrencias": {"AT": 2}}}
    v2 = {"12345": {"nome": "ANA", "ocorrencias": {"AT": 3}}}
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias",
                        lambda self, p, c: v1)
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias_texto",
                        lambda self, p, c: v2)
    return _upload(logged_client, user_csrf)


def test_fluxo_de_conflito(logged_client, user_csrf, monkeypatch):
    r = _upload_com_conflito(logged_client, user_csrf, monkeypatch)
    job_url = r.headers["location"]

    r = logged_client.get(job_url + "/conflitos")
    assert r.status_code == 200
    assert "12345" in r.text and "AT" in r.text

    import re as _re
    token = _re.search(r'name="csrf_token" value="([^"]+)"', r.text).group(1)
    r = logged_client.post(job_url + "/conflitos",
                           data={"res_12345|AT": "3", "csrf_token": token},
                           follow_redirects=False)
    assert r.status_code == 303

    r = logged_client.get(job_url + "/fragment")
    assert "Baixar" in r.text


def test_conflitos_404_quando_nao_ha(logged_client, user_csrf, monkeypatch):
    dados = {"12345": {"nome": "ANA", "ocorrencias": {"FA": 1}}}
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias",
                        lambda self, p, c: dados)
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias_texto",
                        lambda self, p, c: dados)
    r = _upload(logged_client, user_csrf)
    r = logged_client.get(r.headers["location"] + "/conflitos")
    assert r.status_code == 404
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_routes_jobs.py -v`
Expected: FAIL

- [ ] **Step 3: Implementar**

Em `routes_jobs.py`:

```python
from app import worker_tasks


@router.get("/app/jobs/{job_id}/conflitos", response_class=HTMLResponse)
def conflitos_page(request: Request, job_id: str, _=Depends(require_user)):
    job = _job_do_usuario(request, job_id)
    if job["status"] != "awaiting_review":
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(request, "conflitos.html", {
        "job": job, "csrf_token": get_or_create_csrf_token(request),
        "active": "ocorrencias",
    })


@router.post("/app/jobs/{job_id}/conflitos")
async def conflitos_submit(request: Request, job_id: str, _=Depends(require_user)):
    job = _job_do_usuario(request, job_id)
    if job["status"] != "awaiting_review":
        raise HTTPException(status_code=404)
    form = await request.form()
    if not verify_csrf_token(request.session.get("csrf_token"), form.get("csrf_token")):
        return RedirectResponse(f"/app/jobs/{job_id}/conflitos", status_code=303)
    resolucoes = {k[len("res_"):]: v for k, v in form.items() if k.startswith("res_")}
    settings = request.app.state.settings
    worker_tasks.finalizar_ocorrencias(settings.db_path, settings.data_dir,
                                       job_id, resolucoes)
    return RedirectResponse(f"/app/jobs/{job_id}", status_code=303)
```

(Esta rota é `async` só por causa de `request.form()`; a finalização é rápida — segundos — e roda na própria requisição, conforme a spec.)

`conflitos.html` (estende `app_base.html`): form POST para a própria URL, tabela com colunas RE / Nome / Código / 1ª varredura / 2ª varredura / Valor final, onde "Valor final" é `<input type="number" min="0" name="res_{{ c.re }}|{{ c.codigo }}" value="{{ c.sugestao }}">`; iterar `job.result.conflitos` (cada `c` tem `re`, `nome`, `codigo`, `valores.v1`, `valores.v2`, `sugestao`). Botão "Aplicar e gerar planilha".

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_routes_jobs.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add license-server/app license-server/tests
git commit -m "feat(web): tela de revisao de divergencias v1xv2"
```

---

### Task 12: Download do resultado

**Files:**
- Modify: `license-server/app/routes_jobs.py`
- Test: `license-server/tests/test_routes_jobs.py` (acrescentar)

**Interfaces:**
- Produces: `GET /app/jobs/{job_id}/download` → `FileResponse` de `<job_dir>/out/<output_name>`; 404 se job não é do usuário, status ≠ `done`, ou arquivo ausente. `Content-Disposition: attachment`, filename `ocorrencias-<job_id[:8]>.xlsx` (ou `vt-caixa-<id>.csv` quando `kind == "vt_caixa"`).

- [ ] **Step 1: Escrever os testes**

```python
def test_download_do_resultado(logged_client, user_csrf, monkeypatch):
    dados = {"12345": {"nome": "ANA", "ocorrencias": {"FA": 1}}}
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias",
                        lambda self, p, c: dados)
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias_texto",
                        lambda self, p, c: dados)
    r = _upload(logged_client, user_csrf)
    r = logged_client.get(r.headers["location"] + "/download")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert len(r.content) > 1000  # xlsx real


def test_download_de_outro_usuario_404(logged_client, second_logged_client,
                                       user_csrf, monkeypatch):
    dados = {"12345": {"nome": "ANA", "ocorrencias": {"FA": 1}}}
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias",
                        lambda self, p, c: dados)
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias_texto",
                        lambda self, p, c: dados)
    r = _upload(logged_client, user_csrf)
    r = second_logged_client.get(r.headers["location"] + "/download")
    assert r.status_code == 404
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_routes_jobs.py -v`
Expected: FAIL

- [ ] **Step 3: Implementar**

```python
from fastapi.responses import FileResponse


@router.get("/app/jobs/{job_id}/download")
def job_download(request: Request, job_id: str, _=Depends(require_user)):
    job = _job_do_usuario(request, job_id)
    if job["status"] != "done" or not job["result"]:
        raise HTTPException(status_code=404)
    settings = request.app.state.settings
    path = jobs.job_dir(settings.data_dir, job_id) / "out" / job["result"]["output_name"]
    if not path.exists():
        raise HTTPException(status_code=404)
    ext = path.suffix
    prefixo = "ocorrencias" if job["kind"] == "ocorrencias" else "vt-caixa"
    return FileResponse(path, filename=f"{prefixo}-{job_id[:8]}{ext}",
                        media_type="application/octet-stream")
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_routes_jobs.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add license-server/app/routes_jobs.py license-server/tests/test_routes_jobs.py
git commit -m "feat(web): download autenticado do resultado"
```

---

### Task 13: Retenção de 7 dias (limpeza)

**Files:**
- Modify: `license-server/app/jobs.py`
- Create: `license-server/cleanup.py` (script chamado por cron)
- Test: `license-server/tests/test_retention.py`

**Interfaces:**
- Produces:
  - `jobs.cleanup_expired(db_path, data_dir) -> int` — para cada job com `expires_at < agora` e status ≠ `expired`: apaga `data/jobs/<id>/` inteiro e seta status `expired`; retorna quantos limpou
  - `cleanup.py`: script standalone que carrega settings do env e chama `cleanup_expired` (cron diário na VPS)

- [ ] **Step 1: Escrever os testes**

`license-server/tests/test_retention.py`:

```python
from datetime import datetime, timedelta

from app import jobs
from app.db import get_connection, init_db


def test_cleanup_apaga_expirados(tmp_path):
    db = str(tmp_path / "t.db")
    init_db(db)
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_retention.py -v`
Expected: FAIL

- [ ] **Step 3: Implementar**

Em `app/jobs.py`:

```python
import shutil
# ...

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
```

`license-server/cleanup.py`:

```python
"""Limpeza de jobs expirados — agendar no cron: diário.

Ex.: 15 3 * * * cd /opt/ocorrencias && .venv/bin/python cleanup.py
"""
from app.config import load_settings
from app.jobs import cleanup_expired

if __name__ == "__main__":
    s = load_settings()
    n = cleanup_expired(s.db_path, s.data_dir)
    print(f"{n} job(s) expirados removidos")
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_retention.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add license-server/app/jobs.py license-server/cleanup.py license-server/tests/test_retention.py
git commit -m "feat(web): retencao de 7 dias com limpeza via cron"
```

---

### Task 14: Histórico por usuário

**Files:**
- Modify: `license-server/app/db.py` (SCHEMA)
- Create: `license-server/app/history.py`
- Modify: `license-server/app/worker_tasks.py` (gravar entrada ao concluir/errar)
- Modify: `license-server/app/routes_app.py` (tela com busca/filtro/export)
- Modify: `license-server/app/templates/historico.html`
- Test: `license-server/tests/test_history.py`

**Interfaces:**
- Produces:
  - Tabela `history`: id, user_id, job_id, kind, status (`sucesso` | `erro`), input_names (JSON), counts (JSON: matched/total/nao_encontrados...), created_at
  - `history.add(db_path, user_id, job_id, kind, status, input_names: list[str], counts: dict) -> int`
  - `history.list_for_user(db_path, user_id, q: str = "", status: str = "") -> list[dict]` (busca em input_names, mais recente primeiro)
  - `GET /app/historico?q=&status=` → tabela com link para o job; `GET /app/historico.csv` → export CSV
  - `worker_tasks.run_ocorrencias` e `finalizar_ocorrencias` gravam no histórico quando o job chega a `done`/`error`

- [ ] **Step 1: Escrever os testes**

`license-server/tests/test_history.py`:

```python
from app import history
from app.db import init_db
import pytest


@pytest.fixture
def db_path(tmp_path):
    p = str(tmp_path / "t.db")
    init_db(p)
    return p


def test_add_e_list(db_path):
    history.add(db_path, 1, "job1", "ocorrencias", "sucesso",
                ["jornada.pdf", "pedido.xlsx"], {"matched": 10})
    history.add(db_path, 2, "job2", "vt_caixa", "erro", ["nautilus.pdf"], {})
    lst = history.list_for_user(db_path, 1)
    assert len(lst) == 1
    assert lst[0]["counts"]["matched"] == 10


def test_filtros(db_path):
    history.add(db_path, 1, "j1", "ocorrencias", "sucesso", ["marco.pdf"], {})
    history.add(db_path, 1, "j2", "ocorrencias", "erro", ["abril.pdf"], {})
    assert len(history.list_for_user(db_path, 1, q="marco")) == 1
    assert len(history.list_for_user(db_path, 1, status="erro")) == 1


def test_tela_e_export(logged_client, db_path_app, logged_user_id):
    history.add(db_path_app, logged_user_id, "j1", "ocorrencias", "sucesso",
                ["jornada.pdf"], {"matched": 5})
    r = logged_client.get("/app/historico")
    assert "jornada.pdf" in r.text
    r = logged_client.get("/app/historico.csv")
    assert r.status_code == 200
    assert "jornada.pdf" in r.text
```

(`db_path_app`/`logged_user_id`: expor no conftest o db usado pelo app de teste e o id do usuário logado.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_history.py -v`
Expected: FAIL

- [ ] **Step 3: Implementar**

SCHEMA:

```sql
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    job_id TEXT,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    input_names TEXT,
    counts TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_history_user_id ON history(user_id);
```

`app/history.py`:

```python
import json
from datetime import datetime

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


def list_for_user(db_path: str, user_id: int, q: str = "", status: str = "") -> list[dict]:
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
```

Em `worker_tasks.py`, gravar histórico nos desfechos. No fim de `run_ocorrencias` (caminho `done`), no fim de `finalizar_ocorrencias`, e no `except`:

```python
from app import history

# helper no módulo:
def _registrar_historico(db_path, job_id, status_hist, counts):
    job = jobs.get_job(db_path, job_id)
    nomes = [job["params"].get("pdf_name", ""), job["params"].get("xlsx_name", "")]
    nomes += [job["params"].get("fonte_name", ""), job["params"].get("cadastral_name", "")]
    history.add(db_path, job["user_id"], job_id, job["kind"], status_hist,
                [n for n in nomes if n], counts)

# no done de run_ocorrencias e de finalizar_ocorrencias:
_registrar_historico(db_path, job_id, "sucesso",
                     {"matched": result["matched"],
                      "nao_encontrados": len(result["nao_encontrados"])})
# no except de run_ocorrencias:
_registrar_historico(db_path, job_id, "erro", {})
```

Guardar os **nomes originais** dos uploads: na Task 9, acrescentar aos params `"orig_pdf": pdf.filename, "orig_xlsx": xlsx.filename` e usar esses nomes no histórico em vez dos internos (ajustar `_registrar_historico` para preferir `orig_*` quando presentes).

Rota do histórico em `routes_app.py` (substituir o stub):

```python
import csv
import io

from fastapi.responses import PlainTextResponse

from app import history
from app.security import current_user_id


@router.get("/app/historico", response_class=HTMLResponse)
def historico(request: Request, q: str = "", status: str = "", _=Depends(require_user)):
    settings = request.app.state.settings
    entries = history.list_for_user(settings.db_path, current_user_id(request), q, status)
    return templates.TemplateResponse(request, "historico.html", {
        "entries": entries, "q": q, "status": status, "active": "historico",
    })


@router.get("/app/historico.csv")
def historico_csv(request: Request, q: str = "", status: str = "", _=Depends(require_user)):
    settings = request.app.state.settings
    entries = history.list_for_user(settings.db_path, current_user_id(request), q, status)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["data", "tipo", "status", "arquivos", "detalhes"])
    for e in entries:
        w.writerow([e["created_at"], e["kind"], e["status"],
                    "; ".join(e["input_names"]), json.dumps(e["counts"], ensure_ascii=False)])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=historico.csv"})
```

`historico.html`: form GET com input `q` + select `status` (todos/sucesso/erro), tabela (data, tipo, arquivos, contagens, link "abrir" para `/app/jobs/{{ e.job_id }}`), botão "Exportar CSV".

- [ ] **Step 4: Rodar toda a suíte**

Run: `python -m pytest tests -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add license-server/app license-server/tests
git commit -m "feat(web): historico por usuario com busca, filtro e export"
```

---

## FASE 4 — VT-Caixa

### Task 15: Worker task + upload + telas do VT-Caixa

**Files:**
- Modify: `license-server/app/worker_tasks.py`
- Modify: `license-server/app/jobs.py` (enqueue)
- Modify: `license-server/app/routes_jobs.py` (POST /app/vt-caixa)
- Modify: `license-server/app/templates/vt_caixa.html`
- Test: `license-server/tests/test_worker_tasks.py` e `test_routes_jobs.py` (acrescentar)

**Interfaces:**
- Consumes: `core.vt_caixa_processador.ProcessadorVTCaixa.processar(fonte_path, xls_path, output_path, progress_cb)`.
- Produces:
  - `worker_tasks.run_vt_caixa(db_path, data_dir, job_id)` — params: `{"fonte_name": str, "cadastral_name": str, "orig_fonte": str, "orig_cadastral": str}`; entrada `in/fonte.<ext>` e `in/cadastral.<ext>`; saída `out/beneficios.csv`; sem etapa de conflito (fluxo direto done/error); grava histórico com counts `{"total_fonte", "total_ok", "nao_encontrados"}`
  - `jobs.enqueue_vt_caixa(queue, db_path, data_dir, job_id)`
  - `POST /app/vt-caixa` (multipart: `fonte` [.pdf/.xlsx/.xls], `cadastral` [.xlsx/.xls], `csrf_token`) → job + redirect `/app/jobs/{id}`
  - O `result` do job inclui `output_name: "beneficios.csv"`, `total_ok`, `nao_encontrados` (lista), `avisos_csv`

- [ ] **Step 1: Escrever os testes**

Em `test_worker_tasks.py`:

```python
def test_vt_caixa_done(env, monkeypatch):
    db, data_dir = env
    resultado = {"total_pdf": 5, "total_fonte": 5, "tipo_fonte": "PDF",
                 "total_ok": 4, "nao_encontrados": [{"codigo": "999"}],
                 "avisos_csv": []}

    def fake_processar(self, fonte_path, xls_path, output_path, progress_cb=None):
        from pathlib import Path
        Path(output_path).write_text("CNPJ;CEP\n", encoding="latin-1")
        return resultado

    monkeypatch.setattr("core.vt_caixa_processador.ProcessadorVTCaixa.processar",
                        fake_processar)
    jid = jobs.create_job(db, 1, "vt_caixa", {
        "fonte_name": "fonte.pdf", "cadastral_name": "cadastral.xlsx",
        "orig_fonte": "nautilus.pdf", "orig_cadastral": "cad.xlsx"})
    d = jobs.job_dir(data_dir, jid)
    (d / "in" / "fonte.pdf").write_bytes(b"%PDF")
    (d / "in" / "cadastral.xlsx").write_bytes(b"xx")
    worker_tasks.run_vt_caixa(db, data_dir, jid)
    j = jobs.get_job(db, jid)
    assert j["status"] == "done"
    assert j["result"]["total_ok"] == 4
    assert j["result"]["output_name"] == "beneficios.csv"
    assert (d / "out" / "beneficios.csv").exists()
```

Em `test_routes_jobs.py`:

```python
def test_upload_vt_caixa(logged_client, user_csrf, monkeypatch):
    def fake_processar(self, fonte_path, xls_path, output_path, progress_cb=None):
        from pathlib import Path
        Path(output_path).write_text("CNPJ\n", encoding="latin-1")
        return {"total_pdf": 1, "total_fonte": 1, "tipo_fonte": "PDF",
                "total_ok": 1, "nao_encontrados": [], "avisos_csv": []}
    monkeypatch.setattr("core.vt_caixa_processador.ProcessadorVTCaixa.processar",
                        fake_processar)
    r = logged_client.post("/app/vt-caixa", data={"csrf_token": user_csrf}, files={
        "fonte": ("nautilus.pdf", b"%PDF", "application/pdf"),
        "cadastral": ("cad.xlsx", b"xx", "application/octet-stream"),
    }, follow_redirects=False)
    assert r.status_code == 303
    job_url = r.headers["location"]
    r = logged_client.get(job_url + "/download")
    assert r.status_code == 200
    assert "vt-caixa" in r.headers["content-disposition"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_worker_tasks.py tests/test_routes_jobs.py -v`
Expected: FAIL nas funções novas

- [ ] **Step 3: Implementar**

`worker_tasks.py`:

```python
from core.vt_caixa_processador import ProcessadorVTCaixa


def run_vt_caixa(db_path: str, data_dir: str, job_id: str) -> None:
    try:
        job = jobs.get_job(db_path, job_id)
        params = job["params"]
        d = jobs.job_dir(data_dir, job_id)
        jobs.set_status(db_path, job_id, "running")
        p = ProcessadorVTCaixa()
        result = p.processar(
            fonte_path=str(d / "in" / params["fonte_name"]),
            xls_path=str(d / "in" / params["cadastral_name"]),
            output_path=str(d / "out" / "beneficios.csv"),
            progress_cb=_progress_cb(db_path, job_id),
        )
        result["output_name"] = "beneficios.csv"
        jobs.set_status(db_path, job_id, "done", result=result)
        _registrar_historico(db_path, job_id, "sucesso", {
            "total_fonte": result["total_fonte"], "total_ok": result["total_ok"],
            "nao_encontrados": len(result["nao_encontrados"]),
        })
    except Exception as e:
        logger.exception("job %s falhou", job_id)
        jobs.set_status(db_path, job_id, "error", error=str(e))
        _registrar_historico(db_path, job_id, "erro", {})
```

`jobs.py`:

```python
def enqueue_vt_caixa(queue, db_path: str, data_dir: str, job_id: str):
    from app import worker_tasks
    queue.enqueue(worker_tasks.run_vt_caixa, db_path, data_dir, job_id,
                  job_timeout=600)
```

`routes_jobs.py`:

```python
@router.post("/app/vt-caixa")
def vt_caixa_submit(request: Request,
                    fonte: UploadFile = File(...),
                    cadastral: UploadFile = File(...),
                    csrf_token: str = Form(...),
                    _=Depends(require_user)):
    if not verify_csrf_token(request.session.get("csrf_token"), csrf_token):
        return RedirectResponse("/app/vt-caixa", status_code=303)
    if not fonte.filename.lower().endswith((".pdf", ".xlsx", ".xls")):
        return _erro(request, "vt_caixa.html", "A fonte deve ser PDF ou Excel.")
    if not cadastral.filename.lower().endswith((".xlsx", ".xls")):
        return _erro(request, "vt_caixa.html", "O cadastral deve ser Excel.")

    ext_fonte = "." + fonte.filename.rsplit(".", 1)[1].lower()
    ext_cad = "." + cadastral.filename.rsplit(".", 1)[1].lower()
    settings = request.app.state.settings
    params = {"fonte_name": f"fonte{ext_fonte}", "cadastral_name": f"cadastral{ext_cad}",
              "orig_fonte": fonte.filename, "orig_cadastral": cadastral.filename}
    job_id = jobs.create_job(settings.db_path, current_user_id(request), "vt_caixa", params)
    d = jobs.job_dir(settings.data_dir, job_id)
    for up, nome in ((fonte, params["fonte_name"]), (cadastral, params["cadastral_name"])):
        err = _salvar_upload(up, d / "in" / nome)
        if err:
            return _erro(request, "vt_caixa.html", err)
    jobs.enqueue_vt_caixa(request.app.state.queue, settings.db_path,
                          settings.data_dir, job_id)
    return RedirectResponse(f"/app/jobs/{job_id}", status_code=303)
```

`vt_caixa.html`: form multipart com os dois uploads + botão Processar + `{{ error }}`. No `job_fragment.html`, quando `job.kind == "vt_caixa"` e status done, mostrar também `total_ok`/`nao_encontrados` e, se houver, a lista de não encontrados (`job.result.nao_encontrados`).

- [ ] **Step 4: Rodar toda a suíte**

Run: `python -m pytest tests -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add license-server/app license-server/tests
git commit -m "feat(web): fluxo vt-caixa completo"
```

---

## FASE 5 — Corte e infra

### Task 16: Remover IA e licenças/releases do servidor

**Files:**
- Modify: `license-server/app/config.py` (remover `gemini_api_key`)
- Modify: `license-server/app/routes_admin.py` (remover tela/rota de config da key Gemini)
- Delete: `license-server/app/templates/config.html`
- Modify: `license-server/app/main.py` (remover `routes_api`/`routes_update` — rotas de licença e release do desktop)
- Delete: `license-server/app/routes_api.py`, `routes_update.py`, `keygen.py`, `licenses.py`, `releases.py` e templates de licenças (`dashboard.html` ajustar, `detail.html`, `list.html`, `new.html`, `releases.html`)
- Delete: testes correspondentes (`test_routes_api.py`, `test_routes_update.py`, `test_keygen.py`, `test_licenses.py`, `test_releases.py`)
- Test: suíte inteira

**ATENÇÃO:** esta task só executa quando o corte for autorizado (usuários migrados). Até lá, o plano para na Task 15 + Task 17.

- [ ] **Step 1: Remover módulos e rotas** conforme a lista acima. No `main.py`, remover imports/includes de `api_router` e `update_router` e o handler de rate-limit se só era usado por eles. O menu do admin perde "Licenças"/"Releases"/"Config" e mantém "Usuários".
- [ ] **Step 2: Rodar a suíte**

Run: `python -m pytest tests -q`
Expected: PASS (sem os testes deletados)

- [ ] **Step 3: Grep de sobras**

Run: `grep -ri "gemini\|license_key\|keygen" app/ core/ tests/` (Git Bash) — esperado: nenhuma ocorrência.

- [ ] **Step 4: Commit**

```bash
git add -A license-server
git commit -m "feat(web): remove licencas, releases e config de IA do servidor"
```

---

### Task 17: Infra da VPS + deploy

**Files:**
- Create: `license-server/deploy/ocorrencias-web.service`
- Create: `license-server/deploy/ocorrencias-worker.service`
- Create: `license-server/deploy/nginx-snippet.conf`
- Modify: `deploy.py` (raiz — simplificar: sem release de exe; envia código, instala deps, reinicia app+worker)
- Modify: `license-server/README.md` (instruções novas)

Sem TDD aqui — é configuração; validação é manual na VPS.

- [ ] **Step 1: Escrever units systemd**

`deploy/ocorrencias-web.service`:

```ini
[Unit]
Description=Processador de Ocorrencias — web app
After=network.target redis-server.service

[Service]
User=www-data
WorkingDirectory=/opt/ocorrencias
EnvironmentFile=/opt/ocorrencias/.env.systemd
ExecStart=/opt/ocorrencias/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

`deploy/ocorrencias-worker.service`:

```ini
[Unit]
Description=Processador de Ocorrencias — worker RQ
After=network.target redis-server.service

[Service]
User=www-data
WorkingDirectory=/opt/ocorrencias
EnvironmentFile=/opt/ocorrencias/.env.systemd
ExecStart=/opt/ocorrencias/.venv/bin/rq worker default
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

(Ajustar caminho `/opt/ocorrencias` para onde o license-server já está instalado na VPS — verificar com `systemctl cat <serviço atual>` antes.)

`deploy/nginx-snippet.conf`:

```nginx
# dentro do server {} existente do nicolasapp.duckdns.org:
client_max_body_size 50m;
location /static/ {
    proxy_pass http://127.0.0.1:8000;
    expires 7d;
}
```

- [ ] **Step 2: Atualizar deploy.py**

Remover do `deploy.py` a parte de `--release`/upload de exe. Manter: rsync/scp dos arquivos de `license-server/` (agora incluindo `core/`, `cleanup.py`, `static/`), `pip install -r requirements.txt` remoto, `systemctl restart ocorrencias-web ocorrencias-worker`.

- [ ] **Step 3: Checklist manual na VPS** (documentar no README):

```
1. ssh na VPS
2. sudo apt install redis-server && sudo systemctl enable --now redis-server
3. Copiar units para /etc/systemd/system/ + systemctl daemon-reload
4. Adicionar DATA_DIR=/opt/ocorrencias/data e REDIS_URL=redis://localhost:6379/0 ao env
5. Ajustar nginx (client_max_body_size) + nginx -t + reload
6. systemctl enable --now ocorrencias-web ocorrencias-worker
7. Cron: 15 3 * * * cd /opt/ocorrencias && .venv/bin/python cleanup.py
8. Criar os usuários no /admin/users
9. Testar fluxo completo: login → ocorrências → conflito → download; vt-caixa → download
10. Backup do sqlite já existente continua valendo
```

- [ ] **Step 4: Commit**

```bash
git add license-server/deploy deploy.py license-server/README.md
git commit -m "feat(web): units systemd, nginx e deploy simplificado"
```

---

### Task 18: Aposentadoria do desktop (pós-migração)

Executar somente depois que os usuários confirmarem que a web atende.

- [ ] **Step 1:** Mover `app.py`, `ui/`, `auto_update.py`, `license_client.py`, `processador.py`, `vt_caixa_processador.py`, `*.spec` da raiz para `legacy-desktop/` (preserva histórico, tira do caminho).
- [ ] **Step 2:** Atualizar `README.md` da raiz descrevendo a arquitetura web.
- [ ] **Step 3:** Rodar `python -m pytest license-server/tests -q` → PASS.
- [ ] **Step 4:** Commit: `git commit -m "chore: aposenta app desktop apos migracao web"`.

---

## Self-review (executado na escrita do plano)

- **Cobertura da spec:** core sem IA (T1–T2), auth (T3–T5), layout+códigos (T6), jobs+fila (T7–T9), progresso (T10), conflitos (T11), download (T12), retenção (T13), histórico (T14), vt-caixa (T15), remoção licenças/IA (T16), infra/deploy (T17), corte (T18). ✔
- **Divergência da spec:** a página Códigos renderiza as constantes do `core/` em modo somente leitura (sem edição pelo admin) — os dados hoje vivem no código e a edição não tem demanda; a spec foi ajustada.
- **Tipos consistentes:** `run_ocorrencias/finalizar_ocorrencias/run_vt_caixa` usam a mesma assinatura `(db_path, data_dir, job_id, ...)`; `result.output_name` usado por T10/T12/T15. ✔
