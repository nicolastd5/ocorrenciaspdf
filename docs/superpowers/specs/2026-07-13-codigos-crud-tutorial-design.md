# Design — Códigos personalizados, remoção de Dias/Qt e tutorial guiado

**Data:** 2026-07-13
**Status:** Aprovado pelo usuário
**Base:** web app em `license-server/` (spec 2026-07-13-web-migration-design.md, já implementada)

## Objetivo

1. Usuários criam e excluem códigos de benefício (operadora → código) e
   substituições de departamento pela própria página **Códigos**, mantendo os
   embutidos; os personalizados valem também no **processamento do VT-Caixa**.
2. Remover por completo os campos "Dias no mês" e "Colunas Qt" do fluxo de
   Ocorrências (form, rota, job e core).
3. Tutorial interativo (tour com balões sobre os elementos reais) no primeiro
   acesso, com botão fixo para repetir a qualquer momento.

## Decisões tomadas

| Tema | Decisão |
|---|---|
| Escopo dos personalizados | Globais — qualquer usuário logado cria/exclui; todos veem e usam |
| Efeito | Valem no processamento do VT-Caixa, não só na página de referência |
| Embutidos | Intocados (constantes do core); sem botão de excluir na UI |
| Precedência | Personalizado é consultado ANTES do embutido na resolução |
| Duplicatas | Bloqueio de duplicata exata (mesma operadora+valor ou mesmo original) |
| Dias no mês / Colunas Qt | Remoção completa, inclusive a lógica no core |
| Tutorial | Tour interativo com driver.js vendorizado (sem CDN) |
| Primeiro acesso | Auto-inicia 1× por usuário (coluna `tutorial_seen` em `users`) |
| Repetição | Botão "? Ver tutorial" fixo na barra lateral |

## 1. Códigos e departamentos personalizados

### Banco (SQLite, mesmo `licenses.db`)

```sql
CREATE TABLE IF NOT EXISTS custom_benefit_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operadora TEXT NOT NULL,            -- substring uppercase, como nos embutidos
    valor_unitario TEXT,                -- NULL = qualquer valor
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

### Módulo `app/ref_codes.py`

- `list_benefit_codes(db_path) -> list[dict]` / `list_depart_subs(db_path) -> list[dict]`
- `add_benefit_code(db_path, user_id, operadora, valor_unitario, codigo) -> int`
  — normaliza operadora para uppercase/trim; `valor_unitario` vazio → NULL;
  ValueError se (operadora, valor_unitario) já existir (custom) ou campos vazios
- `add_depart_sub(db_path, user_id, original, substituto) -> int`
  — ValueError se `original` já existir (custom) ou campos vazios
- `delete_benefit_code(db_path, code_id)` / `delete_depart_sub(db_path, sub_id)`
- `benefit_tuples(db_path) -> list[tuple]` — `(operadora, valor_unitario|None, codigo)`
  no formato de `_CODIGOS_BENEFICIO`, para injetar no core
- `depart_dict(db_path) -> dict` — no formato de `_DEPART_MAP`

### Core (`core/vt_caixa_processador.py`)

- `processar(..., codigos_extras=None, depart_extras=None)`
- `_resolver_codigo_beneficio(administradora, valor_unitario, extras=None)`:
  percorre `extras` primeiro, depois `_CODIGOS_BENEFICIO` (precedência custom)
- Substituição de departamento usa `{**self._DEPART_MAP, **(depart_extras or {})}`
- Sem `codigos_extras`/`depart_extras` o comportamento atual não muda em nada

### Worker

`run_vt_caixa` lê `ref_codes.benefit_tuples`/`depart_dict` do banco no momento
do job e passa a `processar`. (Snapshot no início do job; alterações durante o
job não o afetam.)

### UI — página `/app/codigos`

- Cada seção (Benefícios, Departamentos) ganha: form "Adicionar" no topo
  (inline, POST via HTMX, re-renderiza a seção) e, nas linhas personalizadas,
  selo "personalizado" + botão excluir (POST HTMX com confirmação `hx-confirm`).
- Embutidos aparecem primeiro? Não — lista única ordenada por operadora/original,
  personalizados identificados pelo selo. Botão copiar continua em todas as linhas.
- Rotas (todas com `require_user` + CSRF):
  - `GET  /app/codigos` — página completa (embutidos + personalizados)
  - `POST /app/codigos/beneficio` — adiciona; retorna fragmento da seção
  - `POST /app/codigos/beneficio/{id}/excluir` — remove; retorna fragmento
  - `POST /app/codigos/departamento` — adiciona; retorna fragmento
  - `POST /app/codigos/departamento/{id}/excluir` — remove; retorna fragmento
- Erros de validação (duplicata, campo vazio) aparecem no próprio fragmento.

## 2. Remoção de Dias no mês / Colunas Qt

Remover de ponta a ponta:

- `ocorrencias.html`: campos "Dias no mês" e "Colunas Qt".
- `routes_jobs.ocorrencias_submit`: parâmetros `dias_mes` e `colunas_qt`;
  params do job perdem `dias_mes`/`colunas_qt_sel`.
- `worker_tasks._processar_final`: deixa de passar `dias_mes`/`colunas_qt_sel`.
- `core/processador.py`: remove parâmetros `dias_mes`/`colunas_qt_sel` de
  `processar`, as constantes `COLUNAS_QT`, `VU_VT_HEADER`, `CODIGOS_DEDUZIR`
  e toda a lógica de detecção/preenchimento/dedução das colunas Qt VA/VR/VT
  e Vu VT.
- Testes que usam esses parâmetros: ajustar/remover.
- Jobs antigos no banco com `dias_mes` nos params: sem migração — o worker
  simplesmente ignora chaves desconhecidas (leitura via `.get` não existe mais).

## 3. Tutorial interativo

### Biblioteca

driver.js (MIT) vendorizado: `app/static/driver.js.iife.js` e
`app/static/driver.css` (download do release, sem CDN em runtime).

### Estado por usuário

- Coluna nova em `users`: `tutorial_seen INTEGER NOT NULL DEFAULT 0`.
  Migração: `init_db` executa `ALTER TABLE users ADD COLUMN ...` dentro de
  try/except (SQLite não tem IF NOT EXISTS para coluna).
- `POST /app/tutorial/seen` (require_user, CSRF) marca `tutorial_seen = 1`.
- O template base recebe `tutorial_seen` (via contexto) e, quando 0, o JS
  auto-inicia o tour completo após o load da página.

### Tour (`app/static/tour.js`)

- Passos ancorados em atributos `data-tour="..."` adicionados aos templates
  (ex.: `data-tour="nav-ocorrencias"`, `data-tour="oc-upload-pdf"`).
- Roteiro completo (auto-start e botão "tour completo"):
  1. Boas-vindas + visão geral da barra lateral
  2. Ocorrências: upload do PDF de jornada, upload da planilha de pedido,
     seleção de códigos, botão Processar, o que esperar (progresso →
     possível revisão de divergências → download)
  3. VT-Caixa: fonte Nautilus (PDF/Excel), Excel cadastral, CSV de saída
  4. Códigos: consultar/copiar, adicionar personalizado, excluir
  5. Histórico: busca, filtro por status, exportar CSV
  6. Botão "? Ver tutorial" (como repetir)
- Passos de páginas que não estão abertas usam navegação: o tour completo é
  dividido em segmentos por página; ao fim do segmento, o tour navega para a
  próxima página com `?tour=continuar` na URL e o JS retoma do segmento dela.
  (driver.js não atravessa page loads sozinho; o segmento ativo vai na query.)
- Ao concluir ou fechar (skip) o tour completo iniciado por primeiro acesso:
  POST `tutorial/seen`. Fechar no meio também marca (não re-incomoda).
- Botão lateral "? Ver tutorial": reinicia o tour completo do começo
  (navegando para `/app/ocorrencias?tour=continuar&seg=0`).

## Tratamento de erros

- CRUD: duplicata/campos vazios → mensagem no fragmento (400), nada é gravado.
- Tour: se um `data-tour` não existir na página (elemento removido no futuro),
  o passo é pulado silenciosamente (comportamento padrão do driver.js com
  elemento ausente — verificado no plano com teste manual).
- `tutorial/seen` idempotente.

## Testes

- `tests/test_ref_codes.py`: CRUD, normalização, duplicata, `benefit_tuples`/
  `depart_dict`.
- `tests/core/test_vt_caixa.py`: precedência extras > embutido em
  `_resolver_codigo_beneficio`; depart_extras sobrepõe `_DEPART_MAP`;
  sem extras, comportamento idêntico.
- `tests/test_worker_tasks.py`: `run_vt_caixa` injeta os extras lidos do banco.
- `tests/test_routes_codigos.py`: páginas/fragmentos, permissão (sem login →
  303), CSRF, exclusão.
- `tests/test_routes_jobs.py`: upload de ocorrências sem `dias_mes`/`colunas_qt`.
- `tests/test_routes_app.py`: `POST /app/tutorial/seen` marca a coluna;
  página inclui `data-tour` e o script do tour.

## Fora de escopo

- Edição inline de entradas personalizadas (excluir + recriar cobre).
- Permissões diferenciadas (todo usuário logado gerencia personalizados).
- Tutorial em vídeo ou por página isolada além dos segmentos definidos.
