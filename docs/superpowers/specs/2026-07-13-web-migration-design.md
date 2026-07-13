# Design — Migração do Processador de Ocorrências para Web

**Data:** 2026-07-13
**Status:** Aprovado pelo usuário (conversa de brainstorming)

## Objetivo

Substituir o app desktop (PySide6 + PyInstaller + auto-update + licença por chave)
por uma aplicação web hospedada na VPS existente, acessada em
`https://nicolasapp.duckdns.org`. Ao final da migração o exe é aposentado.

## Decisões tomadas

| Tema | Decisão |
|---|---|
| Destino do desktop | Web substitui o desktop por completo |
| Acesso | Login com usuário/senha (contas criadas pelo admin) |
| Histórico | No servidor, por usuário |
| Frontend | FastAPI + Jinja2 + HTMX (mesma stack do painel admin) |
| IA/Gemini | **Removida por completo** (cliente e config no servidor) |
| Divergências V1×V2 | Tela de revisão web antes do download |
| Retenção de arquivos | 7 dias, limpeza automática; histórico guarda só metadados após expirar |
| Arquitetura | Evoluir o license-server existente (um único app FastAPI) |
| Domínio | Manter `nicolasapp.duckdns.org` (DNS/HTTPS já configurados) |
| Execução dos jobs | Fila **Redis + RQ** com processo worker dedicado |

## Arquitetura

```
navegador ── HTTPS ── nginx ── uvicorn (FastAPI app)
                                  │ enfileira
                                Redis ── rq worker (systemd)
                                  │            │
                               SQLite      data/jobs/<id>/
```

Um único repositório/serviço evoluído a partir de `license-server/`:

```
license-server/
  app/
    main.py            # já existe — ganha novos routers
    routes_admin.py    # já existe — ganha gestão de usuários
    routes_auth.py     # NOVO: login/logout de usuários
    routes_jobs.py     # NOVO: upload, progresso, conflitos, download
    routes_app.py      # NOVO: páginas Ocorrências, VT-Caixa, Códigos, Histórico
    jobs.py            # NOVO: modelo/estado de jobs + enfileiramento RQ
    worker_tasks.py    # NOVO: funções executadas pelo rq worker
    users.py           # NOVO: CRUD de usuários + hash de senha
    templates/         # já existe — ganha as telas da área do usuário
  core/                # NOVO pacote: processador.py e vt_caixa_processador.py
                       # movidos do cliente, sem Qt e sem verificar_com_ia
```

## Componentes

### core/ (núcleos de processamento)
- `processador.py` movido para `license-server/core/`, removendo
  `verificar_com_ia` e a dependência de `google-genai`/`pypdfium2`/`pillow`.
- `vt_caixa_processador.py` idem (remover caminho de IA).
- Interface inalterada: `processar(...)`, `extrair_ocorrencias(...)`,
  `extrair_ocorrencias_texto(...)`, `reconciliar(...)` com `progress_cb`.
- Testes existentes dos núcleos migram junto.

### Autenticação de usuários
- Tabela `users`: id, email, password_hash (argon2 ou bcrypt), nome, ativo,
  criado_em. Admin continua com o login separado que já existe.
- Sessão via `SessionMiddleware` já configurado (ajustar `https_only=True`).
- Admin cria/desativa usuários e redefine senhas pelo painel.
- Rotas de licença/releases antigas são removidas após a migração dos
  usuários (fase 5).

### Jobs (fila Redis + RQ)
- Tabela `jobs`: id (uuid), user_id, tipo (`ocorrencias` | `vt_caixa`),
  status (`queued` | `running` | `awaiting_review` | `done` | `error`),
  progresso (0–100), mensagem, parâmetros (JSON), resultado (JSON),
  criado_em, expira_em.
- Upload grava arquivos em `data/jobs/<id>/in/`, cria o registro e enfileira
  no RQ. O worker roda o núcleo, atualizando progresso no banco via
  `progress_cb`.
- **Ocorrências:** worker roda V1 + V2 e `reconciliar`. Sem conflitos →
  gera a planilha e status `done`. Com conflitos → status `awaiting_review`;
  a resolução do usuário (tela web) é enviada e a própria rota aplica
  `dados_externos` e finaliza (etapa rápida, não precisa voltar à fila).
- **VT-Caixa:** fluxo direto upload → CSV.
- Página de acompanhamento consulta `GET /app/jobs/<id>/status` via polling
  HTMX (1s) e troca para a tela de conflitos ou de download conforme o status.
- Resultados em `data/jobs/<id>/out/`; download autenticado e restrito ao dono.

### Retenção
- Job agendado (rq-scheduler ou cron diário) apaga `data/jobs/<id>/` com
  `expira_em` vencido (7 dias) e marca o job como expirado — o registro de
  histórico permanece.

### Histórico
- Tabela `history` por usuário (equivalente ao `~/.ocorrencias_history.json`):
  data, tipo, arquivos de entrada (nomes), contagens, status, link para o job.
- Tela com busca, filtro por status e exportação CSV.

### Telas
1. **Login** (`/login`)
2. **Ocorrências** (`/app/ocorrencias`) — dropzone PDF + Excel, seleção de
   códigos, dias do mês e colunas Qt, barra de progresso, revisão de
   conflitos, download.
3. **VT-Caixa** (`/app/vt-caixa`) — upload Nautilus (PDF/Excel) + cadastral,
   progresso, download do CSV (latin-1).
4. **Códigos** (`/app/codigos`) — tabelas de referência com botão copiar,
   renderizadas das constantes do `core/` (somente leitura, como no desktop).
5. **Histórico** (`/app/historico`).
6. **Admin** (existente) — ganha CRUD de usuários; perde config de IA e,
   na fase final, licenças/releases.

### Infra (VPS)
- `apt install redis-server` + systemd unit `rq worker` (mesma venv do app).
- nginx já faz proxy com HTTPS Let's Encrypt para o domínio duckdns —
  ajustar `client_max_body_size` para uploads (ex.: 50 MB).
- `deploy.py` simplificado: rsync do código + restart de `app` e `worker`
  (fim do release de exe).
- Backup do SQLite via cron (já previsto).

### Tratamento de erros
- Exceções no worker marcam o job como `error` com mensagem amigável
  (ex.: "Colunas RE/MOTIVO não encontradas na planilha") e traceback no log.
- Upload validado: extensão, tamanho e conteúdo mínimo antes de enfileirar.
- Restart do worker no meio de um job: RQ reencaminha ou marca falho —
  o usuário reenvia (jobs são idempotentes, entradas ficam salvas 7 dias).

### Testes
- Núcleos: suíte existente migra para `license-server/tests/core/`.
- Rotas novas: auth (login, senha errada, usuário inativo), ciclo completo de
  job com RQ em modo síncrono/fake (upload → progresso → conflito → resolução
  → download), permissão (usuário A não acessa job do usuário B), retenção,
  export do histórico.

## Fora de escopo
- Qualquer funcionalidade de IA/Gemini.
- Auto-update e licenciamento offline (deixam de existir).
- Suporte simultâneo de longo prazo ao desktop (apenas durante a fase de
  transição, sem novos releases).

## Fases de entrega
1. **Core:** mover núcleos para `core/`, remover IA, migrar testes.
2. **Auth:** tabela users, login/logout, CRUD no admin, layout base da área
   do usuário.
3. **Ocorrências completo:** Redis/RQ, jobs, upload, progresso, revisão de
   conflitos, download, retenção.
4. **Demais telas:** VT-Caixa, Códigos, Histórico.
5. **Corte:** deploy final, criação das contas, comunicação aos usuários,
   remoção das rotas de licença/release e aposentadoria do exe.
