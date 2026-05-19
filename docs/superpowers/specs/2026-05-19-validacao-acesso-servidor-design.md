# Validação de Acesso por Servidor — Design Spec

**Data:** 2026-05-19
**Autor:** Nicolas Almeida Hader Dias
**Status:** Aprovado pelo usuário (aguardando review final do spec)

---

## Resumo

Adicionar validação de acesso ao **Processador de Ocorrências** (app desktop tkinter empacotado como `.exe`). Cada usuário recebe uma **chave de licença vitalícia** que o app valida contra um **servidor remoto** a cada abertura. Sem chave válida, o app não abre. O administrador (autor do app) gerencia as chaves por meio de um **painel web** hospedado no mesmo servidor.

O projeto envolve **dois componentes**:

1. **Backend novo** (`license-server/`) — serviço FastAPI + SQLite hospedado em VPS próprio com HTTPS via Let's Encrypt (usando subdomínio gratuito do DuckDNS ou similar).
2. **Cliente embutido** no app atual — módulos novos `license_client.py` e `license_ui.py`, com pequena modificação em `app.py` pra rodar o bootstrap de licença antes da janela principal.

---

## Decisões de produto (resultado do brainstorming)

| Decisão | Escolha |
|---|---|
| Tipo de validação | Chave de licença/serial |
| Backend | FastAPI novo, do zero |
| Modelo de chave | Vitalícia por usuário, revogável pelo admin |
| Frequência de validação | A cada abertura do app |
| Comportamento sem internet | Bloqueia, mas com tolerância de **24h** desde a última validação bem-sucedida |
| Gerenciamento (admin) | Painel web HTML (no mesmo servidor) |
| Hospedagem | VPS próprio (a contratar) |
| HTTPS | Obrigatório — via DuckDNS + Let's Encrypt (configuração concreta fica pra fase de deploy) |

---

## Arquitetura geral

### Componentes

**1. Backend `license-server/`** — projeto novo, repositório separado.

- FastAPI servindo API JSON em `/api/*` e painel admin em `/admin/*`
- SQLite (`licenses.db`) como banco — arquivo único, sem servidor de banco separado
- Painel admin com login por senha (sem múltiplos usuários admin)
- Servido por uvicorn atrás de nginx (proxy reverso + HTTPS), gerenciado por systemd

**2. Cliente embutido em `ocorrenciaspdf/`** — três modificações ao app atual:

- **Novo:** `license_client.py` — lógica pura de validação (HTTP + cache local)
- **Novo:** `license_ui.py` — tela tkinter de ativação/erro
- **Modificado:** `app.py` — chama `bootstrap_license()` antes de criar a janela principal

### Fluxo na abertura do app

1. App lê chave do arquivo de config `~/.ocorrencias_config.json`
2. Se **não tem chave** → tela de ativação (usuário cola a chave)
3. Se **tem chave** → POST `/api/validate` enviando a chave
4. Servidor responde `{"valid": true/false, "reason": "..."}`
5. **Válida** → atualiza timestamp `last_validated_at` no config, abre o app
6. **Inválida** → mostra erro com motivo, oferece colar nova chave (loop)
7. **Servidor inacessível** → lê `last_validated_at`
   - Se `< 24h` → abre o app (modo tolerância offline)
   - Se `≥ 24h` ou nunca validou → bloqueia com mensagem, encerra app

---

## Modelo de dados (SQLite)

### Tabela `licenses`

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | |
| `key` | TEXT UNIQUE NOT NULL | formato `XXXX-XXXX-XXXX-XXXX`, `[A-Z0-9]` |
| `client_name` | TEXT NOT NULL | nome livre do cliente, ex: "João Silva" |
| `notes` | TEXT | observações livres do admin |
| `revoked` | INTEGER NOT NULL DEFAULT 0 | 0 = ativa, 1 = revogada |
| `created_at` | TEXT NOT NULL | ISO 8601 UTC |
| `revoked_at` | TEXT | ISO 8601 UTC quando foi revogada |

### Tabela `validation_log`

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | |
| `license_id` | INTEGER NOT NULL REFERENCES licenses(id) | |
| `validated_at` | TEXT NOT NULL | ISO 8601 UTC |
| `ip` | TEXT NOT NULL | IP de origem da requisição |
| `app_version` | TEXT | versão do app enviada no body (ex: "1.34") |

### Formato da chave

- 4 grupos de 4 caracteres, alfanumérico maiúsculo
- Alfabeto: `A-Z` e `0-9` (36 símbolos)
- Espaço total: `36^16 ≈ 8 × 10^24` combinações
- Gerada por `secrets.token_urlsafe()` filtrado/formatado pra ASCII maiúsculo + dígitos

### Chave em texto claro no banco (não-hash)

O admin precisa ver a chave em texto para entregar ao cliente, então ela fica armazenada em texto no banco. O banco é SQLite num arquivo local do VPS, acessível apenas via SSH do dono. Não há acesso externo ao banco, e a comunicação cliente↔servidor é via HTTPS.

---

## Endpoints HTTP

### Públicos (sem autenticação)

| Método | Path | Body | Resposta |
|---|---|---|---|
| POST | `/api/validate` | `{"key": "XXXX-XXXX-XXXX-XXXX", "app_version": "1.34"}` | `200 {"valid": true, "client_name": "..."}` ou `200 {"valid": false, "reason": "not_found"\|"revoked"}` |

**Notas:**
- Sempre responde 200 com `valid` boolean — não diferencia 404/401 para não dar pistas a quem tenta enumerar chaves
- Validações bem-sucedidas são registradas em `validation_log` (com IP e `app_version`)
- Body inválido (formato errado da chave, JSON malformado) responde `{"valid": false, "reason": "not_found"}` — defesa em profundidade contra enumeração

### Admin (exigem sessão autenticada)

| Método | Path | Descrição |
|---|---|---|
| GET | `/admin/login` | Tela de login (form HTML) |
| POST | `/admin/login` | Recebe senha, cria sessão (cookie). Falha sempre mostra mensagem genérica. |
| POST | `/admin/logout` | Encerra sessão |
| GET | `/admin` | Lista de licenças (HTML): chave, cliente, status, criada em, última validação |
| GET | `/admin/new` | Formulário pra criar nova licença |
| POST | `/admin/new` | Cria licença: gera chave nova, salva, redireciona pra `/admin` |
| POST | `/admin/{id}/revoke` | Marca licença como revogada |
| POST | `/admin/{id}/unrevoke` | Reverte revogação |
| GET | `/admin/{id}` | Detalhe de uma licença + histórico de validações |

### Autenticação do admin

- Senha única em variável de ambiente `ADMIN_PASSWORD` (não há múltiplos admins)
- Hash bcrypt mantido em memória do processo
- Sessão via cookie assinado (FastAPI `SessionMiddleware` com `SECRET_KEY` em env var)
- Cookie marcado `HttpOnly`, `Secure`, `SameSite=Lax`, expira em **7 dias**
- CSRF token embutido em todos os forms (POSTs do painel exigem token válido)
- Rate limits (lib `slowapi`):
  - `/admin/login`: **5 tentativas/min/IP**
  - `/api/validate`: **60 requisições/min/IP**

---

## Estrutura de arquivos

### Backend novo (`license-server/`)

```
license-server/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, middleware, monta rotas
│   ├── config.py            # Lê env vars (ADMIN_PASSWORD, SECRET_KEY, DB_PATH)
│   ├── db.py                # Conexão SQLite + criação de schema
│   ├── models.py            # Dataclasses: License, ValidationLog
│   ├── licenses.py          # CRUD: create_license, get_by_key, revoke, list_all
│   ├── keygen.py            # generate_key() -> "XXXX-XXXX-XXXX-XXXX"
│   ├── security.py          # hash_password, verify_password, csrf token, auth dependency
│   ├── routes_api.py        # /api/validate
│   ├── routes_admin.py      # /admin/* (templates HTML)
│   └── templates/
│       ├── base.html
│       ├── login.html
│       ├── list.html
│       ├── new.html
│       └── detail.html
├── tests/
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

### Cliente — adições ao app atual

```
ocorrenciaspdf/
├── app.py                   # MODIFICAR: chamar bootstrap_license() antes da janela principal
├── license_client.py        # CRIAR: classe LicenseClient
├── license_ui.py            # CRIAR: tela tkinter de ativação
└── tests/
    └── test_license_client.py  # CRIAR
```

**Justificativa da separação no cliente:**
- `license_client.py` é lógica pura (HTTP + leitura/escrita de config) — testável sem GUI
- `license_ui.py` isola tkinter, evita poluir `app.py` (que já é grande)
- `app.py` ganha apenas ~10 linhas no início

---

## Cliente desktop — interface

### `license_client.py`

```python
class LicenseStatus(Enum):
    VALID = "valid"
    INVALID = "invalid"
    OFFLINE_TOLERATED = "offline_tolerated"
    OFFLINE_EXPIRED = "offline_expired"
    NO_KEY = "no_key"

@dataclass
class ValidationResult:
    status: LicenseStatus
    reason: str | None = None
    client_name: str | None = None

class LicenseClient:
    SERVER_URL = "https://meuapp.duckdns.org"   # placeholder até VPS estar configurada
    OFFLINE_TOLERANCE_HOURS = 24
    TIMEOUT_SECONDS = 10

    def __init__(self, config_path: Path = Path.home() / ".ocorrencias_config.json"):
        self.config_path = config_path

    def get_saved_key(self) -> str | None: ...
    def save_key(self, key: str) -> None: ...
    def clear_key(self) -> None: ...
    def validate(self, key: str | None = None) -> ValidationResult: ...
```

### Lógica de `validate()`

1. Se `key` não foi passada, lê do config. Se não tiver → retorna `NO_KEY`
2. Tenta POST `/api/validate` com `{"key": ..., "app_version": "<versão atual>"}`
3. **Sucesso e `valid=true`:** atualiza `last_validated_at`, retorna `VALID` com `client_name`
4. **Sucesso e `valid=false`:** retorna `INVALID` com `reason`. **Não apaga** a chave do config
5. **Erro de rede / timeout / status != 2xx / JSON inválido:** lê `last_validated_at`
   - Delta `< 24h` → `OFFLINE_TOLERATED`
   - Delta `≥ 24h` ou ausente → `OFFLINE_EXPIRED`

### `license_ui.py`

Uma função pública:

```python
def show_activation_window(initial_message: str = "") -> str | None: ...
```

- Janela modal pequena, centralizada
- Título: "Ativação de licença"
- Mostra `initial_message` acima do campo (ex: "Chave revogada. Insira nova chave.")
- Campo de texto pra colar a chave, botão "Ativar", botão "Sair"
- Retorna a chave digitada ou `None` se usuário clicou Sair

Função adicional:

```python
def show_error_window(message: str) -> None: ...
```

- Diálogo simples de erro com botão "OK", usado para `OFFLINE_EXPIRED`

### `app.py` — bootstrap

Adicionar no início, **antes** de criar a janela principal:

```python
def bootstrap_license() -> bool:
    """Retorna True se app deve continuar, False se deve encerrar."""
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

        if new_key is None:
            return False

        client.save_key(new_key)
        # Loop revalida com a nova chave
```

---

## Tratamento de erros

### Backend

- Validação de body via Pydantic. JSON malformado → 422 automático (apenas para endpoints admin; para `/api/validate` é convertido em `valid=false` defensivamente)
- Exceções internas (DB, etc.) → log com stack trace, resposta `500 {"error": "internal"}` sem detalhes
- Login admin com senha errada sempre mostra "Senha incorreta" (mensagem genérica)
- Logs do servidor **nunca** registram a chave completa — apenas os 4 primeiros caracteres + `***` (ex: `A3F2-***`)

### Cliente

- Toda exceção de rede (timeout, DNS, conexão recusada, SSL) → caminho `OFFLINE_*` (sem crash)
- Resposta com status != 200 ou JSON inválido → também tratado como `OFFLINE_*`
- Arquivo de config corrompido (JSON inválido) → log, tratado como "sem chave", segue pra tela de ativação

---

## Estratégia de testes

### Backend (pytest + `httpx.AsyncClient` + SQLite temporário)

| Arquivo | Cobertura |
|---|---|
| `test_keygen.py` | Formato `XXXX-XXXX-XXXX-XXXX`, alfabeto `[A-Z0-9]`, 1000 chaves geradas únicas |
| `test_licenses.py` | create / get_by_key / revoke / unrevoke / list_all em DB temporário; chave duplicada falha |
| `test_security.py` | hash/verify de senha, geração e verificação de token CSRF |
| `test_routes_api.py` | `/api/validate` com chave válida, inexistente, revogada, formato inválido, body malformado; verifica que `validation_log` recebe registro só em validações bem-sucedidas |
| `test_routes_admin.py` | Login (correto/incorreto), acesso a `/admin` sem sessão redireciona, criar/revogar/desfazer-revogação, CSRF inválido rejeita POSTs, rate limit do login |

### Cliente

| Arquivo | Cobertura |
|---|---|
| `test_license_client.py` | `save_key`/`get_saved_key`/`clear_key` com config path temporário; `validate()` com mock de HTTP retornando: válida, inválida, revogada, timeout, erro de conexão, JSON inválido; cálculo do delta de 24h pra tolerância offline; config corrompido tratado como sem chave |

UI tkinter (`license_ui.py`) **não terá testes automatizados** — código pequeno e visual, testado manualmente.

---

## Segurança — resumo

- HTTPS obrigatório no cliente (sem `verify=False`)
- Senha admin: apenas em env var `ADMIN_PASSWORD`, hash bcrypt em memória, nunca em disco
- `SECRET_KEY` em env var, 32+ bytes aleatórios
- Cookie de sessão `HttpOnly`, `Secure`, `SameSite=Lax`
- CSRF token em todos os POSTs do painel
- Rate limit: `/admin/login` 5/min/IP, `/api/validate` 60/min/IP
- Logs do servidor nunca registram chave completa (apenas 4 primeiros + `***`)
- `validation_log` registra IP (mencionar no README do app por questão de LGPD)
- Backup do `licenses.db` recomendado via cron + `sqlite3 .backup` (fora do escopo, documentar no README do servidor)

---

## Itens fora do escopo

- Provisionamento inicial do VPS (escolha de provedor, criação da máquina, hardening básico)
- Configuração do DuckDNS / Let's Encrypt — documentada no README do servidor mas executada manualmente quando a VPS estiver pronta
- Versionamento das chaves (renovação, expiração) — modelo é vitalício
- Múltiplos administradores
- Recuperação de senha do admin (única forma: trocar `ADMIN_PASSWORD` no env e reiniciar o serviço)
- Tela do usuário pra ver a própria chave/status detalhado dentro do app (a tela de ativação é suficiente)

---

## Versionamento

- **Servidor:** tag `v0.1.0` no commit inicial
- **Cliente:** próximo bump de versão do app desktop integrará as mudanças (provavelmente `v1.35`)
- `SERVER_URL` em `license_client.py` é constante; mudança de URL exige nova build do `.exe`
