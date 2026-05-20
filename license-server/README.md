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
