# Design — Códigos de ocorrência personalizados, layout de site e tutorial 2.0

**Data:** 2026-07-14
**Status:** Aprovado pelo usuário
**Base:** web app em `license-server/` com CRUD de benefícios/departamentos e
tour v1 já implementados (HEAD `894f698`).

## Objetivo

1. Usuários criam/excluem **códigos de ocorrência** (ex.: "FR") que aparecem
   no form de Ocorrências e valem no processamento (MOTIVO), mantendo os 11
   embutidos.
2. **Layout** deixa de parecer app desktop portado: conteúdo em tela cheia,
   dropzones de arrastar-e-soltar, painel "como funciona"/requisitos ao lado
   dos forms, processamentos recentes, pílulas de código.
3. **Tutorial 2.0**: visual próprio (tema escuro do app no driver.js),
   conteúdo didático com requisitos concretos (colunas `Folha RE` e `MOTIVO`
   etc.), boas-vindas em modal com "Fazer o tour"/"Agora não".

## Decisões tomadas

| Tema | Decisão |
|---|---|
| Campos do código de ocorrência | codigo + descricao + `com_quantidade` (0/1) |
| Gestão | Seção nova na página Códigos; form de Ocorrências mostra embutidos+personalizados como checkboxes/pílulas (personalizados marcados por padrão) com atalho "gerenciar códigos" |
| Escopo | Global (como benefícios/departamentos); qualquer usuário logado cria/exclui |
| Duplicatas | Bloqueadas contra personalizados existentes E contra os 11 embutidos |
| Embutidos | Intocados; sem excluir; ordem atual (`ORDEM`) preservada no MOTIVO |
| Ordem no MOTIVO | Embutidos na `ORDEM` primeiro, personalizados em ordem alfabética depois |
| Layout | Sidebar mantida; conteúdo full-width com grid; tema escuro atual |
| Tutorial | Mecânica de segmentos mantida; tema e conteúdo reescritos; welcome modal |

## 1. Códigos de ocorrência personalizados

### Banco

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

### `app/ref_codes.py` (acréscimos, mesmo padrão do existente)

- `list_occurrence_codes(db_path) -> list[dict]` (ordenado por codigo)
- `add_occurrence_code(db_path, user_id, codigo, descricao, com_quantidade: bool) -> int`
  — codigo normalizado `strip().upper()`, máx. 4 caracteres; ValueError se
  vazio, se já existir personalizado igual ou se colidir com um dos 11
  embutidos (`ProcessadorOcorrencias.TODOS_CODIGOS`)
- `delete_occurrence_code(db_path, code_id) -> None`
- `occurrence_config(db_path) -> list[dict]` — `[{"codigo": "FR", "com_quantidade": True}, ...]`
  em ordem alfabética, para injetar no core

### Core (`core/processador.py`)

- `montar_motivo(self, ocorrencias, codigos_selecionados, config_extras=None)`:
  ordem = `self.ORDEM` + `[c["codigo"] for c in config_extras]`;
  sem-quantidade = `self.SEM_QUANTIDADE` + códigos extras com
  `com_quantidade == False`.
- `processar(..., config_extras=None)` repassa a `montar_motivo` (nas duas
  chamadas: atualizados e não encontrados).
- Extração não muda (já aceita qualquer código em `codigos_alvo`).

### Worker e rotas

- `run_ocorrencias` e `finalizar_ocorrencias`/`_processar_final` leem
  `ref_codes.occurrence_config(db_path)` e passam `config_extras`.
- `GET /app/ocorrencias` passa ao template a lista de códigos: embutidos
  (`TODOS_CODIGOS` com `DESCRICOES`) + personalizados (com descrição), todos
  marcados por padrão.
- `POST /app/ocorrencias` continua aceitando `codigos: list[str]` (sem
  validação de pertencimento — códigos desconhecidos apenas não casam nada).

### Página Códigos

Terceira seção "Códigos de Ocorrência" (fragmento próprio + rotas
`POST /app/codigos/ocorrencia` e `POST /app/codigos/ocorrencia/{id}/excluir`),
mostrando embutidos (codigo, descrição, "com quantidade"/"sem quantidade")
e personalizados com selo/excluir. Grid da página passa a acomodar 3 cards.

## 2. Layout "site de verdade"

Reescrita do CSS/estrutura dos templates (tema escuro e sidebar mantidos):

- `main`: sem `max-width` fixo; padding maior; grids por página.
- **Ocorrências / VT-Caixa** (`page-grid`: coluna principal `minmax(0,1fr)` +
  aside `380px`; empilha < 1100px):
  - Dropzones estilizadas substituem `<input type=file>` nativo: área
    pontilhada com ícone, texto "Arraste o arquivo ou clique para escolher",
    estados hover/dragover/preenchido (mostra nome e tamanho). JS próprio em
    `app/static/app.js` (sem lib), input real escondido dentro (acessível).
  - Códigos de ocorrência como **pílulas toggle** (label estilizado sobre o
    checkbox real) com descrição em tooltip (`title`).
  - Aside: card "Como funciona" (3–4 passos numerados) + card "Requisitos"
    (Ocorrências: planilha `.xlsx/.xls` com colunas `Folha RE` e `MOTIVO` na
    linha 1; PDF de jornada com tabela por RE; máx. 50 MB; divergências →
    tela de revisão; resultado = planilha + aba "Não localizados".
    VT-Caixa: fonte Nautilus PDF/Excel; cadastral com colunas de CPF/RG/
    endereço; saída CSV latin-1; máx. 50 MB).
  - Abaixo do form: card "Processamentos recentes" — últimos 5 do histórico
    do usuário daquele tipo (`history.list_for_user` já existe; a rota passa
    `recentes` ao template), com status e link para o job.
- **Códigos**: grid adaptativo dos 3 cards; input de busca por card
  (filtro client-side em `app.js` sobre as linhas da tabela).
- **Histórico**: largura total; chips de status (`sucesso` verde, `erro`
  vermelho).
- Toques: favicon SVG inline (data URI), scrollbar estilizada, transições de
  hover, breadcrumb simples no page-header ("Início / Ocorrências").
- **A task de layout do plano deve instruir o executor a carregar a skill
  `frontend-design`** antes de escrever o CSS final.

## 3. Tutorial 2.0

- `app/static/tour-theme.css`: sobrescreve o visual do driver.js — popover
  `--surface` com borda 1px `--border` + glow gradiente, título 15px/700,
  descrição 13.5px `--text`, botões no estilo `.btn`/`.btn-primary`,
  progresso "Passo X de Y" em `--text-muted`, overlay mais escuro.
  Carregado no `app_base.html` após `driver.css`.
- `tour.js` reescrito:
  - `popover.description` com HTML (listas `<ul>`, `<code>`, `<strong>`,
    avisos `<div class="tour-warn">`). driver.js 1.x renderiza HTML na
    descrição por padrão.
  - **Welcome modal**: primeiro passo sem `element` estilizado maior
    (classe extra via `popoverClass`), com botões "Fazer o tour" (avança) e
    "Agora não" (fecha e marca visto) — implementado com `onPopoverRender`
    injetando o botão secundário.
  - Conteúdo por segmento (texto final no plano), incluindo:
    - Ocorrências: o que o sistema faz; dropzone do PDF; dropzone da
      planilha com o requisito das colunas `Folha RE`/`MOTIVO`; pílulas de
      códigos + onde criar novos; processar/progresso/divergências/download.
    - VT-Caixa: fonte, cadastral, CSV.
    - Códigos: consulta/cópia, criar benefício, criar código de ocorrência,
      departamentos, precedência sobre embutidos.
    - Histórico: busca/filtro/export/recentes.
  - Mecânica de segmentos por página, `?tour=N`, `markSeen` — mantida.

## Tratamento de erros

- CRUD ocorrência: mesmos padrões (fragmento com erro, 400).
- Dropzone: arquivo de extensão errada solta na área → mensagem inline no
  card e não preenche o input.
- Tour: passos com elemento ausente continuam sendo pulados.

## Testes

- `test_ref_codes.py`: CRUD ocorrência, normalização, duplicata (inclusive
  contra embutidos), `occurrence_config`.
- `tests/core/test_processador.py`: `montar_motivo` com `config_extras`
  (ordem embutidos→extras; extra sem quantidade não ganha número).
- `test_worker_tasks.py`: worker injeta `config_extras`.
- `test_routes_codigos.py`: seção nova (add/excluir/duplicata/permissão).
- `test_routes_app.py`/`test_routes_jobs.py`: form dinâmico mostra
  personalizado; POST aceita código personalizado; contexto `recentes`.
- Verificação manual (checklist no plano): dropzones (clique e drag),
  pílulas, tour completo com novo visual, welcome modal, busca nos cards.

## Fora de escopo

- Edição inline de personalizados (excluir + recriar).
- Tema claro / troca de tema.
- Mudanças no fluxo de jobs, conflitos ou histórico além do listado.
