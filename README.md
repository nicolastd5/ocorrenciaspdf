# Processador de Ocorrências

App desktop (PySide6) que cruza relatórios PDF/Excel de jornada com planilhas
de pedido e gera as saídas usadas na operação:

- **Ocorrências** — lê o PDF de jornada, extrai códigos de ocorrência por RE
  (com dupla varredura e verificação opcional por IA/Gemini Vision), reconcilia
  divergências e preenche a coluna MOTIVO da planilha de pedido.
- **VT-Caixa** — processa a fonte Nautilus (PDF ou Excel) contra o Excel
  cadastral e gera o CSV de benefícios (latin-1), com verificação opcional por IA.
- **Códigos** — tabelas de referência (operadora → código, substituições de
  departamento) com cópia em um clique.
- **Histórico** — registro local (`~/.ocorrencias_history.json`) com busca,
  filtro por status e exportação CSV.

O licenciamento e o auto-update falam com o `license-server/` (FastAPI),
hospedado na VPS. O download de atualização é validado por SHA-256.

## Rodando em desenvolvimento

```powershell
py -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python app.py
```

## Testes

```powershell
.venv\Scripts\python -m pytest -q            # tudo (cliente + license-server)
.venv\Scripts\python -m pytest tests -q      # só o app
```

## Build e release

1. Bump da versão em [appinfo.py](appinfo.py) (`APP_VERSION`).
2. Gerar o exe com PyInstaller usando o `.spec` da versão
   (`ProcessadorOcorrencias-vX.YY.spec`).
3. `py deploy.py --release X.YY` — sobe o exe para a VPS, grava o
   `version.json` (versão + arquivo + sha256) e reinicia o serviço.

Clientes em campo detectam a versão nova no `/api/version`, baixam pelo
`/api/download/...` e reiniciam sozinhos (ver [auto_update.py](auto_update.py)).

## Estrutura

```
app.py                  # entrypoint (splash, auto-update, licença)
appinfo.py              # APP_VERSION e SERVER_URL — fonte única
processador.py          # núcleo Ocorrências (PDF → Excel)
vt_caixa_processador.py # núcleo VT-Caixa (Nautilus → CSV)
license_client.py       # validação de licença (com tolerância offline)
auto_update.py          # verificação/baixa/relança do exe (SHA-256)
ui/                     # PySide6: tema, janelas, abas e widgets
license-server/         # FastAPI: licenças, config (key Gemini) e releases
tests/                  # pytest + pytest-qt
```
