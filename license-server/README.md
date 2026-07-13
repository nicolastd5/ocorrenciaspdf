# Processador de Ocorrências — Web

Web app (FastAPI + Jinja2 + HTMX) que substitui o app desktop: área logada com
Ocorrências, VT-Caixa, Códigos e Histórico, mais painel admin (usuários).
Processamentos rodam em fila Redis + RQ; núcleos em `core/` (sem IA).

## Setup local

```bash
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -r requirements.txt
cp .env.example .env
# editar .env e definir ADMIN_PASSWORD e SECRET_KEY
# opcionais: DB_PATH, DATA_DIR (padrão: data), REDIS_URL (padrão: redis://localhost:6379/0)
```

## Rodar localmente

```bash
uvicorn app.main:app --reload      # app web  → http://localhost:8000/login
rq worker default                  # worker (precisa de Redis rodando)
```

Painel admin: http://localhost:8000/admin/login

## Testes

```bash
pytest -q
```

Os testes não precisam de Redis (fila fake síncrona via fakeredis) e isolam
`DB_PATH`/`DATA_DIR` em diretórios temporários.

## Deploy

`py deploy.py` (na raiz do repo) envia os arquivos modificados, roda
`pip install` remoto e reinicia `license-server` (app) e `ocorrencias-worker`.
Use `--all` para enviar tudo e `--check` para simular.

### Instalação na VPS (uma vez)

1. `ssh` na VPS (`/home/ubuntu/license-server`)
2. `sudo apt install redis-server && sudo systemctl enable --now redis-server`
3. Copiar `deploy/ocorrencias-worker.service` para `/etc/systemd/system/` e
   `sudo systemctl daemon-reload` (o app web já roda como serviço
   `license-server`; `deploy/ocorrencias-web.service` fica como referência)
4. Acrescentar ao env do serviço (`.env.systemd`):
   `DATA_DIR=/home/ubuntu/license-server/data` e
   `REDIS_URL=redis://localhost:6379/0`
5. nginx: `client_max_body_size 50m;` no server block do domínio
   (ver `deploy/nginx-snippet.conf`), depois `nginx -t && systemctl reload nginx`
6. `sudo systemctl enable --now ocorrencias-worker && sudo systemctl restart license-server`
7. Cron da retenção (7 dias):
   `15 3 * * * cd /home/ubuntu/license-server && .venv/bin/python cleanup.py`
8. Criar os usuários em `https://nicolasapp.duckdns.org/admin/users`
9. Testar o fluxo completo: login → Ocorrências (com divergência) → revisão →
   download; VT-Caixa → download; Histórico
10. Backup do SQLite continua via cron: `sqlite3 licenses.db .backup backup.db`

### Corte final (quando os usuários migrarem)

- Executar a Task 16 do plano (`docs/superpowers/plans/2026-07-13-web-migration.md`):
  remover rotas de licença/release e config de IA do servidor.
- Task 18: aposentar o app desktop (mover para `legacy-desktop/`).
