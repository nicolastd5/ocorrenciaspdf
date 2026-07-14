# Códigos de ocorrência + layout de site + tutorial 2.0 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Usuários criam códigos de ocorrência próprios (visíveis no form e no MOTIVO), o app ganha layout de site em tela cheia (dropzones, painel de requisitos, recentes, pílulas) e o tutorial ganha tema próprio, welcome modal e conteúdo didático.

**Architecture:** Tabela nova `custom_occurrence_codes` gerida por `app/ref_codes.py` (mesmo padrão das duas existentes); `montar_motivo`/`processar` do core ganham `config_extras` opcional injetado pelo worker; página Códigos ganha terceira seção HTMX. Layout: reescrita do CSS em `app_base.html` + templates das 4 páginas + `app/static/app.js` (dropzones e busca, JS puro). Tutorial: `tour-theme.css` sobrescreve o driver.js e `tour.js` é reescrito com HTML rico e welcome modal.

**Tech Stack:** FastAPI, Jinja2, HTMX (vendorizado), SQLite, driver.js 1.3.1 (já vendorizado), JS vanilla, pytest.

## Global Constraints

- Trabalho todo em `license-server/`; testes rodam de lá: `python -m pytest tests -q`.
- Estilo existente: rotas síncronas (`def`), SQLite via `app/db.py:get_connection`, CSRF via `verify_csrf_token`/`get_or_create_csrf_token`, datas `datetime.utcnow().isoformat()`.
- Sem CDN em runtime para JS/CSS de bibliotecas (driver.js já é local; fontes Google podem permanecer).
- Personalizados são **globais**; embutidos (`TODOS_CODIGOS`, `ORDEM`, `SEM_QUANTIDADE`, `DESCRICOES`) **não mudam**.
- Código de ocorrência: `strip().upper()`, máx. **4 caracteres**, duplicata bloqueada contra personalizados E contra os 11 embutidos.
- Ordem no MOTIVO: embutidos na `ORDEM` primeiro, personalizados em ordem alfabética depois.
- Layout: sidebar e tema escuro mantidos; conteúdo full-width.
- **Os anchors `data-tour` existentes NÃO podem sumir** (testes atuais dependem de `nav-ocorrencias`, `btn-tutorial`, `oc-pdf`, `oc-xlsx`, `oc-codigos`, `oc-processar`, `vt-fonte`, `vt-cadastral`, `vt-processar`, `hist-filtros`, `hist-export`, `cod-beneficio`, `cod-add-beneficio`, `cod-depart`).
- A suíte inteira verde ao fim de cada task; commits em português (`feat:`, `fix:`).
- Números de linha citados refletem o HEAD `b2645df`; em caso de drift, localizar pelo trecho.

---

## Estrutura de arquivos

```
license-server/
  app/
    ref_codes.py                          # + occurrence codes (Task 1)
    db.py                                 # + tabela custom_occurrence_codes (Task 1)
    worker_tasks.py                       # _processar_final injeta config_extras (Task 3)
    routes_codigos.py                     # + seção ocorrência (Task 4)
    routes_app.py                         # form dinâmico + recentes (Tasks 5, 6)
    static/
      app.js                              # NOVO: dropzones + busca em tabela (Task 6)
      tour-theme.css                      # NOVO: tema do tutorial (Task 7)
      tour.js                             # reescrito (Task 7)
    templates/
      app_base.html                       # CSS/estrutura reescritos (Task 6)
      ocorrencias.html                    # reescrito: grid + dropzones + pílulas (Tasks 5, 6)
      vt_caixa.html                       # reescrito: grid + dropzones (Task 6)
      historico.html                      # chips + largura total (Task 6)
      codigos.html                        # grid de 3 cards (Task 4)
      codigos_ocorrencia_fragment.html    # NOVO (Task 4)
      codigos_beneficio_fragment.html     # + input de busca (Task 6)
      codigos_depart_fragment.html        # + input de busca (Task 6)
  core/
    processador.py                        # montar_motivo/processar com config_extras (Task 2)
  tests/
    test_ref_codes.py                     # + ocorrência (Task 1)
    tests/core/test_processador.py        # + config_extras (Task 2)
    test_worker_tasks.py                  # + injeção (Task 3)
    test_routes_codigos.py                # + seção nova (Task 4)
    test_routes_app.py                    # form dinâmico, recentes, tour 2.0 (Tasks 5–7)
    test_routes_jobs.py                   # POST aceita código personalizado (Task 5)
```

---

### Task 1: Tabela + CRUD de códigos de ocorrência em `ref_codes.py`

**Files:**
- Modify: `license-server/app/db.py` (final da string `SCHEMA`)
- Modify: `license-server/app/ref_codes.py`
- Test: `license-server/tests/test_ref_codes.py` (acrescentar)

**Interfaces:**
- Consumes: `app.db.get_connection`; `core.processador.ProcessadorOcorrencias.TODOS_CODIGOS` (lista dos 11 embutidos).
- Produces (usado nas Tasks 3, 4, 5):
  - `ref_codes.list_occurrence_codes(db_path) -> list[dict]` — dicts com `id, codigo, descricao, com_quantidade (0/1), created_by, created_at`, ordenado por `codigo`
  - `ref_codes.add_occurrence_code(db_path, user_id: int, codigo: str, descricao: str, com_quantidade: bool) -> int` — ValueError se vazio, > 4 chars, duplicado (personalizado ou embutido)
  - `ref_codes.delete_occurrence_code(db_path, code_id: int) -> None`
  - `ref_codes.occurrence_config(db_path) -> list[dict]` — `[{"codigo": str, "com_quantidade": bool}, ...]` em ordem alfabética

- [ ] **Step 1: Escrever os testes** (acrescentar em `license-server/tests/test_ref_codes.py`; a fixture `db` já existe no arquivo)

```python
def test_add_e_list_ocorrencia(db):
    rid = ref_codes.add_occurrence_code(db, 1, "fr", "Férias Remuneradas", True)
    lst = ref_codes.list_occurrence_codes(db)
    assert len(lst) == 1
    assert lst[0]["id"] == rid
    assert lst[0]["codigo"] == "FR"          # normalizado p/ uppercase
    assert lst[0]["descricao"] == "Férias Remuneradas"
    assert lst[0]["com_quantidade"] == 1


def test_ocorrencia_validacoes(db):
    import pytest
    with pytest.raises(ValueError):
        ref_codes.add_occurrence_code(db, 1, "", "desc", True)
    with pytest.raises(ValueError):
        ref_codes.add_occurrence_code(db, 1, "ABCDE", "desc", True)   # > 4 chars
    with pytest.raises(ValueError):
        ref_codes.add_occurrence_code(db, 1, "FR", "", True)          # sem descrição


def test_ocorrencia_duplicata_personalizado(db):
    import pytest
    ref_codes.add_occurrence_code(db, 1, "FR", "Férias", True)
    with pytest.raises(ValueError):
        ref_codes.add_occurrence_code(db, 2, "fr", "Outra", False)


def test_ocorrencia_duplicata_embutido(db):
    import pytest
    with pytest.raises(ValueError):
        ref_codes.add_occurrence_code(db, 1, "FA", "Faltas de novo", True)
    with pytest.raises(ValueError):
        ref_codes.add_occurrence_code(db, 1, "at", "Atestado 2", True)


def test_occurrence_config_e_delete(db):
    ref_codes.add_occurrence_code(db, 1, "ZZ", "Zeta", True)
    rid = ref_codes.add_occurrence_code(db, 1, "BB", "Beta", False)
    assert ref_codes.occurrence_config(db) == [
        {"codigo": "BB", "com_quantidade": False},
        {"codigo": "ZZ", "com_quantidade": True},
    ]
    ref_codes.delete_occurrence_code(db, rid)
    assert ref_codes.occurrence_config(db) == [{"codigo": "ZZ", "com_quantidade": True}]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_ref_codes.py -v`
Expected: FAIL — `AttributeError: module 'app.ref_codes' has no attribute 'add_occurrence_code'`

- [ ] **Step 3: Implementar**

Em `license-server/app/db.py`, acrescentar ao final da string `SCHEMA` (antes das aspas de fechamento):

```sql
CREATE TABLE IF NOT EXISTS custom_occurrence_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL,
    descricao TEXT NOT NULL,
    com_quantidade INTEGER NOT NULL DEFAULT 1,
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
);
```

Em `license-server/app/ref_codes.py`, acrescentar ao final:

```python
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
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_ref_codes.py -v`
Expected: PASS (todos, incluindo os 5 novos)

- [ ] **Step 5: Commit**

```bash
git add license-server/app/db.py license-server/app/ref_codes.py license-server/tests/test_ref_codes.py
git commit -m "feat(web): tabela e CRUD de codigos de ocorrencia personalizados"
```

---

### Task 2: Core — `montar_motivo`/`processar` com `config_extras`

**Files:**
- Modify: `license-server/core/processador.py` (método `montar_motivo` e `processar`)
- Test: `license-server/tests/core/test_processador.py` (acrescentar)

**Interfaces:**
- Produces (usado na Task 3):
  - `montar_motivo(self, ocorrencias, codigos_selecionados, config_extras=None)`
  - `processar(self, pdf_path, xlsx_path, output_path, codigos, progress_cb=None, dados_externos=None, config_extras=None)`
  - `config_extras`: `list[dict]` `[{"codigo": str, "com_quantidade": bool}]`; códigos extras entram DEPOIS de `ORDEM` (na ordem recebida — o chamador já manda alfabético); `com_quantidade=False` = comportamento de AP/LM/FE

- [ ] **Step 1: Escrever os testes** (acrescentar em `license-server/tests/core/test_processador.py`)

```python
def test_montar_motivo_config_extras_ordem_e_quantidade():
    p = ProcessadorOcorrencias()
    extras = [{"codigo": "BB", "com_quantidade": False},
              {"codigo": "FR", "com_quantidade": True}]
    ocorr = {"FR": 2, "FA": 1, "BB": 3}
    # embutido (FA) vem primeiro; extras depois na ordem recebida;
    # BB sem quantidade mesmo com contagem 3; FR com quantidade.
    assert p.montar_motivo(ocorr, ["FA", "FR", "BB"], extras) == "FA, BB, 2 FR"


def test_montar_motivo_sem_extras_inalterado():
    p = ProcessadorOcorrencias()
    ocorr = {"AT": 2, "FA": 1, "AP": 3}
    assert p.montar_motivo(ocorr, ["FA", "AT", "AP"]) == "FA, 2 AT, AP"


def test_processar_aceita_config_extras():
    import inspect
    sig = inspect.signature(ProcessadorOcorrencias.processar)
    assert "config_extras" in sig.parameters
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/core/test_processador.py -v`
Expected: FAIL — `TypeError: montar_motivo() takes 3 positional arguments but 4 were given`

- [ ] **Step 3: Implementar**

Em `license-server/core/processador.py`, substituir `montar_motivo` inteiro por:

```python
    def montar_motivo(self, ocorrencias, codigos_selecionados, config_extras=None):
        """
        Monta a string de motivo a partir das ocorrências.

        Regras:
        - Ordem: embutidos (self.ORDEM) primeiro, depois os códigos de
          config_extras na ordem recebida
        - Quantidade na frente quando > 1 (ex: 2 AT, 3 FA)
        - AP/LM/FE — e extras com com_quantidade=False — nunca recebem quantidade
        - Múltiplos códigos separados por vírgula
        """
        extras = config_extras or []
        ordem = self.ORDEM + [c["codigo"] for c in extras
                              if c["codigo"] not in self.ORDEM]
        sem_quantidade = set(self.SEM_QUANTIDADE) | {
            c["codigo"] for c in extras if not c["com_quantidade"]
        }
        partes = []
        codigos_set = set(codigos_selecionados)

        for codigo in ordem:
            if codigo in ocorrencias and codigo in codigos_set:
                contagem = ocorrencias[codigo]
                if codigo in sem_quantidade:
                    partes.append(codigo)
                elif contagem > 1:
                    partes.append(f"{contagem} {codigo}")
                else:
                    partes.append(codigo)

        return ', '.join(partes)
```

Na assinatura de `processar`, acrescentar o parâmetro final:

```python
    def processar(self, pdf_path, xlsx_path, output_path, codigos,
                  progress_cb=None, dados_externos=None, config_extras=None):
```

E nas **duas** chamadas de `montar_motivo` dentro de `processar` (a do cruzamento
e a dos não encontrados), acrescentar o argumento:

```python
                    motivo = self.montar_motivo(ocorr, codigos, config_extras)
```

```python
            motivo = self.montar_motivo(dados['ocorrencias'], codigos, config_extras)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/core -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add license-server/core/processador.py license-server/tests/core/test_processador.py
git commit -m "feat(web): montar_motivo aceita codigos extras com regra de quantidade"
```

---

### Task 3: Worker injeta `config_extras` nos jobs de Ocorrências

**Files:**
- Modify: `license-server/app/worker_tasks.py` (função `_processar_final`)
- Test: `license-server/tests/test_worker_tasks.py` (acrescentar)

**Interfaces:**
- Consumes: `ref_codes.occurrence_config(db_path)` (Task 1); `processar(..., config_extras=)` (Task 2).
- Produces: nenhum contrato novo (assinaturas do worker inalteradas).

- [ ] **Step 1: Escrever o teste** (acrescentar em `license-server/tests/test_worker_tasks.py`; usa as fixtures/helpers `env`, `_setup_job` e os monkeypatches de extração já existentes no arquivo)

```python
def test_ocorrencias_injeta_config_extras(env, monkeypatch):
    db, data_dir = env
    from app import ref_codes
    ref_codes.add_occurrence_code(db, 1, "FR", "Férias Rem.", False)

    dados = {"12345": {"nome": "ANA", "ocorrencias": {"FR": 2}}}
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias",
                        lambda self, p, c: dados)
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias_texto",
                        lambda self, p, c: dados)
    jid = _setup_job(db, data_dir, params={"codigos": ["FA", "FR"]})
    worker_tasks.run_ocorrencias(db, data_dir, jid)
    j = jobs.get_job(db, jid)
    assert j["status"] == "done"
    # com_quantidade=False: motivo é "FR", não "2 FR"
    assert j["result"]["atualizados"][0]["motivo"] == "FR"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_worker_tasks.py::test_ocorrencias_injeta_config_extras -v`
Expected: FAIL — motivo é `"2 FR"` (extras não injetados)

- [ ] **Step 3: Implementar**

Em `license-server/app/worker_tasks.py`, garantir o import no topo
(`from app import history, jobs, ref_codes`) e em `_processar_final` acrescentar
o argumento na chamada de `processar`:

```python
    result = p.processar(
        pdf_path=None,
        xlsx_path=str(d / "in" / params["xlsx_name"]),
        output_path=str(out),
        codigos=params["codigos"],
        progress_cb=_progress_cb(db_path, job_id),
        dados_externos=dados,
        config_extras=ref_codes.occurrence_config(db_path),
    )
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_worker_tasks.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add license-server/app/worker_tasks.py license-server/tests/test_worker_tasks.py
git commit -m "feat(web): worker de ocorrencias usa codigos personalizados no motivo"
```

---

### Task 4: Seção "Códigos de Ocorrência" na página Códigos

**Files:**
- Modify: `license-server/app/routes_codigos.py`
- Create: `license-server/app/templates/codigos_ocorrencia_fragment.html`
- Modify: `license-server/app/templates/codigos.html`
- Test: `license-server/tests/test_routes_codigos.py` (acrescentar)

**Interfaces:**
- Consumes: `ref_codes.list_occurrence_codes/add_occurrence_code/delete_occurrence_code` (Task 1); `ProcessadorOcorrencias.TODOS_CODIGOS/DESCRICOES/SEM_QUANTIDADE`.
- Produces:
  - `GET /app/codigos` passa também `ocorrencia_rows` (embutidos com `id=None` + personalizados) e `ocorrencia_error`
  - `POST /app/codigos/ocorrencia` (form: codigo, descricao, com_quantidade opcional "1", csrf_token) → fragmento
  - `POST /app/codigos/ocorrencia/{code_id}/excluir` (form: csrf_token) → fragmento
  - Anchors novos: `data-tour="cod-ocorrencia"` e `data-tour="cod-add-ocorrencia"`

- [ ] **Step 1: Escrever os testes** (acrescentar em `license-server/tests/test_routes_codigos.py`)

```python
def test_pagina_mostra_ocorrencias_embutidas_e_personalizadas(logged_client):
    c, db = logged_client
    from app import ref_codes
    ref_codes.add_occurrence_code(db, 1, "FR", "Férias Remuneradas", True)
    r = c.get("/app/codigos")
    assert r.status_code == 200
    assert "Faltas" in r.text                 # descrição do embutido FA
    assert "Férias Remuneradas" in r.text     # personalizado


def test_adicionar_ocorrencia(logged_client, user_csrf):
    c, db = logged_client
    r = c.post("/app/codigos/ocorrencia", data={
        "codigo": "fr", "descricao": "Férias Rem.", "com_quantidade": "1",
        "csrf_token": user_csrf,
    })
    assert r.status_code == 200
    assert "FR" in r.text
    from app import ref_codes
    assert ref_codes.occurrence_config(db) == [{"codigo": "FR", "com_quantidade": True}]


def test_adicionar_ocorrencia_sem_quantidade(logged_client, user_csrf):
    c, db = logged_client
    c.post("/app/codigos/ocorrencia", data={
        "codigo": "BB", "descricao": "Beta", "csrf_token": user_csrf,
    })  # checkbox desmarcado: campo ausente
    from app import ref_codes
    assert ref_codes.occurrence_config(db) == [{"codigo": "BB", "com_quantidade": False}]


def test_adicionar_ocorrencia_embutido_da_erro(logged_client, user_csrf):
    c, db = logged_client
    r = c.post("/app/codigos/ocorrencia", data={
        "codigo": "FA", "descricao": "Faltas 2", "com_quantidade": "1",
        "csrf_token": user_csrf,
    })
    assert r.status_code == 400
    assert "embutido" in r.text


def test_excluir_ocorrencia(logged_client, user_csrf):
    c, db = logged_client
    from app import ref_codes
    rid = ref_codes.add_occurrence_code(db, 1, "FR", "Férias", True)
    r = c.post(f"/app/codigos/ocorrencia/{rid}/excluir",
               data={"csrf_token": user_csrf})
    assert r.status_code == 200
    assert ref_codes.list_occurrence_codes(db) == []


def test_ocorrencia_post_sem_login(client):
    c, _ = client
    r = c.post("/app/codigos/ocorrencia", data={"codigo": "X", "descricao": "d"},
               follow_redirects=False)
    assert r.status_code == 303
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_routes_codigos.py -v`
Expected: FAIL — 404 nas rotas novas

- [ ] **Step 3: Implementar as rotas**

Em `license-server/app/routes_codigos.py`, acrescentar o import
`from core.processador import ProcessadorOcorrencias` e:

```python
def _ctx_ocorrencia(request: Request, db_path: str, error: str | None = None) -> dict:
    builtin = [{"codigo": c,
                "descricao": ProcessadorOcorrencias.DESCRICOES.get(c, ""),
                "com_quantidade": 0 if c in ProcessadorOcorrencias.SEM_QUANTIDADE else 1,
                "id": None}
               for c in ProcessadorOcorrencias.TODOS_CODIGOS]
    return {
        "ocorrencia_rows": builtin + ref_codes.list_occurrence_codes(db_path),
        "csrf_token": get_or_create_csrf_token(request),
        "ocorrencia_error": error,
    }


@router.post("/app/codigos/ocorrencia", response_class=HTMLResponse)
def ocorrencia_add(request: Request, codigo: str = Form(""),
                   descricao: str = Form(""), com_quantidade: str = Form(""),
                   csrf_token: str = Form(""), _=Depends(require_user)):
    db = request.app.state.settings.db_path
    error, status_code = None, 200
    if not verify_csrf_token(request.session.get("csrf_token"), csrf_token):
        error, status_code = "Sessão expirada — recarregue a página.", 400
    else:
        try:
            ref_codes.add_occurrence_code(db, current_user_id(request),
                                          codigo, descricao,
                                          com_quantidade == "1")
        except ValueError as e:
            error, status_code = str(e), 400
    return templates.TemplateResponse(
        request, "codigos_ocorrencia_fragment.html",
        _ctx_ocorrencia(request, db, error), status_code=status_code)


@router.post("/app/codigos/ocorrencia/{code_id}/excluir", response_class=HTMLResponse)
def ocorrencia_delete(request: Request, code_id: int,
                      csrf_token: str = Form(""), _=Depends(require_user)):
    db = request.app.state.settings.db_path
    if verify_csrf_token(request.session.get("csrf_token"), csrf_token):
        ref_codes.delete_occurrence_code(db, code_id)
    return templates.TemplateResponse(
        request, "codigos_ocorrencia_fragment.html", _ctx_ocorrencia(request, db))
```

E em `codigos_page`, incluir o contexto novo:

```python
    ctx = {**_ctx_beneficio(request, db), **_ctx_depart(request, db),
           **_ctx_ocorrencia(request, db),
           "active": "codigos", "tutorial_seen": bool(user["tutorial_seen"])}
```

- [ ] **Step 4: Criar o fragmento e incluir na página**

Criar `license-server/app/templates/codigos_ocorrencia_fragment.html`:

```html
<div id="sec-ocorrencia" class="card" data-tour="cod-ocorrencia">
    <div class="card-title">Códigos de Ocorrência</div>
    <form hx-post="/app/codigos/ocorrencia" hx-target="#sec-ocorrencia" hx-swap="outerHTML"
          class="card-add-form" data-tour="cod-add-ocorrencia">
        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
        <div style="flex:0 0 90px"><label>Código</label>
            <input type="text" name="codigo" placeholder="FR" maxlength="4" required></div>
        <div style="flex:1"><label>Descrição</label>
            <input type="text" name="descricao" placeholder="Férias Remuneradas" required></div>
        <label class="check" style="margin:0 0 8px" title="Se marcado, o MOTIVO mostra a contagem (ex.: 2 FR)">
            <input type="checkbox" name="com_quantidade" value="1" checked> quantidade
        </label>
        <button type="submit" class="btn btn-primary btn-sm" style="height:36px">Adicionar</button>
    </form>
    {% if ocorrencia_error %}
    <div class="alert alert-error" style="margin:12px 16px 0">{{ ocorrencia_error }}</div>
    {% endif %}
    <table>
        <thead>
            <tr><th>Código</th><th>Descrição</th><th>Quantidade</th><th></th></tr>
        </thead>
        <tbody>
            {% for r in ocorrencia_rows %}
            <tr>
                <td class="key">{{ r.codigo }}</td>
                <td>{{ r.descricao }}</td>
                <td class="meta">{{ "com quantidade" if r.com_quantidade else "sem quantidade" }}</td>
                <td style="text-align:right">
                    {% if r.id %}
                    <span class="meta" style="margin-right:8px">personalizado</span>
                    <form hx-post="/app/codigos/ocorrencia/{{ r.id }}/excluir"
                          hx-target="#sec-ocorrencia" hx-swap="outerHTML"
                          hx-confirm="Excluir o código {{ r.codigo }}?" style="display:inline">
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

Nota: as classes `card-title` e `card-add-form` são criadas na Task 6; até lá,
se o CSS ainda não existir, o fragmento funciona com o estilo default (os
testes só verificam HTML). Se a Task 6 já tiver sido executada, nada a fazer.

Em `license-server/app/templates/codigos.html`, incluir o novo fragmento no
grid (primeiro, por ser o mais usado no dia a dia):

```html
<div class="code-grid">
    {% include "codigos_ocorrencia_fragment.html" %}
    {% include "codigos_beneficio_fragment.html" %}
    {% include "codigos_depart_fragment.html" %}
</div>
```

E atualizar o subtítulo da página para:

```html
    <p>Consulte e copie códigos, e cadastre novos — códigos de ocorrência valem
       no processamento de Ocorrências; benefícios e departamentos, no VT-Caixa.
       Personalizados têm precedência sobre os embutidos.</p>
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python -m pytest tests/test_routes_codigos.py -v`
Expected: PASS

- [ ] **Step 6: Rodar a suíte inteira**

Run: `python -m pytest tests -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add license-server/app license-server/tests
git commit -m "feat(web): secao de codigos de ocorrencia na pagina codigos"
```

---

### Task 5: Form de Ocorrências dinâmico (embutidos + personalizados)

**Files:**
- Modify: `license-server/app/routes_app.py` (rota `GET /app/ocorrencias`)
- Modify: `license-server/app/templates/ocorrencias.html` (lista de códigos)
- Test: `license-server/tests/test_routes_app.py` e `license-server/tests/test_routes_jobs.py` (acrescentar)

**Interfaces:**
- Consumes: `ref_codes.list_occurrence_codes` (Task 1), `ProcessadorOcorrencias.TODOS_CODIGOS/DESCRICOES`.
- Produces: contexto `codigos_disponiveis: list[dict]` — `[{"codigo", "descricao", "custom": bool}, ...]` (embutidos primeiro, personalizados depois) — consumido também pelo template reescrito na Task 6.

- [ ] **Step 1: Escrever os testes**

Em `license-server/tests/test_routes_app.py`:

```python
def test_form_ocorrencias_mostra_codigo_personalizado(logged_client):
    c, db = logged_client
    from app import ref_codes
    ref_codes.add_occurrence_code(db, 1, "FR", "Férias Remuneradas", True)
    r = c.get("/app/ocorrencias")
    assert 'value="FR"' in r.text
    assert 'value="FA"' in r.text   # embutidos continuam
```

Em `license-server/tests/test_routes_jobs.py` (usa `_upload` e mocks já existentes no arquivo — acrescentar o parâmetro `codigos` ao helper se ele for fixo; o helper atual envia `"codigos": ["FA", "AT"]`, então este teste faz o POST direto):

```python
def test_upload_aceita_codigo_personalizado(logged_client, user_csrf, monkeypatch):
    import io
    from openpyxl import Workbook
    dados = {"12345": {"nome": "ANA", "ocorrencias": {"FR": 1}}}
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias",
                        lambda self, p, c: dados)
    monkeypatch.setattr("core.processador.ProcessadorOcorrencias.extrair_ocorrencias_texto",
                        lambda self, p, c: dados)
    c, db = logged_client
    wb = Workbook(); ws = wb.active
    ws.append(["Folha RE", "Nome", "MOTIVO"]); ws.append(["12345", "ANA", ""])
    buf = io.BytesIO(); wb.save(buf)
    r = c.post("/app/ocorrencias", data={
        "codigos": ["FR"], "csrf_token": user_csrf,
    }, files={
        "pdf": ("jornada.pdf", b"%PDF-fake", "application/pdf"),
        "xlsx": ("pedido.xlsx", buf.getvalue(), "application/octet-stream"),
    }, follow_redirects=False)
    assert r.status_code == 303
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_routes_app.py::test_form_ocorrencias_mostra_codigo_personalizado -v`
Expected: FAIL — `value="FR"` ausente (lista fixa no template)

(O teste de upload já deve passar — o POST aceita qualquer código; confirmar.)

- [ ] **Step 3: Implementar**

Em `license-server/app/routes_app.py`, imports novos:
`from app import ref_codes` e `from core.processador import ProcessadorOcorrencias`.
A rota `ocorrencias` vira:

```python
@router.get("/app/ocorrencias", response_class=HTMLResponse)
def ocorrencias(request: Request, _=Depends(require_user)):
    settings = request.app.state.settings
    builtin = [{"codigo": c,
                "descricao": ProcessadorOcorrencias.DESCRICOES.get(c, ""),
                "custom": False}
               for c in ProcessadorOcorrencias.TODOS_CODIGOS]
    custom = [{"codigo": r["codigo"], "descricao": r["descricao"], "custom": True}
              for r in ref_codes.list_occurrence_codes(settings.db_path)]
    return templates.TemplateResponse(request, "ocorrencias.html", {
        "csrf_token": get_or_create_csrf_token(request), "active": "ocorrencias",
        "tutorial_seen": _tutorial_seen(request),
        "codigos_disponiveis": builtin + custom,
    })
```

Em `license-server/app/templates/ocorrencias.html`, substituir o bloco da lista
fixa (linhas 19–27: o `{% for cod in ['FA',...] %}`) por:

```html
        <label>Códigos de ocorrência
            <a href="/app/codigos" class="meta" style="font-weight:400;margin-left:8px">gerenciar códigos →</a>
        </label>
        <div data-tour="oc-codigos" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:4px">
            {% for c in codigos_disponiveis %}
            <label class="check" title="{{ c.descricao }}">
                <input type="checkbox" name="codigos" value="{{ c.codigo }}" checked>
                {{ c.codigo }}
            </label>
            {% endfor %}
        </div>
```

(O visual em pílulas chega na Task 6; aqui é só o dado dinâmico.)

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_routes_app.py tests/test_routes_jobs.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add license-server/app license-server/tests
git commit -m "feat(web): form de ocorrencias renderiza codigos embutidos + personalizados"
```

---

### Task 6: Layout de site — full-width, dropzones, requisitos, recentes, chips

> **REQUIRED SUB-SKILL:** antes de escrever qualquer template/CSS desta task,
> o executor deve invocar a skill **`frontend-design`** para calibrar as
> decisões visuais. O código abaixo é o contrato base (estrutura, classes,
> anchors, comportamento); refinamentos de espaçamento/tipografia vindos da
> skill são bem-vindos desde que classes, ids e `data-tour` não mudem.

**Files:**
- Modify: `license-server/app/templates/app_base.html` (bloco `<style>` inteiro + favicon)
- Create: `license-server/app/static/app.js`
- Rewrite: `license-server/app/templates/ocorrencias.html`, `vt_caixa.html`, `historico.html`
- Modify: `license-server/app/templates/codigos_beneficio_fragment.html`, `codigos_depart_fragment.html`, `codigos_ocorrencia_fragment.html` (título/form em classes + input de busca)
- Modify: `license-server/app/routes_app.py` (rotas passam `recentes`)
- Test: `license-server/tests/test_routes_app.py` (acrescentar)

**Interfaces:**
- Consumes: `history_module.list_for_user(db_path, user_id, q="", status="")` (existente), `codigos_disponiveis` (Task 5).
- Produces:
  - Contexto `recentes: list[dict]` (até 5 entradas do histórico do usuário filtradas por tipo) nas rotas `ocorrencias` e `vt_caixa`
  - Classes CSS estáveis: `page-grid`, `dropzone`, `pill-grid`, `pill`, `aside-card`, `steps`, `chip chip-ok`, `chip chip-err`, `card-title`, `card-add-form`, `table-filter`
  - `app.js`: inicializa `[data-dropzone]` e `[data-filter]` no `DOMContentLoaded` e em `htmx:afterSwap`

- [ ] **Step 1: Escrever os testes** (acrescentar em `license-server/tests/test_routes_app.py`)

```python
def test_paginas_incluem_app_js(logged_client):
    c, _ = logged_client
    r = c.get("/app/ocorrencias")
    assert 'src="/static/app.js"' in r.text
    assert 'class="dropzone"' in r.text
    assert 'data-tour="oc-pdf"' in r.text          # anchor preservado
    assert 'data-tour="oc-processar"' in r.text


def test_ocorrencias_mostra_requisitos_e_recentes(logged_client):
    c, db = logged_client
    from app import history
    history.add(db, 1, "j1", "ocorrencias", "sucesso", ["jornada.pdf"], {"matched": 3})
    history.add(db, 1, "j2", "vt_caixa", "sucesso", ["nautilus.pdf"], {"total_ok": 9})
    r = c.get("/app/ocorrencias")
    assert "Folha RE" in r.text and "MOTIVO" in r.text   # card de requisitos
    assert "jornada.pdf" in r.text                        # recente do tipo certo
    assert "nautilus.pdf" not in r.text                   # tipo errado não aparece


def test_historico_usa_chips(logged_client):
    c, db = logged_client
    from app import history
    history.add(db, 1, "j1", "ocorrencias", "erro", ["x.pdf"], {})
    r = c.get("/app/historico")
    assert 'class="chip chip-err"' in r.text
```

Nota: `history.add` usa `user_id` — se a fixture `logged_client` criar o usuário
com id diferente de 1, obter o id real (`users.list_users(db)[0]["id"]`).

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_routes_app.py -v`
Expected: FAIL

- [ ] **Step 3: Rotas passam `recentes`**

Em `license-server/app/routes_app.py`, acrescentar helper e usar nas duas rotas:

```python
def _recentes(request: Request, kind: str) -> list[dict]:
    settings = request.app.state.settings
    entries = history_module.list_for_user(settings.db_path, current_user_id(request))
    return [e for e in entries if e["kind"] == kind][:5]
```

Na rota `ocorrencias`, acrescentar ao contexto: `"recentes": _recentes(request, "ocorrencias"),`
Na rota `vt_caixa`: `"recentes": _recentes(request, "vt_caixa"),`

- [ ] **Step 4: Reescrever o `<style>` de `app_base.html`**

No `<head>`, acrescentar (após a linha do htmx):

```html
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='22' fill='%233b82f6'/><rect x='22' y='26' width='56' height='8' rx='4' fill='white'/><rect x='22' y='46' width='56' height='8' rx='4' fill='white'/><rect x='22' y='66' width='36' height='8' rx='4' fill='white'/></svg>">
<script src="/static/app.js" defer></script>
```

Substituir o bloco `<style>...</style>` inteiro por:

```html
<style>
:root{
  --bg:#0d0f14; --surface:#171a21; --surface-2:#1f242d; --border:#2b303a;
  --text:#c9d4e6; --text-bright:#f0f6fc; --text-muted:#8b95a7;
  --accent:#3b82f6; --green:#3fb950; --red:#f85149; --amber:#e3b341;
  --grad:linear-gradient(135deg,#3b82f6,#22c55e);
  --radius:14px; --radius-sm:9px;
  --font:'Inter','Segoe UI',system-ui,sans-serif;
  --mono:'JetBrains Mono','Cascadia Mono',Consolas,monospace;
  --shadow:0 8px 28px rgba(0,0,0,.35);
}
*{box-sizing:border-box;margin:0;padding:0}
html{scrollbar-color:var(--surface-2) var(--bg)}
::-webkit-scrollbar{width:10px;height:10px}
::-webkit-scrollbar-thumb{background:var(--surface-2);border-radius:5px}
::-webkit-scrollbar-track{background:transparent}
body{
  font-family:var(--font); color:var(--text); background:var(--bg); font-size:14px;
  min-height:100vh;
  background-image:
    radial-gradient(1100px 560px at 85% -10%, rgba(59,130,246,.10), transparent 60%),
    radial-gradient(800px 480px at -10% 105%, rgba(34,197,94,.07), transparent 60%);
  background-attachment:fixed;
}
a{color:var(--accent);text-decoration:none}

/* ---------- shell ---------- */
.shell{display:flex;min-height:100vh}
.sidebar{
  width:236px;flex-shrink:0;display:flex;flex-direction:column;gap:2px;
  padding:20px 14px;border-right:1px solid var(--border);
  background:rgba(23,26,33,.72);backdrop-filter:blur(8px);
  position:sticky;top:0;height:100vh;
}
.brand{display:flex;align-items:center;gap:11px;padding:4px 6px 18px}
.brand-logo{
  width:36px;height:36px;border-radius:10px;background:var(--grad);
  display:flex;align-items:center;justify-content:center;
  color:#fff;font-size:18px;font-weight:700;
  box-shadow:0 4px 16px rgba(59,130,246,.4);
}
.brand-name{font-size:12.5px;font-weight:600;color:var(--text-bright);line-height:1.25}
.sidebar nav{display:flex;flex-direction:column;gap:2px}
.sidebar nav a{
  display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:9px;
  color:var(--text);font-weight:500;font-size:13.5px;
  border:1px solid transparent;transition:background .15s,border-color .15s;
}
.sidebar nav a svg{width:16px;height:16px;color:var(--text-muted);flex-shrink:0}
.sidebar nav a:hover{background:var(--surface-2)}
.sidebar nav a.active{background:var(--surface-2);color:var(--text-bright);border-color:var(--border)}
.sidebar nav a.active svg{color:var(--accent)}
.sidebar .user-info{
  padding:12px 11px 8px;font-size:12px;color:var(--text-muted);
  border-top:1px solid var(--border);margin-top:auto;
}
.sidebar .user-info .name{color:var(--text-bright);font-weight:600;font-size:13px}
.logout a{
  display:flex;align-items:center;gap:10px;padding:9px 11px;border-radius:8px;
  color:var(--text-muted);font-size:13.5px;
}
.logout a:hover{background:var(--surface-2);color:var(--text)}
main{flex:1;min-width:0;padding:32px clamp(24px,4vw,56px) 48px}

/* ---------- header ---------- */
.crumb{font-size:12px;color:var(--text-muted);margin-bottom:6px;letter-spacing:.03em}
.crumb b{color:var(--text)}
.page-header{margin-bottom:26px}
.page-header h1{font-size:26px;font-weight:800;color:var(--text-bright);letter-spacing:-.02em}
.page-header p{color:var(--text-muted);margin-top:5px;font-size:14px;max-width:760px}

/* ---------- layout por página ---------- */
.page-grid{display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:22px;align-items:start}
@media(max-width:1100px){.page-grid{grid-template-columns:1fr}}
.stack{display:flex;flex-direction:column;gap:22px;min-width:0}

/* ---------- cards ---------- */
.card{
  background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  overflow:hidden;box-shadow:var(--shadow);
}
.card-title{
  padding:16px 20px;border-bottom:1px solid var(--border);
  font-weight:600;color:var(--text-bright);font-size:14px;
}
.card-add-form{
  display:flex;gap:10px;padding:14px 16px;border-bottom:1px solid var(--border);
  align-items:flex-end;flex-wrap:wrap;
}
.card-add-form label{margin:0 0 6px}
.form-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:26px 28px;box-shadow:var(--shadow)}
.form-actions{display:flex;gap:10px;margin-top:22px}
.aside-card{
  background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  padding:20px 22px;box-shadow:var(--shadow);
}
.aside-card h3{font-size:13px;font-weight:700;color:var(--text-bright);
  text-transform:uppercase;letter-spacing:.06em;margin-bottom:14px}
.aside-card + .aside-card{margin-top:18px}
.steps{list-style:none;counter-reset:s;display:flex;flex-direction:column;gap:12px}
.steps li{counter-increment:s;display:flex;gap:12px;font-size:13.5px;line-height:1.5}
.steps li::before{
  content:counter(s);flex-shrink:0;width:24px;height:24px;border-radius:50%;
  background:var(--surface-2);border:1px solid var(--border);color:var(--accent);
  font-weight:700;font-size:12px;display:flex;align-items:center;justify-content:center;
}
.req-list{list-style:none;display:flex;flex-direction:column;gap:10px;font-size:13px;line-height:1.5}
.req-list li{padding-left:20px;position:relative}
.req-list li::before{content:"✓";position:absolute;left:0;color:var(--green);font-weight:700}
.req-list code{
  font-family:var(--mono);font-size:11.5px;background:var(--surface-2);
  border:1px solid var(--border);border-radius:5px;padding:1px 6px;color:var(--amber);
}

/* ---------- dropzone ---------- */
.dropzone{
  border:1.5px dashed var(--border);border-radius:var(--radius-sm);
  padding:26px 18px;text-align:center;cursor:pointer;
  transition:border-color .15s,background .15s;position:relative;
}
.dropzone:hover,.dropzone.dragover{border-color:var(--accent);background:rgba(59,130,246,.06)}
.dropzone.filled{border-style:solid;border-color:rgba(63,185,80,.5);background:rgba(63,185,80,.05)}
.dropzone input[type=file]{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%}
.dropzone .dz-icon{font-size:22px;margin-bottom:6px;color:var(--text-muted)}
.dropzone.filled .dz-icon{color:var(--green)}
.dropzone .dz-text{font-size:13.5px;color:var(--text)}
.dropzone .dz-hint{font-size:12px;color:var(--text-muted);margin-top:3px}
.dropzone .dz-file{font-family:var(--mono);font-size:12.5px;color:var(--text-bright);word-break:break-all}
.dz-error{color:var(--red);font-size:12.5px;margin-top:6px;display:none}

/* ---------- pílulas de código ---------- */
.pill-grid{display:flex;flex-wrap:wrap;gap:8px}
.pill{position:relative;display:inline-flex}
.pill input{position:absolute;opacity:0;inset:0;cursor:pointer}
.pill span{
  padding:7px 14px;border-radius:999px;border:1px solid var(--border);
  background:var(--surface-2);color:var(--text-muted);font-size:12.5px;font-weight:600;
  transition:all .12s;user-select:none;
}
.pill input:checked + span{
  background:rgba(59,130,246,.15);border-color:var(--accent);color:var(--text-bright);
}
.pill input:focus-visible + span{outline:2px solid var(--accent);outline-offset:2px}

/* ---------- buttons ---------- */
.btn{
  display:inline-flex;align-items:center;gap:8px;padding:9px 18px;border-radius:var(--radius-sm);
  font-family:var(--font);font-size:13.5px;font-weight:600;cursor:pointer;
  border:1px solid var(--border);background:var(--surface-2);color:var(--text);
  transition:border-color .15s,opacity .15s;
}
.btn:hover{border-color:var(--text-muted)}
.btn-primary{background:var(--grad);border:none;color:#fff;box-shadow:0 3px 14px rgba(59,130,246,.35)}
.btn-primary:hover{opacity:.92}
.btn-danger{background:rgba(248,81,73,.12);border:1px solid rgba(248,81,73,.35);color:var(--red)}
.btn-ghost{background:transparent;border:1px solid var(--border);color:var(--text-muted)}
.btn-ghost:hover{color:var(--text);background:var(--surface-2)}
.btn-sm{padding:5px 12px;font-size:12.5px}
.btn:disabled{opacity:.4;cursor:not-allowed}

/* ---------- tables ---------- */
table{width:100%;border-collapse:collapse;font-size:13.5px}
th{
  text-align:left;padding:11px 18px;background:var(--surface-2);color:var(--text-muted);
  font-size:11.5px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;
  border-bottom:1px solid var(--border);
}
td{padding:11px 18px;border-bottom:1px solid rgba(43,48,58,.55);vertical-align:middle}
tr:last-child td{border-bottom:none}
tbody tr:hover{background:rgba(59,130,246,.045)}
td.empty{text-align:center;color:var(--text-muted);padding:36px}
.meta{color:var(--text-muted);font-size:12.5px}
.key{font-family:var(--mono);font-size:12px;color:var(--accent);letter-spacing:.02em}
.chip{
  display:inline-block;padding:3px 10px;border-radius:999px;font-size:11.5px;font-weight:700;
  text-transform:uppercase;letter-spacing:.04em;
}
.chip-ok{background:rgba(63,185,80,.12);border:1px solid rgba(63,185,80,.4);color:var(--green)}
.chip-err{background:rgba(248,81,73,.12);border:1px solid rgba(248,81,73,.4);color:var(--red)}
.table-filter{margin:12px 16px 0;width:calc(100% - 32px)}

/* ---------- forms ---------- */
label{display:block;font-size:12.5px;font-weight:600;color:var(--text-bright);margin:16px 0 7px}
input[type=text],input[type=email],input[type=password],input[type=number],textarea,select{
  width:100%;padding:9px 12px;border-radius:var(--radius-sm);font-family:var(--font);font-size:13.5px;
  background:var(--bg);border:1px solid var(--border);color:var(--text-bright);outline:none;
  transition:border-color .15s;
}
input:focus,textarea:focus,select:focus{border-color:var(--accent)}
textarea{min-height:84px;resize:vertical}
.hint{font-size:12.5px;color:var(--text-muted);margin-top:6px;line-height:1.55}
.check{display:flex;align-items:center;gap:8px;margin-top:10px;font-size:13px;color:var(--text)}
.check input[type=checkbox]{width:auto;accent-color:var(--accent)}

/* ---------- alerts / progress / toolbar ---------- */
.alert{padding:12px 16px;border-radius:var(--radius-sm);font-size:13.5px;margin-bottom:18px}
.alert-success{background:rgba(63,185,80,.1);border:1px solid rgba(63,185,80,.35);color:var(--green)}
.alert-error{background:rgba(248,81,73,.1);border:1px solid rgba(248,81,73,.35);color:var(--red)}
progress{width:100%;height:10px;border-radius:5px;overflow:hidden;-webkit-appearance:none;appearance:none}
progress::-webkit-progress-bar{background:var(--surface-2);border-radius:5px}
progress::-webkit-progress-value{background:var(--grad);border-radius:5px}
progress::-moz-progress-bar{background:var(--grad);border-radius:5px}
.toolbar{display:flex;gap:12px;align-items:center;margin-bottom:18px;flex-wrap:wrap}
.toolbar form{display:flex;gap:10px;flex:1;min-width:280px}
.toolbar input[type=text]{flex:1}
.toolbar select{width:auto}
.code-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(430px,1fr));gap:20px}
@media(max-width:960px){.code-grid{grid-template-columns:1fr}}
</style>
```

Diferenças-chave vs. atual: `main` sem `max-width` (padding fluido `clamp`),
tokens de sombra, `page-grid`/`stack`/`aside-card`/`steps`/`req-list`/
`dropzone`/`pill*`/`chip*`/`card-title`/`card-add-form`/`table-filter` novos,
`code-grid` com `auto-fit` para 3 cards. **Não** alterar o restante do
`app_base.html` (nav, brand, user-info, scripts do tour) além do favicon e do
`app.js` no head.

- [ ] **Step 5: Criar `license-server/app/static/app.js`**

```javascript
/* Interações do app: dropzones de upload e filtro de tabelas.
   Sem dependências; re-inicializa após swaps do HTMX. */
(function () {
  function initDropzones(root) {
    root.querySelectorAll(".dropzone:not([data-dz-ready])").forEach(function (dz) {
      dz.setAttribute("data-dz-ready", "1");
      var input = dz.querySelector('input[type="file"]');
      var text = dz.querySelector(".dz-text");
      var hint = dz.querySelector(".dz-hint");
      var err = dz.parentElement.querySelector(".dz-error");
      var emptyText = text.textContent;

      function accepted(name) {
        var accept = (input.getAttribute("accept") || "").split(",")
          .map(function (s) { return s.trim().toLowerCase(); }).filter(Boolean);
        if (!accept.length) return true;
        return accept.some(function (ext) { return name.toLowerCase().endsWith(ext); });
      }

      function showFile(file) {
        dz.classList.add("filled");
        text.innerHTML = '<span class="dz-file"></span>';
        text.querySelector(".dz-file").textContent = file.name;
        hint.textContent = (file.size / 1048576).toFixed(1) + " MB — clique para trocar";
        if (err) err.style.display = "none";
      }

      function showError(msg) {
        dz.classList.remove("filled");
        text.textContent = emptyText;
        if (err) { err.textContent = msg; err.style.display = "block"; }
      }

      input.addEventListener("change", function () {
        if (input.files.length) showFile(input.files[0]);
      });

      ["dragenter", "dragover"].forEach(function (ev) {
        dz.addEventListener(ev, function (e) {
          e.preventDefault(); dz.classList.add("dragover");
        });
      });
      ["dragleave", "drop"].forEach(function (ev) {
        dz.addEventListener(ev, function (e) {
          e.preventDefault(); dz.classList.remove("dragover");
        });
      });
      dz.addEventListener("drop", function (e) {
        var files = e.dataTransfer.files;
        if (!files.length) return;
        if (!accepted(files[0].name)) {
          showError("Formato não aceito. Use: " + input.getAttribute("accept"));
          input.value = "";
          return;
        }
        var dt = new DataTransfer();
        dt.items.add(files[0]);
        input.files = dt.files;
        showFile(files[0]);
      });
    });
  }

  function initFilters(root) {
    root.querySelectorAll("input.table-filter:not([data-tf-ready])").forEach(function (inp) {
      inp.setAttribute("data-tf-ready", "1");
      inp.addEventListener("input", function () {
        var card = inp.closest(".card");
        var q = inp.value.trim().toLowerCase();
        card.querySelectorAll("tbody tr").forEach(function (tr) {
          tr.style.display = tr.textContent.toLowerCase().indexOf(q) === -1 ? "none" : "";
        });
      });
    });
  }

  function initAll(root) { initDropzones(root); initFilters(root); }

  document.addEventListener("DOMContentLoaded", function () { initAll(document); });
  document.body && initAll(document);
  document.addEventListener("htmx:afterSwap", function (e) { initAll(e.target.parentElement || document); });
})();
```

- [ ] **Step 6: Reescrever `ocorrencias.html`**

Conteúdo completo do arquivo:

```html
{% extends "app_base.html" %}
{% block title %}Ocorrências — Processador de Ocorrências{% endblock %}
{% block content %}
<div class="page-header">
    <div class="crumb">Início / <b>Ocorrências</b></div>
    <h1>Ocorrências</h1>
    <p>Cruze o PDF de jornada com a planilha de pedido: o sistema conta as
       ocorrências de cada RE e preenche a coluna MOTIVO automaticamente.</p>
</div>
<div class="page-grid">
    <div class="stack">
        <div class="form-card">
            {% if error %}<div class="alert alert-error">{{ error }}</div>{% endif %}
            <form method="post" action="/app/ocorrencias" enctype="multipart/form-data">
                <input type="hidden" name="csrf_token" value="{{ csrf_token }}">

                <label>PDF de jornada</label>
                <div>
                    <div class="dropzone" data-tour="oc-pdf">
                        <input type="file" name="pdf" accept=".pdf" required>
                        <div class="dz-icon">⇪</div>
                        <div class="dz-text">Arraste o PDF aqui ou clique para escolher</div>
                        <div class="dz-hint">Relatório de jornada de trabalho (.pdf, máx. 50 MB)</div>
                    </div>
                    <div class="dz-error"></div>
                </div>

                <label>Planilha de pedido</label>
                <div>
                    <div class="dropzone" data-tour="oc-xlsx">
                        <input type="file" name="xlsx" accept=".xlsx,.xls" required>
                        <div class="dz-icon">⇪</div>
                        <div class="dz-text">Arraste a planilha aqui ou clique para escolher</div>
                        <div class="dz-hint">Excel com as colunas Folha RE e MOTIVO (.xlsx/.xls)</div>
                    </div>
                    <div class="dz-error"></div>
                </div>

                <label>Códigos de ocorrência
                    <a href="/app/codigos" class="meta" style="font-weight:400;margin-left:8px">gerenciar códigos →</a>
                </label>
                <div class="pill-grid" data-tour="oc-codigos">
                    {% for c in codigos_disponiveis %}
                    <label class="pill" title="{{ c.descricao }}">
                        <input type="checkbox" name="codigos" value="{{ c.codigo }}" checked>
                        <span>{{ c.codigo }}</span>
                    </label>
                    {% endfor %}
                </div>

                <div class="form-actions">
                    <button type="submit" data-tour="oc-processar" class="btn btn-primary" style="width:100%;justify-content:center">
                        Processar
                    </button>
                </div>
            </form>
        </div>

        {% if recentes %}
        <div class="card">
            <div class="card-title">Processamentos recentes</div>
            <table>
                <tbody>
                    {% for e in recentes %}
                    <tr>
                        <td class="meta">{{ e.created_at[:16].replace('T', ' ') }}</td>
                        <td>{{ e.input_names | join('; ') }}</td>
                        <td><span class="chip {{ 'chip-ok' if e.status == 'sucesso' else 'chip-err' }}">{{ e.status }}</span></td>
                        <td style="text-align:right">
                            {% if e.job_id %}<a href="/app/jobs/{{ e.job_id }}" class="btn btn-sm btn-ghost">Abrir</a>{% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}
    </div>

    <aside>
        <div class="aside-card" data-tour="oc-como-funciona">
            <h3>Como funciona</h3>
            <ol class="steps">
                <li>Envie o PDF de jornada e a planilha de pedido.</li>
                <li>O sistema lê o PDF duas vezes e compara os resultados.</li>
                <li>Se as leituras divergirem, você decide o valor certo numa tela de revisão.</li>
                <li>Baixe a planilha com a coluna MOTIVO preenchida.</li>
            </ol>
        </div>
        <div class="aside-card" data-tour="oc-requisitos">
            <h3>Requisitos do arquivo</h3>
            <ul class="req-list">
                <li>A planilha precisa das colunas <code>Folha RE</code> e <code>MOTIVO</code> na primeira linha.</li>
                <li>Formatos aceitos: <code>.xlsx</code> e <code>.xls</code>; PDF de jornada em <code>.pdf</code>.</li>
                <li>Tamanho máximo por arquivo: 50 MB.</li>
                <li>REs que estão no PDF mas não na planilha saem na aba <code>Não localizados</code> do resultado.</li>
            </ul>
        </div>
    </aside>
</div>
{% endblock %}
```

- [ ] **Step 7: Reescrever `vt_caixa.html`**

Conteúdo completo:

```html
{% extends "app_base.html" %}
{% block title %}VT-Caixa — Processador de Ocorrências{% endblock %}
{% block content %}
<div class="page-header">
    <div class="crumb">Início / <b>VT-Caixa</b></div>
    <h1>VT-Caixa</h1>
    <p>Gere o arquivo CSV de benefícios de Vale-Transporte cruzando o relatório
       Nautilus com o cadastro funcional.</p>
</div>
<div class="page-grid">
    <div class="stack">
        <div class="form-card">
            {% if error %}<div class="alert alert-error">{{ error }}</div>{% endif %}
            <form method="post" action="/app/vt-caixa" enctype="multipart/form-data">
                <input type="hidden" name="csrf_token" value="{{ csrf_token }}">

                <label>Fonte (relatório Nautilus)</label>
                <div>
                    <div class="dropzone" data-tour="vt-fonte">
                        <input type="file" name="fonte" accept=".pdf,.xlsx,.xls" required>
                        <div class="dz-icon">⇪</div>
                        <div class="dz-text">Arraste o arquivo aqui ou clique para escolher</div>
                        <div class="dz-hint">PDF ou Excel do Nautilus (máx. 50 MB)</div>
                    </div>
                    <div class="dz-error"></div>
                </div>

                <label>Cadastro funcional</label>
                <div>
                    <div class="dropzone" data-tour="vt-cadastral">
                        <input type="file" name="cadastral" accept=".xlsx,.xls" required>
                        <div class="dz-icon">⇪</div>
                        <div class="dz-text">Arraste a planilha aqui ou clique para escolher</div>
                        <div class="dz-hint">Excel cadastral (.xlsx/.xls)</div>
                    </div>
                    <div class="dz-error"></div>
                </div>

                <div class="form-actions">
                    <button type="submit" data-tour="vt-processar" class="btn btn-primary" style="width:100%;justify-content:center">
                        Processar
                    </button>
                </div>
            </form>
        </div>

        {% if recentes %}
        <div class="card">
            <div class="card-title">Processamentos recentes</div>
            <table>
                <tbody>
                    {% for e in recentes %}
                    <tr>
                        <td class="meta">{{ e.created_at[:16].replace('T', ' ') }}</td>
                        <td>{{ e.input_names | join('; ') }}</td>
                        <td><span class="chip {{ 'chip-ok' if e.status == 'sucesso' else 'chip-err' }}">{{ e.status }}</span></td>
                        <td style="text-align:right">
                            {% if e.job_id %}<a href="/app/jobs/{{ e.job_id }}" class="btn btn-sm btn-ghost">Abrir</a>{% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}
    </div>

    <aside>
        <div class="aside-card" data-tour="vt-como-funciona">
            <h3>Como funciona</h3>
            <ol class="steps">
                <li>Envie a fonte Nautilus (PDF ou Excel) e o cadastro funcional.</li>
                <li>O sistema cruza matrículas, aplica códigos de benefício e substituições de departamento.</li>
                <li>Baixe o CSV pronto (codificação latin-1) para importar no banco.</li>
            </ol>
        </div>
        <div class="aside-card" data-tour="vt-requisitos">
            <h3>Requisitos do arquivo</h3>
            <ul class="req-list">
                <li>O cadastro precisa da coluna de matrícula (<code>Cód Epr</code>) e dos dados pessoais (CPF, RG, endereço, nome da mãe).</li>
                <li>Fonte: <code>.pdf</code>, <code>.xlsx</code> ou <code>.xls</code>; cadastro: <code>.xlsx</code>/<code>.xls</code>.</li>
                <li>Tamanho máximo por arquivo: 50 MB.</li>
                <li>Operadoras sem código cadastrado saem com o nome original — cadastre o código na página <a href="/app/codigos">Códigos</a>.</li>
            </ul>
        </div>
    </aside>
</div>
{% endblock %}
```

- [ ] **Step 8: Atualizar `historico.html` (chips) e fragmentos de códigos (título/busca)**

Em `historico.html`: adicionar `<div class="crumb">Início / <b>Histórico</b></div>`
antes do `<h1>`; na coluna Resultado/status da tabela, envolver o status num chip.
Trocar a célula de resultado atual por:

```html
                <td>
                    <span class="chip {{ 'chip-ok' if e.status == 'sucesso' else 'chip-err' }}">{{ e.status }}</span>
                    <span class="meta" style="margin-left:8px">
                        {% if e.counts.matched is defined %}{{ e.counts.matched }} correspondências
                        {% elif e.counts.total_ok is defined %}{{ e.counts.total_ok }} registros{% endif %}
                    </span>
                </td>
```

Nos três fragmentos de códigos (`codigos_beneficio_fragment.html`,
`codigos_depart_fragment.html`, `codigos_ocorrencia_fragment.html`):
1. Trocar o `div` de título com style inline por `<div class="card-title">…</div>`.
2. Trocar o style inline do form de adicionar por `class="card-add-form"`.
3. Logo após o form de adicionar, inserir a busca:

```html
    <input type="text" class="table-filter" placeholder="Filtrar...">
```

Em `codigos.html`, adicionar o crumb: `<div class="crumb">Início / <b>Códigos</b></div>`.
Nas páginas ocorrências/vt-caixa os crumbs já estão nos Steps 6–7.

- [ ] **Step 9: Rodar os testes e a suíte**

Run: `python -m pytest tests/test_routes_app.py -v` → PASS
Run: `python -m pytest tests -q` → PASS
(Se algum teste antigo asserta HTML que mudou — ex.: `class="check"` nos códigos
do form — ajustar o teste para o HTML novo, mantendo o comportamento verificado.)

- [ ] **Step 10: Verificação manual no navegador**

Com `uvicorn app.main:app --reload` (de `license-server/`):
1. Ocorrências: dropzones respondem a clique e drag (arquivo errado solto → erro inline; certo → nome+tamanho e borda verde); pílulas alternam ao clique; aside com "Como funciona"/"Requisitos"; recentes aparecem após um processamento.
2. VT-Caixa: idem.
3. Códigos: 3 cards no grid; busca filtra linhas em cada card; adicionar/excluir continuam funcionando (inclusive após swap HTMX a busca segue funcionando).
4. Histórico: chips coloridos.
5. Janela estreita (< 1100px): grid empilha; < 960px: cards de códigos empilham.
6. Conferir que nada do tour quebrou (âncoras preservadas).

- [ ] **Step 11: Commit**

```bash
git add license-server/app
git commit -m "feat(web): layout full-width com dropzones, requisitos, recentes e chips"
```

---

### Task 7: Tutorial 2.0 — tema próprio, welcome modal e conteúdo didático

**Files:**
- Create: `license-server/app/static/tour-theme.css`
- Rewrite: `license-server/app/static/tour.js`
- Modify: `license-server/app/templates/app_base.html` (link do CSS novo)
- Test: `license-server/tests/test_routes_app.py` (acrescentar)

**Interfaces:**
- Consumes: anchors `data-tour` (existentes + `oc-requisitos`, `oc-como-funciona`, `vt-requisitos`, `cod-ocorrencia`, `cod-add-ocorrencia` criados nas Tasks 4/6); `POST /app/tutorial/seen`; `window.TOUR = {seen, csrf}` (já emitido pelo `app_base.html`).
- Produces: `window.startTour(segIndex)` (mesmo contrato de hoje — o botão da sidebar não muda).

- [ ] **Step 1: Escrever os testes** (acrescentar em `license-server/tests/test_routes_app.py`)

```python
def test_base_inclui_tour_theme(logged_client):
    c, _ = logged_client
    r = c.get("/app/ocorrencias")
    assert 'href="/static/tour-theme.css"' in r.text


def test_tour_js_tem_welcome_e_requisitos():
    from pathlib import Path
    js = Path("app/static/tour.js").read_text(encoding="utf-8")
    assert "Fazer o tour" in js
    assert "Agora não" in js
    assert "Folha RE" in js          # conteúdo didático
    assert "MOTIVO" in js
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_routes_app.py -v`
Expected: FAIL

- [ ] **Step 3: Criar `license-server/app/static/tour-theme.css`**

```css
/* Tema do tutorial — sobrepõe o driver.css padrão (carregar DEPOIS dele). */
.driver-popover{
  background:#171a21;color:#c9d4e6;
  border:1px solid #2b303a;border-radius:14px;
  box-shadow:0 12px 40px rgba(0,0,0,.55),0 0 0 1px rgba(59,130,246,.15);
  font-family:'Inter','Segoe UI',system-ui,sans-serif;
  max-width:360px;padding:18px 20px 14px;
}
.driver-popover-title{
  color:#f0f6fc;font-size:15px;font-weight:700;letter-spacing:-.01em;
}
.driver-popover-description{
  color:#c9d4e6;font-size:13.5px;line-height:1.6;margin-top:6px;
}
.driver-popover-description code{
  font-family:'JetBrains Mono',Consolas,monospace;font-size:11.5px;
  background:#1f242d;border:1px solid #2b303a;border-radius:5px;
  padding:1px 6px;color:#e3b341;
}
.driver-popover-description ul{margin:8px 0 0 18px;display:flex;flex-direction:column;gap:5px}
.tour-warn{
  margin-top:10px;padding:9px 12px;border-radius:8px;font-size:12.5px;
  background:rgba(227,179,65,.1);border:1px solid rgba(227,179,65,.35);color:#e3b341;
}
.driver-popover-progress-text{color:#8b95a7;font-size:12px}
.driver-popover-footer button{
  font-family:'Inter','Segoe UI',system-ui,sans-serif;
  border-radius:9px;padding:7px 14px;font-size:12.5px;font-weight:600;
  border:1px solid #2b303a;background:#1f242d;color:#c9d4e6;text-shadow:none;
}
.driver-popover-footer button:hover{background:#2b303a;color:#f0f6fc}
.driver-popover-footer .driver-popover-next-btn{
  background:linear-gradient(135deg,#3b82f6,#22c55e);border:none;color:#fff;
}
.driver-popover-footer .driver-popover-next-btn:hover{opacity:.92}
.driver-popover-close-btn{color:#8b95a7}
.driver-popover-close-btn:hover{color:#f0f6fc}
.driver-popover-arrow-side-left.driver-popover-arrow{border-left-color:#171a21}
.driver-popover-arrow-side-right.driver-popover-arrow{border-right-color:#171a21}
.driver-popover-arrow-side-top.driver-popover-arrow{border-top-color:#171a21}
.driver-popover-arrow-side-bottom.driver-popover-arrow{border-bottom-color:#171a21}
.driver-overlay{opacity:.78}

/* welcome modal (primeiro passo, sem elemento) */
.tour-welcome.driver-popover{max-width:440px;text-align:center;padding:28px 28px 20px}
.tour-welcome .driver-popover-title{font-size:19px}
.tour-welcome .driver-popover-description{font-size:14px}
.tour-welcome .driver-popover-footer{justify-content:center;gap:10px}
.tour-skip-btn{
  border:1px solid #2b303a !important;background:transparent !important;color:#8b95a7 !important;
}
.tour-skip-btn:hover{color:#c9d4e6 !important}
```

Em `app_base.html`, no `<head>`, logo APÓS `<link rel="stylesheet" href="/static/driver.css">`:

```html
<link rel="stylesheet" href="/static/tour-theme.css">
```

- [ ] **Step 4: Reescrever `license-server/app/static/tour.js`**

Conteúdo completo:

```javascript
/* Tour guiado 2.0 — segmentos por página ancorados em [data-tour].
   Auto-inicia no primeiro acesso (window.TOUR.seen === false) com um
   welcome modal ("Fazer o tour" / "Agora não"); o botão "Ver tutorial"
   chama startTour(0). Entre páginas: ?tour=<indice do segmento>. */
(function () {
  const driver = window.driver.js.driver;

  const SEGMENTS = [
    {
      page: "/app/ocorrencias",
      steps: [
        {
          popover: {
            title: "Bem-vindo ao Processador de Ocorrências",
            description:
              "Em ~2 minutos você vê tudo que o sistema faz: Ocorrências, " +
              "VT-Caixa, Códigos e Histórico.<br><br>Você pode rever este " +
              "tour quando quiser no botão <strong>Ver tutorial</strong> da barra lateral.",
            popoverClass: "tour-welcome",
          },
          welcome: true,
        },
        { element: '[data-tour="oc-pdf"]', popover: { title: "1. PDF de jornada",
            description: "Arraste (ou clique e escolha) o relatório PDF de jornada. " +
              "É dele que o sistema extrai as ocorrências de cada RE." } },
        { element: '[data-tour="oc-xlsx"]', popover: { title: "2. Planilha de pedido",
            description: "Esta é a planilha que será preenchida." +
              '<div class="tour-warn">Ela <strong>precisa ter</strong> as colunas ' +
              "<code>Folha RE</code> e <code>MOTIVO</code> na primeira linha — sem elas " +
              "o processamento falha.</div>" } },
        { element: '[data-tour="oc-codigos"]', popover: { title: "3. Códigos de ocorrência",
            description: "Clique nas pílulas para escolher quais códigos entram no MOTIVO " +
              "(FA = Faltas, AT = Atestado...).<br><br>Precisa de um código que não existe? " +
              "Crie na página <strong>Códigos</strong> — ele aparece aqui na hora." } },
        { element: '[data-tour="oc-processar"]', popover: { title: "4. Processar",
            description: "O arquivo entra na fila e uma barra mostra o progresso.<ul>" +
              "<li>Leituras iguais → resultado sai direto.</li>" +
              "<li>Leituras divergentes → você revisa cada diferença antes de gerar.</li>" +
              "</ul>O download fica disponível por 7 dias." } },
        { element: '[data-tour="oc-requisitos"]', popover: { title: "Requisitos sempre à mão",
            description: "Este painel resume o que cada arquivo precisa ter. Os REs do PDF " +
              "que não estiverem na planilha saem na aba <code>Não localizados</code> do resultado." } },
      ],
    },
    {
      page: "/app/vt-caixa",
      steps: [
        { element: '[data-tour="nav-vtcaixa"]', popover: { title: "VT-Caixa",
            description: "Gera o CSV de benefícios de Vale-Transporte para importação no banco." } },
        { element: '[data-tour="vt-fonte"]', popover: { title: "Fonte Nautilus",
            description: "O relatório Nautilus, em <code>.pdf</code> ou Excel." } },
        { element: '[data-tour="vt-cadastral"]', popover: { title: "Cadastro funcional",
            description: "Excel com matrícula (<code>Cód Epr</code>), CPF, RG, endereço e " +
              "nome da mãe — é de onde saem os dados pessoais do CSV." } },
        { element: '[data-tour="vt-processar"]', popover: { title: "Processar",
            description: "Ao concluir, baixe o CSV (codificação latin-1) pronto para o banco." +
              '<div class="tour-warn">Operadora sem código cadastrado sai com o nome original — ' +
              "cadastre o código na página Códigos.</div>" } },
      ],
    },
    {
      page: "/app/codigos",
      steps: [
        { element: '[data-tour="nav-codigos"]', popover: { title: "Códigos",
            description: "Todas as tabelas de referência do sistema, com busca e cópia num clique." } },
        { element: '[data-tour="cod-ocorrencia"]', popover: { title: "Códigos de Ocorrência",
            description: "Os códigos que aparecem no formulário de Ocorrências. Além dos 11 " +
              "embutidos, você pode criar os seus." } },
        { element: '[data-tour="cod-add-ocorrencia"]', popover: { title: "Criar um código",
            description: "Informe o código (até 4 letras), a descrição e se ele leva quantidade " +
              "no MOTIVO (ex.: <code>2 FR</code>) ou não (como AP/LM/FE).<br><br>Vale para todos " +
              "os usuários imediatamente." } },
        { element: '[data-tour="cod-beneficio"]', popover: { title: "Operadora → Código de Benefício",
            description: "Usados no VT-Caixa: quando a operadora (e o valor, se definido) casa, " +
              "o CSV sai com o código no lugar do nome. Personalizados têm prioridade sobre os embutidos." } },
        { element: '[data-tour="cod-depart"]', popover: { title: "Substituições de Departamento",
            description: "Renomeiam departamentos no CSV do VT-Caixa (ex.: nomes de contrato → nomes curtos)." } },
      ],
    },
    {
      page: "/app/historico",
      steps: [
        { element: '[data-tour="nav-historico"]', popover: { title: "Histórico",
            description: "Cada processamento seu fica registrado aqui, com status e link para reabrir." } },
        { element: '[data-tour="hist-filtros"]', popover: { title: "Busca e filtro",
            description: "Procure por nome de arquivo ou filtre por sucesso/erro." } },
        { element: '[data-tour="hist-export"]', popover: { title: "Exportar CSV",
            description: "Baixa o histórico filtrado em CSV." } },
        { element: '[data-tour="btn-tutorial"]', popover: { title: "É isso!",
            description: "Sempre que precisar, clique aqui para rever este tour do início. Bom trabalho! 🎉" } },
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
    const steps = seg.steps.filter(
      (s) => !s.element || document.querySelector(s.element)
    );
    if (!steps.length) { nextSegment(idx); return; }
    const d = driver({
      showProgress: true,
      progressText: "{{current}} de {{total}}",
      nextBtnText: "Próximo",
      prevBtnText: "Anterior",
      doneBtnText: idx === SEGMENTS.length - 1 ? "Concluir" : "Continuar →",
      steps: steps,
      onPopoverRender: (popover, opts) => {
        const stepDef = steps[opts.state.activeIndex];
        if (stepDef && stepDef.welcome) {
          // welcome modal: renomeia o next e adiciona "Agora não"
          popover.nextButton.innerText = "Fazer o tour";
          const skip = document.createElement("button");
          skip.innerText = "Agora não";
          skip.className = "tour-skip-btn";
          skip.addEventListener("click", () => { d.destroy(); markSeen(); });
          popover.footerButtons.appendChild(skip);
        }
      },
      onDestroyed: () => {
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
      window.startTour(0);
    }
  });
})();
```

Notas para o executor:
- driver.js 1.x renderiza HTML em `description` por padrão (`innerHTML`).
- `onPopoverRender(popover, { config, state })`: `popover.nextButton` e
  `popover.footerButtons` são elementos DOM reais — API pública do driver 1.3.
- O passo welcome existe só no segmento 0; nos reinícios via botão ele aparece
  de novo (comportamento desejado: dá a opção de sair na hora).

- [ ] **Step 5: Rodar os testes e a suíte**

Run: `python -m pytest tests/test_routes_app.py -v` → PASS
Run: `python -m pytest tests -q` → PASS

- [ ] **Step 6: Verificação manual no navegador** (obrigatória)

1. Usuário novo (criar no `/admin/users`, logar): welcome modal centralizado
   com "Fazer o tour" e "Agora não"; visual escuro do app (sem popover branco).
2. "Agora não" → fecha, recarrega, não volta a abrir.
3. Outro usuário novo → "Fazer o tour" → percorre os 4 segmentos; conferir os
   textos com `<code>`/avisos amarelos renderizados; "Concluir" no fim marca visto.
4. Botão "Ver tutorial" repete do início.
5. Fechar no X no meio do segmento 2 → não reabre ao navegar.
6. Passo do welcome: barra "1 de N" visível e botões estilizados.

- [ ] **Step 7: Commit**

```bash
git add license-server/app/static license-server/app/templates/app_base.html license-server/tests
git commit -m "feat(web): tutorial 2.0 com tema proprio, welcome modal e conteudo didatico"
```

---

## Self-review (executado na escrita do plano)

- **Cobertura da spec:** tabela+CRUD ocorrência (T1), core `config_extras` com ordem/quantidade (T2), worker injeta (T3), seção nova na página Códigos com anchors (T4), form dinâmico + POST aceita personalizado (T5), layout full-width/dropzones/pílulas/requisitos (com coluna `Folha RE`/`MOTIVO`)/recentes/chips/busca/favicon/crumb + frontend-design skill (T6), tour tema+welcome+conteúdo didático (T7). Erros: duplicata/CSRF nos fragmentos (T4), extensão errada na dropzone (T6 app.js), passos ausentes pulados (T7 filter). ✔
- **Placeholders:** nenhum; todos os steps de código têm o código completo. ✔
- **Consistência:** `occurrence_config` → `config_extras` (T1→T2→T3); `codigos_disponiveis` (T5→T6); classes CSS de T6 usadas em T4 (`card-title`/`card-add-form` — nota de ordem incluída no T4) e T7 (`tour-warn`); anchors `data-tour` de T4/T6 referenciados em T7; `window.TOUR`/`startTour` inalterados para o botão existente. ✔
- **Ordem de execução:** T1→T2→T3→T4→T5→T6→T7 (T4 pode rodar antes de T6 — o fragmento usa classes que só ganham estilo na T6, sem quebrar testes).
