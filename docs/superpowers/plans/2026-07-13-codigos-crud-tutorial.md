# Códigos personalizados + remoção Dias/Qt + tutorial guiado — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Usuários criam/excluem códigos de benefício e substituições de departamento pela página Códigos (valendo no processamento VT-Caixa), os campos "Dias no mês"/"Colunas Qt" somem do fluxo de Ocorrências, e um tour interativo (driver.js) roda no primeiro acesso com botão de repetição na barra lateral.

**Architecture:** Duas tabelas novas no SQLite (`custom_benefit_codes`, `custom_depart_subs`) geridas por `app/ref_codes.py`; o core `ProcessadorVTCaixa` ganha parâmetros opcionais `codigos_extras`/`depart_extras` com precedência sobre os embutidos; o worker injeta os extras lidos do banco no momento do job. A página Códigos ganha forms HTMX de adicionar/excluir. Tutorial: driver.js vendorizado + `tour.js` com segmentos por página ancorados em `data-tour`, estado `tutorial_seen` na tabela `users`.

**Tech Stack:** FastAPI, Jinja2, HTMX (já vendorizado), SQLite, driver.js 1.3.1 (vendorizar), pytest.

## Global Constraints

- Todo o trabalho acontece dentro de `license-server/`; comandos de teste rodam de lá: `python -m pytest tests -q`.
- Espelhar o estilo existente: rotas síncronas (`def`), SQLite via `app/db.py:get_connection`, CSRF via `verify_csrf_token`/`get_or_create_csrf_token` de `app/security.py`, datas `datetime.utcnow().isoformat()`.
- **Nenhum recurso via CDN em runtime** — driver.js e seu CSS são baixados uma vez e servidos de `app/static/`.
- Personalizados são **globais** (qualquer usuário logado cria/exclui) e têm **precedência** sobre os embutidos.
- Constantes embutidas `_CODIGOS_BENEFICIO`/`_DEPART_MAP` do core **não mudam**.
- "Dias no mês"/"Colunas Qt": remoção **completa** (form, rota, params do job, worker e core).
- Commits frequentes em português no padrão do repo (`feat:`, `fix:`).
- A suíte inteira deve estar verde ao fim de cada task.

---

## Estrutura de arquivos

```
license-server/
  app/
    ref_codes.py                          # NOVO: CRUD dos personalizados
    routes_codigos.py                     # NOVO: página Códigos + fragmentos HTMX
    routes_app.py                         # − rota /app/codigos (migra) + rota tutorial/seen
    users.py                              # + mark_tutorial_seen / tutorial_seen no dict
    db.py                                 # + 2 tabelas + coluna tutorial_seen (migração)
    worker_tasks.py                       # run_vt_caixa injeta extras; − dias_mes/colunas_qt
    routes_jobs.py                        # − dias_mes/colunas_qt
    static/
      driver.js.iife.js                   # NOVO (vendorizado)
      driver.css                          # NOVO (vendorizado)
      tour.js                             # NOVO: segmentos do tutorial
    templates/
      app_base.html                       # + data-tour, botão "? Ver tutorial", scripts
      codigos.html                        # reescrito: inclui os 2 fragmentos
      codigos_beneficio_fragment.html     # NOVO
      codigos_depart_fragment.html        # NOVO
      ocorrencias.html                    # − dias_mes/colunas_qt; + data-tour
      vt_caixa.html                       # + data-tour
      historico.html                      # + data-tour
  core/
    vt_caixa_processador.py               # + codigos_extras/depart_extras
    processador.py                        # − dias_mes/colunas_qt/Vu VT
  tests/
    test_ref_codes.py                     # NOVO
    test_routes_codigos.py                # NOVO
    (ajustes em test_worker_tasks.py, test_routes_jobs.py,
     tests/core/test_processador.py, tests/core/test_vt_caixa.py,
     test_routes_app.py)
```

---

### Task 1: Tabelas + módulo `ref_codes.py`

**Files:**
- Modify: `license-server/app/db.py` (acrescentar ao final da string `SCHEMA`)
- Create: `license-server/app/ref_codes.py`
- Test: `license-server/tests/test_ref_codes.py`

**Interfaces:**
- Consumes: `app.db.get_connection(db_path)`.
- Produces (usado nas Tasks 3 e 4):
  - `ref_codes.list_benefit_codes(db_path) -> list[dict]` (dicts com id, operadora, valor_unitario, codigo, created_by, created_at; ordenado por operadora)
  - `ref_codes.list_depart_subs(db_path) -> list[dict]` (id, original, substituto, ...; ordenado por original)
  - `ref_codes.add_benefit_code(db_path, user_id: int, operadora: str, valor_unitario: str, codigo: str) -> int` — ValueError em campo vazio ou duplicata
  - `ref_codes.add_depart_sub(db_path, user_id: int, original: str, substituto: str) -> int` — ValueError em campo vazio ou duplicata
  - `ref_codes.delete_benefit_code(db_path, code_id: int) -> None`
  - `ref_codes.delete_depart_sub(db_path, sub_id: int) -> None`
  - `ref_codes.benefit_tuples(db_path) -> list[tuple]` — `[(operadora, valor_unitario|None, codigo), ...]`
  - `ref_codes.depart_dict(db_path) -> dict` — `{original: substituto}`

- [ ] **Step 1: Escrever os testes**

Criar `license-server/tests/test_ref_codes.py`:

```python
import pytest

from app import ref_codes
from app.db import init_db


@pytest.fixture
def db(tmp_path):
    p = str(tmp_path / "t.db")
    init_db(p)
    return p


def test_add_e_list_beneficio(db):
    rid = ref_codes.add_benefit_code(db, 1, "nova linha", "11,50", "12345")
    lst = ref_codes.list_benefit_codes(db)
    assert len(lst) == 1
    assert lst[0]["id"] == rid
    assert lst[0]["operadora"] == "NOVA LINHA"   # normalizado p/ uppercase
    assert lst[0]["valor_unitario"] == "11,50"
    assert lst[0]["codigo"] == "12345"


def test_valor_vazio_vira_none(db):
    ref_codes.add_benefit_code(db, 1, "OPX", "", "111")
    assert ref_codes.list_benefit_codes(db)[0]["valor_unitario"] is None
    assert ref_codes.benefit_tuples(db) == [("OPX", None, "111")]


def test_beneficio_campos_obrigatorios(db):
    with pytest.raises(ValueError):
        ref_codes.add_benefit_code(db, 1, "", "1", "111")
    with pytest.raises(ValueError):
        ref_codes.add_benefit_code(db, 1, "OP", "1", "")


def test_beneficio_duplicata(db):
    ref_codes.add_benefit_code(db, 1, "OPX", "11,50", "111")
    with pytest.raises(ValueError):
        ref_codes.add_benefit_code(db, 2, "opx", "11,50", "222")
    # mesmo nome com valor diferente é permitido (como SPTRANS embutido)
    ref_codes.add_benefit_code(db, 1, "OPX", "22,00", "222")


def test_delete_beneficio(db):
    rid = ref_codes.add_benefit_code(db, 1, "OPX", "", "111")
    ref_codes.delete_benefit_code(db, rid)
    assert ref_codes.list_benefit_codes(db) == []


def test_add_list_delete_depart(db):
    rid = ref_codes.add_depart_sub(db, 1, "DEPTO ORIGINAL", "SUBSTITUTO")
    assert ref_codes.depart_dict(db) == {"DEPTO ORIGINAL": "SUBSTITUTO"}
    with pytest.raises(ValueError):
        ref_codes.add_depart_sub(db, 2, "DEPTO ORIGINAL", "OUTRO")
    with pytest.raises(ValueError):
        ref_codes.add_depart_sub(db, 1, "", "X")
    ref_codes.delete_depart_sub(db, rid)
    assert ref_codes.list_depart_subs(db) == []
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_ref_codes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ref_codes'`

- [ ] **Step 3: Implementar**

Em `license-server/app/db.py`, acrescentar ao final da string `SCHEMA` (antes das aspas de fechamento):

```sql
CREATE TABLE IF NOT EXISTS custom_benefit_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operadora TEXT NOT NULL,
    valor_unitario TEXT,
    codigo TEXT NOT NULL,
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS custom_depart_subs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original TEXT NOT NULL,
    substituto TEXT NOT NULL,
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
);
```

Criar `license-server/app/ref_codes.py`:

```python
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
```

Nota: `valor_unitario IS ?` é a comparação NULL-safe do SQLite (`IS` funciona com parâmetro).

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_ref_codes.py -v`
Expected: PASS (6 testes)

- [ ] **Step 5: Commit**

```bash
git add license-server/app/db.py license-server/app/ref_codes.py license-server/tests/test_ref_codes.py
git commit -m "feat(web): tabelas e CRUD de codigos/departamentos personalizados"
```

---

### Task 2: Core aceita `codigos_extras`/`depart_extras` com precedência

**Files:**
- Modify: `license-server/core/vt_caixa_processador.py`
- Test: `license-server/tests/core/test_vt_caixa.py` (acrescentar)

**Interfaces:**
- Produces (usado na Task 3):
  - `ProcessadorVTCaixa.processar(fonte_path, xls_path, output_path, progress_cb=None, codigos_extras=None, depart_extras=None)`
  - `codigos_extras`: `list[tuple]` no formato `(operadora_uppercase, valor|None, codigo)` — consultado ANTES de `_CODIGOS_BENEFICIO`
  - `depart_extras`: `dict {original: substituto}` — sobrepõe `_DEPART_MAP`
  - `_resolver_codigo_beneficio(self, administradora, valor_unitario, extras=None)`

- [ ] **Step 1: Escrever os testes** (acrescentar em `license-server/tests/core/test_vt_caixa.py`)

```python
def test_resolver_codigo_extras_tem_precedencia():
    p = ProcessadorVTCaixa()
    # embutido: ('SPTRANS', '11,64', '701')
    extras = [('SPTRANS', '11,64', '999')]
    assert p._resolver_codigo_beneficio('SPTRANS SP', '11,64', extras) == '999'
    # sem extras, embutido continua valendo
    assert p._resolver_codigo_beneficio('SPTRANS SP', '11,64') == '701'
    # operadora só nos extras
    extras2 = [('OPERADORA NOVA', None, '555')]
    assert p._resolver_codigo_beneficio('OPERADORA NOVA LTDA', '10,00', extras2) == '555'
    assert p._resolver_codigo_beneficio('OPERADORA NOVA LTDA', '10,00') is None


def test_cruzar_dados_usa_depart_extras():
    p = ProcessadorVTCaixa()
    pdf_rows = [{'codigo': '111', 'colaborador': 'ANA',
                 'administradora': 'QUALQUER', 'valor_unitario': '5,00',
                 'quantidade': '20'}]
    excel_data = {'111': {
        'CPF': '1', 'RG': '2', 'Data nascimento': '', 'Descrição cargo': '',
        'Descrição Ccusto': 'MEU DEPTO', 'Descrição Dpto': '', 'Nome Mae': '',
        'Endereço': '', 'Numero': '', 'Complemento': '', 'Cep': '',
        'Estado Civil': '', 'Data EX': '', 'Orgão RG': '', 'UF RG': '',
    }}
    regs, _ = p._cruzar_dados(pdf_rows, excel_data,
                              depart_extras={'MEU DEPTO': 'DEPTO NOVO'})
    assert regs[0]['DEPARTAMENTO'] == 'DEPTO NOVO'
    # depart_extras sobrepõe _DEPART_MAP quando a chave coincide
    regs2, _ = p._cruzar_dados(pdf_rows, excel_data)
    assert regs2[0]['DEPARTAMENTO'] == 'MEU DEPTO'
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/core/test_vt_caixa.py -v`
Expected: FAIL — `TypeError` (parâmetros inexistentes)

- [ ] **Step 3: Implementar**

Em `license-server/core/vt_caixa_processador.py`:

(a) `_resolver_codigo_beneficio` (linha ~869) passa a:

```python
    def _resolver_codigo_beneficio(self, administradora, valor_unitario, extras=None):
        """Retorna o código de benefício quando a operadora+valor bate uma regra, ou None.

        `extras` (regras personalizadas, mesmo formato de _CODIGOS_BENEFICIO)
        é consultado antes das regras embutidas.
        """
        adm_up = administradora.upper()
        for operadora, valor_regra, codigo in list(extras or []) + self._CODIGOS_BENEFICIO:
            if operadora not in adm_up:
                continue
            if valor_regra is None or valor_unitario == valor_regra:
                return codigo
        return None
```

(b) `_cruzar_dados` ganha os parâmetros e usa-os nos dois blocos:

```python
    def _cruzar_dados(self, pdf_rows, excel_data, codigos_extras=None, depart_extras=None):
```

No bloco de substituição de departamento (linha ~940), trocar:

```python
        # Substituições de departamento (personalizadas sobrepõem o mapa embutido)
        depart_map = {**self._DEPART_MAP, **(depart_extras or {})}
        for reg in registros:
            depart = reg.get('DEPARTAMENTO', '')
            if depart in depart_map:
                reg['DEPARTAMENTO'] = depart_map[depart]
```

No bloco de resolução de código (linha ~947), trocar a chamada:

```python
            codigo = self._resolver_codigo_beneficio(
                reg[chave_benef],
                reg.get('VALOR UNITÁRIO', ''),
                codigos_extras,
            )
```

(c) `processar` ganha os parâmetros e repassa (assinatura na linha ~1096 e chamada de `_cruzar_dados` logo abaixo de `_prog(65, 'Cruzando dados...')`):

```python
    def processar(self, fonte_path, xls_path, output_path,
                  progress_cb=None, codigos_extras=None, depart_extras=None):
```

```python
        registros, nao_encontrados = self._cruzar_dados(
            pdf_rows, excel_data, codigos_extras, depart_extras)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/core/test_vt_caixa.py -v`
Expected: PASS

- [ ] **Step 5: Rodar a suíte inteira** (garante que nada quebrou)

Run: `python -m pytest tests -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add license-server/core/vt_caixa_processador.py license-server/tests/core/test_vt_caixa.py
git commit -m "feat(web): core vt-caixa aceita codigos/departamentos extras com precedencia"
```

---

### Task 3: Worker injeta os personalizados no job VT-Caixa

**Files:**
- Modify: `license-server/app/worker_tasks.py` (função `run_vt_caixa`)
- Test: `license-server/tests/test_worker_tasks.py` (acrescentar)

**Interfaces:**
- Consumes: `ref_codes.benefit_tuples(db_path)`, `ref_codes.depart_dict(db_path)` (Task 1); `processar(..., codigos_extras=, depart_extras=)` (Task 2).
- Produces: nenhum contrato novo — `run_vt_caixa(db_path, data_dir, job_id)` inalterado por fora.

- [ ] **Step 1: Escrever o teste** (acrescentar em `license-server/tests/test_worker_tasks.py`)

```python
def test_vt_caixa_injeta_personalizados(env, monkeypatch):
    db, data_dir = env
    from app import ref_codes
    ref_codes.add_benefit_code(db, 1, "OP CUSTOM", "", "777")
    ref_codes.add_depart_sub(db, 1, "DEP A", "DEP B")

    capturado = {}

    def fake_processar(self, fonte_path, xls_path, output_path, progress_cb=None,
                       codigos_extras=None, depart_extras=None):
        from pathlib import Path
        capturado["codigos"] = codigos_extras
        capturado["depart"] = depart_extras
        Path(output_path).write_text("CNPJ\n", encoding="latin-1")
        return {"total_pdf": 1, "total_fonte": 1, "tipo_fonte": "PDF",
                "total_ok": 1, "nao_encontrados": [], "avisos_csv": []}

    monkeypatch.setattr("core.vt_caixa_processador.ProcessadorVTCaixa.processar",
                        fake_processar)
    jid = jobs.create_job(db, 1, "vt_caixa", {
        "fonte_name": "fonte.pdf", "cadastral_name": "cadastral.xlsx"})
    d = jobs.job_dir(data_dir, jid)
    (d / "in" / "fonte.pdf").write_bytes(b"%PDF")
    (d / "in" / "cadastral.xlsx").write_bytes(b"xx")
    worker_tasks.run_vt_caixa(db, data_dir, jid)

    assert jobs.get_job(db, jid)["status"] == "done"
    assert capturado["codigos"] == [("OP CUSTOM", None, "777")]
    assert capturado["depart"] == {"DEP A": "DEP B"}
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_worker_tasks.py -v`
Expected: FAIL — `capturado["codigos"]` é `None`

- [ ] **Step 3: Implementar**

Em `license-server/app/worker_tasks.py`, no `run_vt_caixa`, trocar a chamada de `processar` por:

```python
        from app import ref_codes
        result = p.processar(
            fonte_path=str(d / "in" / params["fonte_name"]),
            xls_path=str(d / "in" / params["cadastral_name"]),
            output_path=str(d / "out" / "beneficios.csv"),
            progress_cb=_progress_cb(db_path, job_id),
            codigos_extras=ref_codes.benefit_tuples(db_path),
            depart_extras=ref_codes.depart_dict(db_path),
        )
```

(Manter o import local dentro da função ou mover para o topo do módulo — topo é preferível: `from app import history, jobs, ref_codes`.)

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_worker_tasks.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add license-server/app/worker_tasks.py license-server/tests/test_worker_tasks.py
git commit -m "feat(web): worker vt-caixa usa codigos/departamentos personalizados"
```

---

### Task 4: Página Códigos com adicionar/excluir (HTMX)

**Files:**
- Create: `license-server/app/routes_codigos.py`
- Modify: `license-server/app/routes_app.py` (remover a rota `GET /app/codigos` e o import de `ProcessadorVTCaixa` dela)
- Modify: `license-server/app/main.py` (incluir router novo)
- Rewrite: `license-server/app/templates/codigos.html`
- Create: `license-server/app/templates/codigos_beneficio_fragment.html`
- Create: `license-server/app/templates/codigos_depart_fragment.html`
- Test: `license-server/tests/test_routes_codigos.py`

**Interfaces:**
- Consumes: `ref_codes.*` (Task 1), fixtures `client`/`logged_client`/`user_csrf` do conftest existente, constantes `ProcessadorVTCaixa._CODIGOS_BENEFICIO`/`_DEPART_MAP`.
- Produces rotas (todas exigem login; POSTs exigem CSRF):
  - `GET  /app/codigos` — página completa
  - `POST /app/codigos/beneficio` (form: operadora, valor_unitario, codigo, csrf_token) → fragmento da seção benefícios
  - `POST /app/codigos/beneficio/{code_id}/excluir` (form: csrf_token) → fragmento
  - `POST /app/codigos/departamento` (form: original, substituto, csrf_token) → fragmento da seção departamentos
  - `POST /app/codigos/departamento/{sub_id}/excluir` (form: csrf_token) → fragmento

- [ ] **Step 1: Escrever os testes**

Criar `license-server/tests/test_routes_codigos.py`:

```python
import re


def test_pagina_exige_login(client):
    c, _ = client
    r = c.get("/app/codigos", follow_redirects=False)
    assert r.status_code == 303


def test_pagina_mostra_embutidos_e_personalizados(logged_client):
    c, db = logged_client
    from app import ref_codes
    ref_codes.add_benefit_code(db, 1, "MINHA OPERADORA", "", "424242")
    r = c.get("/app/codigos")
    assert r.status_code == 200
    assert "SPTRANS" in r.text            # embutido
    assert "MINHA OPERADORA" in r.text    # personalizado
    assert "424242" in r.text


def test_adicionar_beneficio(logged_client, user_csrf):
    c, db = logged_client
    r = c.post("/app/codigos/beneficio", data={
        "operadora": "Nova Op", "valor_unitario": "", "codigo": "9999",
        "csrf_token": user_csrf,
    })
    assert r.status_code == 200
    assert "NOVA OP" in r.text
    from app import ref_codes
    assert ref_codes.benefit_tuples(db) == [("NOVA OP", None, "9999")]


def test_adicionar_beneficio_duplicado_mostra_erro(logged_client, user_csrf):
    c, db = logged_client
    from app import ref_codes
    ref_codes.add_benefit_code(db, 1, "OPX", "", "111")
    r = c.post("/app/codigos/beneficio", data={
        "operadora": "OPX", "valor_unitario": "", "codigo": "222",
        "csrf_token": user_csrf,
    })
    assert r.status_code == 400
    assert "Já existe" in r.text
    assert len(ref_codes.list_benefit_codes(db)) == 1


def test_excluir_beneficio(logged_client, user_csrf):
    c, db = logged_client
    from app import ref_codes
    rid = ref_codes.add_benefit_code(db, 1, "OPX", "", "111")
    r = c.post(f"/app/codigos/beneficio/{rid}/excluir",
               data={"csrf_token": user_csrf})
    assert r.status_code == 200
    assert ref_codes.list_benefit_codes(db) == []


def test_adicionar_e_excluir_departamento(logged_client, user_csrf):
    c, db = logged_client
    r = c.post("/app/codigos/departamento", data={
        "original": "DEP X", "substituto": "DEP Y", "csrf_token": user_csrf,
    })
    assert r.status_code == 200
    assert "DEP Y" in r.text
    from app import ref_codes
    subs = ref_codes.list_depart_subs(db)
    assert len(subs) == 1
    r = c.post(f"/app/codigos/departamento/{subs[0]['id']}/excluir",
               data={"csrf_token": user_csrf})
    assert r.status_code == 200
    assert ref_codes.list_depart_subs(db) == []


def test_post_sem_login(client):
    c, _ = client
    r = c.post("/app/codigos/beneficio", data={"operadora": "X", "codigo": "1"},
               follow_redirects=False)
    assert r.status_code == 303
```

Nota: as fixtures `client`/`logged_client` retornam tupla `(TestClient, db_path)` — seguir o padrão do conftest existente.

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_routes_codigos.py -v`
Expected: FAIL — 404/405 nas rotas novas

- [ ] **Step 3: Implementar as rotas**

Criar `license-server/app/routes_codigos.py`:

```python
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import ref_codes
from app.security import (
    current_user_id, get_or_create_csrf_token, require_user, verify_csrf_token,
)
from core.vt_caixa_processador import ProcessadorVTCaixa

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _ctx_beneficio(request: Request, db_path: str, error: str | None = None) -> dict:
    builtin = [{"operadora": op, "valor_unitario": valor, "codigo": cod, "id": None}
               for op, valor, cod in ProcessadorVTCaixa._CODIGOS_BENEFICIO]
    return {
        "beneficio_rows": builtin + ref_codes.list_benefit_codes(db_path),
        "csrf_token": get_or_create_csrf_token(request),
        "beneficio_error": error,
    }


def _ctx_depart(request: Request, db_path: str, error: str | None = None) -> dict:
    builtin = [{"original": o, "substituto": s, "id": None}
               for o, s in ProcessadorVTCaixa._DEPART_MAP.items()]
    return {
        "depart_rows": builtin + ref_codes.list_depart_subs(db_path),
        "csrf_token": get_or_create_csrf_token(request),
        "depart_error": error,
    }


@router.get("/app/codigos", response_class=HTMLResponse)
def codigos_page(request: Request, _=Depends(require_user)):
    db = request.app.state.settings.db_path
    ctx = {**_ctx_beneficio(request, db), **_ctx_depart(request, db),
           "active": "codigos"}
    return templates.TemplateResponse(request, "codigos.html", ctx)


@router.post("/app/codigos/beneficio", response_class=HTMLResponse)
def beneficio_add(request: Request, operadora: str = Form(""),
                  valor_unitario: str = Form(""), codigo: str = Form(""),
                  csrf_token: str = Form(""), _=Depends(require_user)):
    db = request.app.state.settings.db_path
    error, status_code = None, 200
    if not verify_csrf_token(request.session.get("csrf_token"), csrf_token):
        error, status_code = "Sessão expirada — recarregue a página.", 400
    else:
        try:
            ref_codes.add_benefit_code(db, current_user_id(request),
                                       operadora, valor_unitario, codigo)
        except ValueError as e:
            error, status_code = str(e), 400
    return templates.TemplateResponse(
        request, "codigos_beneficio_fragment.html",
        _ctx_beneficio(request, db, error), status_code=status_code)


@router.post("/app/codigos/beneficio/{code_id}/excluir", response_class=HTMLResponse)
def beneficio_delete(request: Request, code_id: int,
                     csrf_token: str = Form(""), _=Depends(require_user)):
    db = request.app.state.settings.db_path
    if verify_csrf_token(request.session.get("csrf_token"), csrf_token):
        ref_codes.delete_benefit_code(db, code_id)
    return templates.TemplateResponse(
        request, "codigos_beneficio_fragment.html", _ctx_beneficio(request, db))


@router.post("/app/codigos/departamento", response_class=HTMLResponse)
def depart_add(request: Request, original: str = Form(""),
               substituto: str = Form(""), csrf_token: str = Form(""),
               _=Depends(require_user)):
    db = request.app.state.settings.db_path
    error, status_code = None, 200
    if not verify_csrf_token(request.session.get("csrf_token"), csrf_token):
        error, status_code = "Sessão expirada — recarregue a página.", 400
    else:
        try:
            ref_codes.add_depart_sub(db, current_user_id(request),
                                     original, substituto)
        except ValueError as e:
            error, status_code = str(e), 400
    return templates.TemplateResponse(
        request, "codigos_depart_fragment.html",
        _ctx_depart(request, db, error), status_code=status_code)


@router.post("/app/codigos/departamento/{sub_id}/excluir", response_class=HTMLResponse)
def depart_delete(request: Request, sub_id: int,
                  csrf_token: str = Form(""), _=Depends(require_user)):
    db = request.app.state.settings.db_path
    if verify_csrf_token(request.session.get("csrf_token"), csrf_token):
        ref_codes.delete_depart_sub(db, sub_id)
    return templates.TemplateResponse(
        request, "codigos_depart_fragment.html", _ctx_depart(request, db))
```

Em `license-server/app/routes_app.py`: **remover** a função `codigos` inteira (rota `GET /app/codigos`).

Em `license-server/app/main.py`: adicionar `from app.routes_codigos import router as codigos_router` junto aos outros imports e `fastapi_app.include_router(codigos_router)` junto aos outros includes.

- [ ] **Step 4: Criar os templates**

`license-server/app/templates/codigos_beneficio_fragment.html`:

```html
<div id="sec-beneficio" class="card" data-tour="cod-beneficio">
    <div style="padding:16px 18px;border-bottom:1px solid var(--border);font-weight:600;color:var(--text-bright)">
        Operadora → Código de Benefício
    </div>
    <form hx-post="/app/codigos/beneficio" hx-target="#sec-beneficio" hx-swap="outerHTML"
          style="display:flex;gap:8px;padding:12px 16px;border-bottom:1px solid var(--border);align-items:flex-end"
          data-tour="cod-add-beneficio">
        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
        <div style="flex:2"><label>Operadora</label>
            <input type="text" name="operadora" placeholder="NOME DA OPERADORA" required></div>
        <div style="flex:1"><label>Valor (opcional)</label>
            <input type="text" name="valor_unitario" placeholder="11,64"></div>
        <div style="flex:1"><label>Código</label>
            <input type="text" name="codigo" placeholder="12345" required></div>
        <button type="submit" class="btn btn-primary btn-sm" style="height:36px">Adicionar</button>
    </form>
    {% if beneficio_error %}
    <div class="alert alert-error" style="margin:12px 16px 0">{{ beneficio_error }}</div>
    {% endif %}
    <table>
        <thead>
            <tr><th>Operadora</th><th>Valor Unitário</th><th>Código</th><th></th></tr>
        </thead>
        <tbody>
            {% for r in beneficio_rows %}
            <tr>
                <td onclick="navigator.clipboard.writeText('{{ r.codigo }}')" style="cursor:pointer">{{ r.operadora }}</td>
                <td class="meta">{{ r.valor_unitario or "qualquer" }}</td>
                <td class="key">{{ r.codigo }}</td>
                <td style="text-align:right">
                    {% if r.id %}
                    <span class="meta" style="margin-right:8px">personalizado</span>
                    <form hx-post="/app/codigos/beneficio/{{ r.id }}/excluir"
                          hx-target="#sec-beneficio" hx-swap="outerHTML"
                          hx-confirm="Excluir o código de {{ r.operadora }}?" style="display:inline">
                        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                        <button type="submit" class="btn btn-danger btn-sm">Excluir</button>
                    </form>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
```

`license-server/app/templates/codigos_depart_fragment.html`:

```html
<div id="sec-depart" class="card" data-tour="cod-depart">
    <div style="padding:16px 18px;border-bottom:1px solid var(--border);font-weight:600;color:var(--text-bright)">
        Departamento → Substituição
    </div>
    <form hx-post="/app/codigos/departamento" hx-target="#sec-depart" hx-swap="outerHTML"
          style="display:flex;gap:8px;padding:12px 16px;border-bottom:1px solid var(--border);align-items:flex-end">
        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
        <div style="flex:1"><label>Original</label>
            <input type="text" name="original" placeholder="Departamento original" required></div>
        <div style="flex:1"><label>Substituto</label>
            <input type="text" name="substituto" placeholder="Substituto" required></div>
        <button type="submit" class="btn btn-primary btn-sm" style="height:36px">Adicionar</button>
    </form>
    {% if depart_error %}
    <div class="alert alert-error" style="margin:12px 16px 0">{{ depart_error }}</div>
    {% endif %}
    <table>
        <thead>
            <tr><th>Original</th><th>Substituto</th><th></th></tr>
        </thead>
        <tbody>
            {% for r in depart_rows %}
            <tr>
                <td>{{ r.original }}</td>
                <td class="key">{{ r.substituto }}</td>
                <td style="text-align:right">
                    {% if r.id %}
                    <span class="meta" style="margin-right:8px">personalizado</span>
                    <form hx-post="/app/codigos/departamento/{{ r.id }}/excluir"
                          hx-target="#sec-depart" hx-swap="outerHTML"
                          hx-confirm="Excluir a substituição de {{ r.original }}?" style="display:inline">
                        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                        <button type="submit" class="btn btn-danger btn-sm">Excluir</button>
                    </form>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
```

Reescrever `license-server/app/templates/codigos.html` como:

```html
{% extends "app_base.html" %}
{% block title %}Códigos — Processador de Ocorrências{% endblock %}
{% block content %}
<div class="page-header">
    <h1>Códigos de referência</h1>
    <p>Clique em uma linha para copiar o código. Entradas personalizadas valem
       também no processamento do VT-Caixa e têm precedência sobre as embutidas.</p>
</div>
<div class="code-grid">
    {% include "codigos_beneficio_fragment.html" %}
    {% include "codigos_depart_fragment.html" %}
</div>
{% endblock %}
```

Nota: os fragmentos retornados pelos POSTs re-renderizam a seção inteira
(`hx-swap="outerHTML"` no `div` raiz com o mesmo id), então erro e lista
sempre chegam juntos.

- [ ] **Step 5: Rodar e ver passar**

Run: `python -m pytest tests/test_routes_codigos.py tests/test_routes_app.py -v`
Expected: PASS (se algum teste antigo de `/app/codigos` em `test_routes_app.py` verificava conteúdo, ajustar para o novo HTML)

- [ ] **Step 6: Rodar a suíte inteira**

Run: `python -m pytest tests -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add license-server/app license-server/tests
git commit -m "feat(web): pagina codigos com criar/excluir personalizados via htmx"
```

---

### Task 5: Remover "Dias no mês" e "Colunas Qt" de ponta a ponta

**Files:**
- Modify: `license-server/app/templates/ocorrencias.html` (linhas 29–40)
- Modify: `license-server/app/routes_jobs.py` (linhas 48–49, 64–65)
- Modify: `license-server/app/worker_tasks.py` (linhas 103–104)
- Modify: `license-server/core/processador.py` (linhas 23–25, 229, 281–283, 300–345 — ver Step 3)
- Modify: `license-server/tests/test_worker_tasks.py` (linha 32)
- Modify: `license-server/tests/core/test_processador.py` (se referenciar dias_mes/colunas_qt)

**Interfaces:**
- Produces (contratos finais):
  - `ProcessadorOcorrencias.processar(pdf_path, xlsx_path, output_path, codigos, progress_cb=None, dados_externos=None)`
  - Params do job `ocorrencias`: `{"codigos", "pdf_name", "xlsx_name", "orig_pdf", "orig_xlsx"}` (sem `dias_mes`/`colunas_qt_sel`)
  - `POST /app/ocorrencias` não aceita mais `dias_mes`/`colunas_qt`

- [ ] **Step 1: Ajustar os testes primeiro**

Em `license-server/tests/test_worker_tasks.py`, remover `"dias_mes": None, "colunas_qt_sel": None,` do dict `p` em `_setup_job` (linha 32). Acrescentar teste de assinatura:

```python
def test_processar_sem_dias_mes():
    import inspect
    from core.processador import ProcessadorOcorrencias
    sig = inspect.signature(ProcessadorOcorrencias.processar)
    assert "dias_mes" not in sig.parameters
    assert "colunas_qt_sel" not in sig.parameters
```

Em `license-server/tests/core/test_processador.py`, remover/ajustar qualquer teste que use `dias_mes`/`colunas_qt_sel`/`COLUNAS_QT` (verificar com grep antes: `grep -n "dias_mes\|colunas_qt\|COLUNAS_QT\|VU_VT" tests/core/test_processador.py`).

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_worker_tasks.py::test_processar_sem_dias_mes -v`
Expected: FAIL — parâmetro ainda existe

- [ ] **Step 3: Remover no core**

Em `license-server/core/processador.py`:

1. Deletar as constantes (linhas 23–25):
   `CODIGOS_DEDUZIR`, `COLUNAS_QT`, `VU_VT_HEADER`.
2. Assinatura de `processar` vira:

```python
    def processar(self, pdf_path, xlsx_path, output_path, codigos,
                  progress_cb=None, dados_externos=None):
```

3. No passo "3. Encontrar colunas": deletar as variáveis `qt_cols = {}` e
   `vu_vt_col = None` e os dois `if` que as preenchem
   (`if val_lower in self.COLUNAS_QT:` e `if val_lower == self.VU_VT_HEADER:`).
4. No passo "4. Cruzar dados": deletar o bloco `qt_cols_ativas = {...}`,
   o bloco `if dias_mes is not None and qt_cols_ativas:` (preenchimento) e o
   bloco de dedução `if dias_mes is not None and qt_cols_ativas:` com
   `dias_ded = sum(...)`. O laço fica apenas com: montar `excel_res`,
   casar RE → escrever MOTIVO → montar `atualizados`, e o progresso.
5. Atualizar a docstring de `processar` (remover menção a dias/Qt).

- [ ] **Step 4: Remover no worker, rota e template**

`license-server/app/worker_tasks.py`, `_processar_final`: deletar as linhas
`dias_mes=params.get("dias_mes"),` e `colunas_qt_sel=params.get("colunas_qt_sel"),`.

`license-server/app/routes_jobs.py`, `ocorrencias_submit`: deletar os parâmetros
`dias_mes: Optional[int] = Form(None),` e `colunas_qt: Optional[list[str]] = Form(None),`
e no dict `params` deletar `"dias_mes": dias_mes,` e `"colunas_qt_sel": colunas_qt,`
(mantendo `codigos`, `pdf_name`, `xlsx_name`, `orig_pdf`, `orig_xlsx`).
Se `Optional` ficar sem uso no arquivo, remover o import.

`license-server/app/templates/ocorrencias.html`: deletar as linhas 29–40
(label+input de `dias_mes` e label+div de `colunas_qt`).

- [ ] **Step 5: Rodar a suíte inteira**

Run: `python -m pytest tests -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add license-server/app license-server/core license-server/tests
git commit -m "feat(web): remove dias no mes e colunas qt do fluxo de ocorrencias"
```

---

### Task 6: Coluna `tutorial_seen` + endpoint de marcação

**Files:**
- Modify: `license-server/app/db.py` (migração da coluna)
- Modify: `license-server/app/users.py`
- Modify: `license-server/app/routes_app.py`
- Test: `license-server/tests/test_users.py` e `license-server/tests/test_routes_app.py` (acrescentar)

**Interfaces:**
- Produces (usado na Task 7):
  - `users` tem coluna `tutorial_seen INTEGER NOT NULL DEFAULT 0`
  - `users.get_user(db_path, user_id)` retorna dict incluindo `tutorial_seen`
  - `users.mark_tutorial_seen(db_path, user_id) -> None`
  - `POST /app/tutorial/seen` (form: csrf_token) → 204; marca o usuário logado; idempotente

- [ ] **Step 1: Escrever os testes**

Acrescentar em `license-server/tests/test_users.py`:

```python
def test_tutorial_seen(db_path):
    uid = users.create_user(db_path, "ana@ex.com", "Ana", "s3nh4forte")
    assert users.get_user(db_path, uid)["tutorial_seen"] == 0
    users.mark_tutorial_seen(db_path, uid)
    assert users.get_user(db_path, uid)["tutorial_seen"] == 1
    users.mark_tutorial_seen(db_path, uid)  # idempotente
    assert users.get_user(db_path, uid)["tutorial_seen"] == 1
```

Acrescentar em `license-server/tests/test_routes_app.py`:

```python
def test_tutorial_seen_endpoint(logged_client, user_csrf):
    c, db = logged_client
    r = c.post("/app/tutorial/seen", data={"csrf_token": user_csrf})
    assert r.status_code == 204
    from app import users as users_module
    lst = users_module.list_users(db)
    assert lst[0]["tutorial_seen"] == 1


def test_tutorial_seen_exige_login(client):
    c, _ = client
    r = c.post("/app/tutorial/seen", follow_redirects=False)
    assert r.status_code == 303
```

(Se a fixture `logged_client` do conftest atual retornar algo diferente de `(client, db)`, adaptar a leitura do db ao padrão real.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_users.py tests/test_routes_app.py -v`
Expected: FAIL

- [ ] **Step 3: Implementar**

Em `license-server/app/db.py`, dentro de `init_db`, após o `executescript(SCHEMA)`:

```python
        # Migração: coluna nova em bancos criados antes dela (SQLite não tem
        # ADD COLUMN IF NOT EXISTS).
        try:
            conn.execute(
                "ALTER TABLE users ADD COLUMN tutorial_seen INTEGER NOT NULL DEFAULT 0"
            )
        except sqlite3.OperationalError:
            pass  # coluna já existe
```

(Adicionar `import sqlite3` no topo se não houver.) E na tabela `users` do
`SCHEMA`, acrescentar a coluna `tutorial_seen INTEGER NOT NULL DEFAULT 0`
(bancos novos já nascem com ela; o ALTER cobre os antigos).

Em `license-server/app/users.py`, acrescentar:

```python
def mark_tutorial_seen(db_path: str, user_id: int) -> None:
    with get_connection(db_path) as conn:
        conn.execute("UPDATE users SET tutorial_seen = 1 WHERE id = ?", (user_id,))
```

Em `license-server/app/routes_app.py`, acrescentar (imports: `Form`, `Response` de fastapi/fastapi.responses; `verify_csrf_token` de app.security; `users` de app):

```python
from fastapi import Form
from fastapi.responses import Response

from app import users as users_module
from app.security import verify_csrf_token


@router.post("/app/tutorial/seen")
def tutorial_seen(request: Request, csrf_token: str = Form(""),
                  _=Depends(require_user)):
    if verify_csrf_token(request.session.get("csrf_token"), csrf_token):
        settings = request.app.state.settings
        users_module.mark_tutorial_seen(settings.db_path, current_user_id(request))
    return Response(status_code=204)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_users.py tests/test_routes_app.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add license-server/app license-server/tests
git commit -m "feat(web): coluna tutorial_seen e endpoint de marcacao"
```

---

### Task 7: Tour interativo (driver.js vendorizado + tour.js + data-tour)

**Files:**
- Create: `license-server/app/static/driver.js.iife.js` (download)
- Create: `license-server/app/static/driver.css` (download)
- Create: `license-server/app/static/tour.js`
- Modify: `license-server/app/templates/app_base.html`
- Modify: `license-server/app/templates/ocorrencias.html`, `vt_caixa.html`, `historico.html` (atributos `data-tour`; `codigos_*_fragment.html` já os têm da Task 4)
- Modify: `license-server/app/routes_app.py` e `license-server/app/routes_codigos.py` (passar `tutorial_seen` ao contexto)
- Test: `license-server/tests/test_routes_app.py` (acrescentar)

**Interfaces:**
- Consumes: `users.get_user(...)["tutorial_seen"]` e `POST /app/tutorial/seen` (Task 6).
- Produces: função global JS `startTour(segIndex)` (usada pelo botão da sidebar); auto-start quando `window.TOUR.seen === false`; retomada por query `?tour=<segIndex>`.

- [ ] **Step 1: Vendorizar o driver.js**

De `license-server/`, rodar (Git Bash):

```bash
curl -L -o app/static/driver.js.iife.js https://unpkg.com/driver.js@1.3.1/dist/driver.js.iife.js
curl -L -o app/static/driver.css https://unpkg.com/driver.js@1.3.1/dist/driver.css
```

Verificar: `head -c 200 app/static/driver.js.iife.js` deve mostrar JS minificado
(não HTML de erro), e o arquivo deve ter > 20 KB.

- [ ] **Step 2: Escrever os testes** (acrescentar em `license-server/tests/test_routes_app.py`)

```python
def test_base_inclui_tour(logged_client):
    c, _ = logged_client
    r = c.get("/app/ocorrencias")
    assert 'src="/static/tour.js"' in r.text
    assert 'src="/static/driver.js.iife.js"' in r.text
    assert "window.TOUR" in r.text
    assert '"seen": false' in r.text.replace("'", '"') or "seen: false" in r.text
    assert 'data-tour="nav-ocorrencias"' in r.text
    assert 'data-tour="btn-tutorial"' in r.text


def test_tour_seen_true_apos_marcar(logged_client, user_csrf):
    c, _ = logged_client
    c.post("/app/tutorial/seen", data={"csrf_token": user_csrf})
    r = c.get("/app/ocorrencias")
    assert "seen: true" in r.text
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `python -m pytest tests/test_routes_app.py -v`
Expected: FAIL

- [ ] **Step 4: Contexto `tutorial_seen` nas páginas**

Em `license-server/app/routes_app.py` e `license-server/app/routes_codigos.py`,
todas as rotas GET de página (`/app/ocorrencias`, `/app/vt-caixa`,
`/app/codigos`, `/app/historico`) passam a incluir no contexto:

```python
        "tutorial_seen": bool(users_module.get_user(
            request.app.state.settings.db_path, current_user_id(request)
        )["tutorial_seen"]),
        "csrf_token": get_or_create_csrf_token(request),
```

(As rotas que ainda não passavam `csrf_token` — historico — passam a passar,
pois o tour usa o token para o POST de `seen`. Import de `users as users_module`
e `current_user_id` onde faltar.)

- [ ] **Step 5: Editar `app_base.html`**

No `<head>`, após o htmx:

```html
<link rel="stylesheet" href="/static/driver.css">
<script src="/static/driver.js.iife.js"></script>
```

Nos links do nav, acrescentar atributos:
- link Ocorrências: `data-tour="nav-ocorrencias"`
- link VT-Caixa: `data-tour="nav-vtcaixa"`
- link Códigos: `data-tour="nav-codigos"`
- link Histórico: `data-tour="nav-historico"`

Logo após o `</nav>` (antes de `.user-info`), o botão de repetir:

```html
    <nav style="margin-top:6px">
      <a href="#" data-tour="btn-tutorial" onclick="startTour(0);return false">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
        Ver tutorial
      </a>
    </nav>
```

Antes de `</body>`:

```html
<script>
window.TOUR = {
  seen: {{ 'true' if tutorial_seen else 'false' }},
  csrf: "{{ csrf_token }}",
};
</script>
<script src="/static/tour.js"></script>
```

Nota: páginas fora da área logada (login) não estendem `app_base.html`, então
não são afetadas. `tutorial_seen`/`csrf_token` sempre presentes no contexto
das páginas do app (Step 4); usar `{{ 'true' if tutorial_seen else 'false' }}`
falha alto no teste se alguma rota esquecer a variável — proposital.

- [ ] **Step 6: `data-tour` nas páginas**

`ocorrencias.html`: no input do PDF `data-tour="oc-pdf"`, no input da planilha
`data-tour="oc-xlsx"`, no div-grid dos códigos `data-tour="oc-codigos"`, no
botão Processar `data-tour="oc-processar"`.

`vt_caixa.html`: input fonte `data-tour="vt-fonte"`, input cadastral
`data-tour="vt-cadastral"`, botão Processar `data-tour="vt-processar"`.

`historico.html`: no form da toolbar `data-tour="hist-filtros"`, no link
Exportar CSV `data-tour="hist-export"`.

(`codigos_beneficio_fragment.html` já tem `cod-beneficio`/`cod-add-beneficio`
e `codigos_depart_fragment.html` tem `cod-depart` — Task 4.)

- [ ] **Step 7: Criar `license-server/app/static/tour.js`**

```javascript
/* Tour guiado — segmentos por página, ancorados em [data-tour].
   Auto-inicia no primeiro acesso (window.TOUR.seen === false); o botão
   "Ver tutorial" chama startTour(0). Entre páginas, a continuação vai na
   query ?tour=<indice do segmento>. */
(function () {
  const driver = window.driver.js.driver;

  const SEGMENTS = [
    {
      page: "/app/ocorrencias",
      steps: [
        { popover: { title: "Bem-vindo!", description:
            "Este tour rápido mostra tudo que o sistema faz. Você pode revê-lo " +
            "a qualquer momento no botão “Ver tutorial” da barra lateral." } },
        { element: '[data-tour="nav-ocorrencias"]', popover: { title: "Ocorrências",
            description: "Cruza o PDF de jornada com a planilha de pedido e preenche a coluna MOTIVO." } },
        { element: '[data-tour="oc-pdf"]', popover: { title: "PDF de jornada",
            description: "Envie aqui o relatório PDF de jornada de trabalho." } },
        { element: '[data-tour="oc-xlsx"]', popover: { title: "Planilha de pedido",
            description: "Envie a planilha Excel que receberá os motivos." } },
        { element: '[data-tour="oc-codigos"]', popover: { title: "Códigos de ocorrência",
            description: "Marque quais códigos entram no processamento (FA, AT, FE...)." } },
        { element: '[data-tour="oc-processar"]', popover: { title: "Processar",
            description: "O arquivo entra na fila e a barra de progresso acompanha. Se as duas " +
            "varreduras do PDF divergirem, você revisa as diferenças antes de baixar o resultado." } },
      ],
    },
    {
      page: "/app/vt-caixa",
      steps: [
        { element: '[data-tour="nav-vtcaixa"]', popover: { title: "VT-Caixa",
            description: "Gera o CSV de benefícios a partir da fonte Nautilus e do cadastro." } },
        { element: '[data-tour="vt-fonte"]', popover: { title: "Fonte Nautilus",
            description: "PDF ou Excel do relatório Nautilus." } },
        { element: '[data-tour="vt-cadastral"]', popover: { title: "Cadastro funcional",
            description: "Excel cadastral com CPF, RG, endereço etc." } },
        { element: '[data-tour="vt-processar"]', popover: { title: "Processar",
            description: "Ao concluir, baixe o CSV pronto para o banco." } },
      ],
    },
    {
      page: "/app/codigos",
      steps: [
        { element: '[data-tour="nav-codigos"]', popover: { title: "Códigos",
            description: "Tabelas de referência usadas no VT-Caixa." } },
        { element: '[data-tour="cod-beneficio"]', popover: { title: "Operadora → Código",
            description: "Clique numa linha para copiar o código." } },
        { element: '[data-tour="cod-add-beneficio"]', popover: { title: "Adicionar código",
            description: "Cadastre operadoras novas aqui — elas passam a valer no processamento " +
            "do VT-Caixa para todos os usuários, com prioridade sobre as embutidas." } },
        { element: '[data-tour="cod-depart"]', popover: { title: "Departamentos",
            description: "Substituições de nome de departamento aplicadas no CSV. Também é " +
            "possível adicionar e excluir as personalizadas." } },
      ],
    },
    {
      page: "/app/historico",
      steps: [
        { element: '[data-tour="nav-historico"]', popover: { title: "Histórico",
            description: "Todos os seus processamentos ficam registrados aqui." } },
        { element: '[data-tour="hist-filtros"]', popover: { title: "Busca e filtro",
            description: "Procure por nome de arquivo ou filtre por sucesso/erro." } },
        { element: '[data-tour="hist-export"]', popover: { title: "Exportar",
            description: "Baixe o histórico filtrado em CSV." } },
        { element: '[data-tour="btn-tutorial"]', popover: { title: "Rever o tutorial",
            description: "Fim! Clique aqui sempre que quiser rever este tour." } },
      ],
    },
  ];

  function markSeen() {
    if (window.TOUR.seen) return;
    window.TOUR.seen = true;
    fetch("/app/tutorial/seen", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "csrf_token=" + encodeURIComponent(window.TOUR.csrf),
    });
  }

  function runSegment(idx) {
    const seg = SEGMENTS[idx];
    // pula passos cujo elemento não existe na página (layout pode mudar)
    const steps = seg.steps.filter(
      (s) => !s.element || document.querySelector(s.element)
    );
    if (!steps.length) { nextSegment(idx); return; }
    const d = driver({
      showProgress: true,
      nextBtnText: "Próximo",
      prevBtnText: "Anterior",
      doneBtnText: idx === SEGMENTS.length - 1 ? "Concluir" : "Continuar →",
      steps: steps,
      onDestroyed: () => {
        // driver destruído: ou terminou o segmento (avança) ou fechou no meio
        if (d.hasNextStep()) {
          markSeen();           // fechou no meio: marca e para
        } else {
          nextSegment(idx);     // terminou o segmento: próximo
        }
      },
    });
    d.drive();
  }

  function nextSegment(idx) {
    const next = idx + 1;
    if (next >= SEGMENTS.length) { markSeen(); return; }
    window.location.href = SEGMENTS[next].page + "?tour=" + next;
  }

  window.startTour = function (idx) {
    const seg = SEGMENTS[idx || 0];
    if (window.location.pathname !== seg.page) {
      window.location.href = seg.page + "?tour=" + (idx || 0);
      return;
    }
    runSegment(idx || 0);
  };

  document.addEventListener("DOMContentLoaded", () => {
    const params = new URLSearchParams(window.location.search);
    const tourParam = params.get("tour");
    if (tourParam !== null) {
      const idx = parseInt(tourParam, 10);
      if (idx >= 0 && idx < SEGMENTS.length) runSegment(idx);
    } else if (window.TOUR && window.TOUR.seen === false) {
      // primeiro acesso: começa do início (navega se não estiver na 1ª página)
      window.startTour(0);
    }
  });
})();
```

- [ ] **Step 8: Rodar os testes e a suíte**

Run: `python -m pytest tests/test_routes_app.py -v` → PASS
Run: `python -m pytest tests -q` → PASS

- [ ] **Step 9: Verificação manual no navegador** (obrigatória — o tour é JS e os testes não o exercitam)

De `license-server/` com `.env` local configurado e Redis dispensável para isto:

```bash
uvicorn app.main:app --reload
```

1. Criar usuário no `/admin/users`, logar em `/login`.
2. Confirmar que o tour inicia sozinho em Ocorrências e navega pelos 4 segmentos
   (Ocorrências → VT-Caixa → Códigos → Histórico), terminando no botão
   "Ver tutorial".
3. Recarregar a página: o tour NÃO deve auto-iniciar de novo.
4. Clicar em "Ver tutorial": tour reinicia do segmento 0.
5. Fechar o tour no meio (X): não reabre ao navegar.
6. Na página Códigos, adicionar e excluir um código personalizado e uma
   substituição de departamento; conferir a mensagem de duplicata.
7. Conferir que o form de Ocorrências não tem mais "Dias no mês"/"Colunas Qt".

- [ ] **Step 10: Commit**

```bash
git add license-server/app/static license-server/app/templates license-server/app/routes_app.py license-server/app/routes_codigos.py license-server/tests
git commit -m "feat(web): tutorial interativo com driver.js e botao de repeticao"
```

---

## Self-review (executado na escrita do plano)

- **Cobertura da spec:** tabelas+CRUD (T1), precedência no core (T2), worker injeta (T3), UI HTMX com selo/excluir/erros (T4), remoção Dias/Qt completa (T5), tutorial_seen+endpoint (T6), driver.js vendorizado+tour por segmentos+botão+auto-start+skip-marca (T7, incl. teste manual). ✔
- **Placeholders:** nenhum "TBD"/"similar à task N"; todo step de código tem o código. ✔
- **Consistência de tipos:** `ref_codes.benefit_tuples -> list[(op, valor|None, cod)]` casa com `codigos_extras` do core (T2) e com o worker (T3); fixtures `(client, db)` seguem o conftest real; `startTour(0)` do botão (T7 Step 5) é definida em tour.js (T7 Step 7). ✔
- **Nota ao executor:** os números de linha citados refletem o código em `main` neste commit; se drifts pequenos ocorrerem, localizar pelos trechos citados.
