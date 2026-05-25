# Migração da UI para PySide6 (v2.0) — Design Spec

**Data:** 2026-05-25
**Autor:** Nicolas Almeida Hader Dias
**Status:** Aguardando review do usuário

---

## Resumo

Reescrita da camada de apresentação do **Processador de Ocorrências** de **Tkinter** para **PySide6** em um único salto (big bang → v2.0). A lógica de processamento (PDF/XLSX), o cliente de licença e o auto-update permanecem intactos — apenas o `app.py` (3609 linhas, monolítico) e o `license_ui.py` são substituídos por um pacote `ui/` modular. A migração é a oportunidade para: (1) modernizar o visual (paleta GitHub-dark, fontes Inter + JetBrains Mono já embutidas), (2) reorganizar o código em módulos pequenos por responsabilidade, (3) adicionar features que o Tk não entrega bem (drag-and-drop, abas reais, toggle dark/light em runtime, histórico de processamentos), (4) remover a feature "Deduzir dias nas colunas Qt" que não é mais usada.

---

## Decisões de produto (resultado do brainstorming)

| Decisão | Escolha |
|---|---|
| Binding Qt | **PySide6** (LGPL — distribuição comercial sem ônus de licença) |
| Estratégia de migração | **Big bang** — reescrita completa em branch separada, bump v1.60 → v2.0 |
| Layout de navegação | **Abas no topo** (`QTabWidget`) |
| Disposição da tela principal | **Wizard vertical** (cards numerados 1 → 2 → 3 → Processar → Log) |
| Paleta | **GitHub-dark refinada** — bg `#0d1117`, surface `#161b22`, border `#30363d`, verde `#238636` pra ação primária, azul `#58a6ff` reservado para links/info |
| Tema | Dark default + toggle dark/light em runtime (persistido) |
| Estrutura de código | Pacote `ui/` com um módulo por tela; `app.py` vira só entrypoint |
| Histórico | Tabela na aba Histórico + persistência em `~/.ocorrencias_history.json` (cap 500 entradas) |
| Drag-and-drop | Suportado nas dropzones (PDFs e XLSX) |
| Splash | Mantido (`QSplashScreen`) |
| Licença | Bootstrap igual hoje — só as janelas de ativação/erro viram diálogos Qt |
| Auto-update | Mantido — só ajusta o nome do exe pra v2.0 |
| Packaging | PyInstaller `--onefile` (`ProcessadorOcorrencias-v2.0.spec`) |
| Removido | Toggle "Deduzir dias nas colunas Qt", campo "Dias do mês", seleção de colunas Qt e a lógica de dedução de FA/AT/SD/LC ([app.py:330](../../../app.py#L330), [app.py:955](../../../app.py#L955), [app.py:2534](../../../app.py#L2534), [app.py:2710-2717](../../../app.py#L2710-L2717)) |

---

## Escopo

### Dentro do escopo da v2.0

- Substituir todo o conteúdo de [app.py](../../../app.py) por um novo entrypoint + pacote `ui/`.
- Reescrever [license_ui.py](../../../license_ui.py) em Qt como `ui/license_dialogs.py` (mesma API: `show_activation_window(message) -> str | None`, `show_error_window(message)`).
- 4 abas reais: Ocorrências, VT-Caixa, Histórico, Configurações.
- 4 features novas: drag-and-drop, abas (`QTabWidget`), toggle dark/light em runtime, histórico de processamentos.
- Remover a feature "Deduzir dias nas colunas Qt".
- Novo `.spec` PyInstaller (`ProcessadorOcorrencias-v2.0.spec`); ajustes pontuais em `deploy.py` e `auto_update.py`.
- Bump `APP_VERSION = "2.0"` em [license_client.py](../../../license_client.py).

### Fora do escopo (não muda)

- [processador.py](../../../processador.py) — lógica de extração de PDFs e preenchimento de MOTIVO.
- [vt_caixa_processador.py](../../../vt_caixa_processador.py) — processador VT/Caixa.
- [license_client.py](../../../license_client.py) — exceto o número de versão.
- [auto_update.py](../../../auto_update.py) — exceto a string com nome do exe.
- Servidor de licença (`license-server/`).
- Formato dos PDFs/XLSX de entrada e saída.
- Fluxo de validação de licença (sequência: bootstrap → validar → splash → janela principal; loop de retry; 24h offline tolerado).

---

## Arquitetura

### Estrutura de arquivos

```
ocorrenciaspdf/
├── app.py                          # entrypoint (~80 linhas): licença → splash → MainWindow
├── processador.py                  # (intacto)
├── vt_caixa_processador.py         # (intacto)
├── license_client.py               # (só APP_VERSION = "2.0")
├── auto_update.py                  # ajuste pequeno: novo nome de exe
├── deploy.py                       # ajuste: novo .spec + hooks PySide6
├── requirements.txt                # + PySide6>=6.7
├── requirements-dev.txt            # NOVO — pytest-qt
├── ProcessadorOcorrencias-v2.0.spec
├── assets/                         # (intacto — Inter + JetBrains Mono)
└── ui/
    ├── __init__.py
    ├── main_window.py              # QMainWindow + QTabWidget no topo
    ├── theme.py                    # paleta dark/light + gerador de QSS
    ├── settings.py                 # leitura/escrita de ~/.ocorrencias_config.json
    ├── history.py                  # leitura/escrita de ~/.ocorrencias_history.json
    ├── splash.py                   # QSplashScreen
    ├── license_dialogs.py          # janelas de ativação/erro
    ├── tabs/
    │   ├── __init__.py
    │   ├── ocorrencias.py
    │   ├── vt_caixa.py
    │   ├── historico.py
    │   └── configuracoes.py
    └── widgets/
        ├── __init__.py
        ├── drop_zone.py            # área de drag-and-drop reutilizável
        ├── log_panel.py            # painel de log monoespaçado com auto-scroll
        ├── primary_button.py       # botão verde "ação principal"
        └── section_card.py         # card numerado do wizard
```

### Princípios de organização

- Cada arquivo de `ui/` deve caber em ~200-400 linhas.
- Cada aba é um `QWidget` autocontido; recebe dependências (config, history, processadores) por injeção no construtor — sem singleton global.
- `theme.py`, `settings.py`, `history.py` são módulos puros (sem dependência de Qt para `settings`/`history`; `theme` depende de Qt só pra gerar QSS).
- Abas não conhecem umas às outras; comunicam-se com a `MainWindow` via sinais (ex.: aba Ocorrências dispara `processed(entry)` → MainWindow chama `history.append(entry)`).

### Threading

Processamentos pesados rodam em **`QThread` + worker `QObject`**. O worker expõe os sinais:

```
progress(int, str)   # 0–100, mensagem ("preenchendo MOTIVO…")
log(str)             # linha individual pro painel de log
finished(dict)       # {status, output_path, duration, rows_processed, ...}
error(str, str)      # (mensagem amigável, traceback completo)
```

`processador.py` / `vt_caixa_processador.py` permanecem sem dependência de Qt — aceitam um callback de progresso opcional (já é o padrão hoje), e o worker traduz esse callback em `emit(progress, ...)`.

**Cancelamento:** o worker checa `_cancel_requested` entre PDFs/linhas; ao detectar, encerra e emite `finished({status: 'cancelled'})`. O botão "Cancelar" apenas seta a flag — nunca mata a thread (evita XLSX corrompido).

---

## Telas e fluxo

### Janela principal — [ui/main_window.py](../../../ui/main_window.py)

`QMainWindow` com `QTabWidget` no topo. 4 abas fixas, com Ocorrências como default:

1. Ocorrências
2. VT-Caixa
3. Histórico
4. Configurações

`QStatusBar` no rodapé: versão, indicador de licença válida (✔ verde), último processamento ("último: 14:32 · ok"). Geometria da janela (tamanho, posição) é persistida em config e restaurada na abertura.

Sem `QMenuBar` — toggle dark/light fica em Configurações.

### Aba Ocorrências — [ui/tabs/ocorrencias.py](../../../ui/tabs/ocorrencias.py)

Wizard vertical com cards numerados (`SectionCard` = `QGroupBox` estilizado):

```
┌─ 1 · PDFs de jornada ──────────────────────────────┐
│  [DropZone: arraste PDFs ou clique pra selecionar]│
│  Lista de arquivos selecionados com botão ✕       │
└────────────────────────────────────────────────────┘

┌─ 2 · Planilha de pedido ───────────────────────────┐
│  [DropZone .xlsx]                                  │
│  Arquivo selecionado com botão ✕                  │
└────────────────────────────────────────────────────┘

┌─ 3 · Opções ───────────────────────────────────────┐
│  Códigos de ocorrência: [FA, AT, SD, LC, ...]     │
│  ☐ Usar IA para refinar (Gemini)                  │
└────────────────────────────────────────────────────┘

              [▶ Processar]  (PrimaryButton verde)

┌─ Log ──────────────────────────────────────────────┐
│  LogPanel monoespaçado com auto-scroll             │
│  Barra de progresso aparece embaixo durante run    │
└────────────────────────────────────────────────────┘
```

Dropzones aceitam tanto clique (abre `QFileDialog`) quanto arrastar (eventos `dragEnter` / `drop`). O botão "Processar" habilita só quando há ≥1 PDF e exatamente 1 XLSX (estado READY).

**Removido vs hoje:** toggle "Deduzir dias nas colunas Qt", campo "Dias do mês", widgets de seleção de colunas Qt — bem como toda a lógica associada em [app.py:330-331](../../../app.py#L330), [app.py:955-1000](../../../app.py#L955), [app.py:2534-2540](../../../app.py#L2534), [app.py:2710-2717](../../../app.py#L2710), e os parâmetros correspondentes na chamada do processador em [app.py:2763](../../../app.py#L2763).

### Aba VT-Caixa — [ui/tabs/vt_caixa.py](../../../ui/tabs/vt_caixa.py)

Mesma arquitetura visual (wizard + LogPanel), com os inputs específicos de [vt_caixa_processador.py](../../../vt_caixa_processador.py) — o conjunto exato de inputs será inventariado na fase de plano (lendo `ProcessadorVTCaixa`), mas a estrutura visual e o ciclo de execução são idênticos aos de Ocorrências.

### Aba Histórico — [ui/tabs/historico.py](../../../ui/tabs/historico.py)

`QTableView` com modelo customizado (`QAbstractTableModel`). Colunas:

| Data/hora | Tipo | Arquivos de entrada | Saída | Status | Duração |
|---|---|---|---|---|---|
| 2026-05-25 14:32 | Ocorrências | jornada_jan.pdf (+1) | pedido_jan_out.xlsx | ✔ ok (verde) | 12s |

Ações:
- Duplo-clique: abre o XLSX de saída no app padrão (`os.startfile` no Windows).
- Menu de contexto (botão direito): "Abrir pasta da saída", "Reprocessar com os mesmos arquivos", "Remover do histórico".
- Botão "Limpar histórico" no canto superior direito (com confirmação).

Persistência via [ui/history.py](../../../ui/history.py) — `~/.ocorrencias_history.json`, lista append-only, cap em 500 entradas (FIFO).

### Aba Configurações — [ui/tabs/configuracoes.py](../../../ui/tabs/configuracoes.py)

Seções em blocos (não colapsáveis na v2.0 — pode virar collapsible depois se ficar grande):

- **Aparência** — radio dark/light, preview ao vivo (ao mudar, aplica o QSS na hora).
- **API Gemini** — `QLineEdit` mascarado pra chave, botão "Testar" (faz uma chamada de probe).
- **Licença** — exibe chave atual (mascarada), status, validade offline restante, botão "Trocar chave" → reabre `show_activation_window()`.
- **Atualizações** — botão "Verificar agora" → chama `auto_update.check_and_update()`; mostra versão atual.
- **Sobre** — versão, autor, link de suporte.

### Splash — [ui/splash.py](../../../ui/splash.py)

`QSplashScreen` com logo (PNG em `assets/`); mostra mensagens via `showMessage()` durante: "Validando licença…", "Carregando interface…". Fecha quando MainWindow aparece (`finish(window)`).

### Diálogos de licença — [ui/license_dialogs.py](../../../ui/license_dialogs.py)

Substitui [license_ui.py](../../../license_ui.py) preservando a API pública:

```python
def show_activation_window(message: str) -> str | None: ...
def show_error_window(message: str) -> None: ...
```

Implementação em `QDialog` modal. Retorna a chave digitada (via `dialog.exec()` + `dialog.result()`) ou `None` se o usuário cancelar.

---

## Estados, threading e tratamento de erro

### Máquina de estados de cada aba de processamento

```
IDLE → READY (≥1 PDF e 1 XLSX) → RUNNING → DONE | ERROR | CANCELLED → IDLE/READY
```

| Estado | Botão principal | Inputs | Log |
|---|---|---|---|
| IDLE | "Processar" (desabilitado) | habilitados | vazio |
| READY | "Processar" (verde, habilitado) | habilitados | vazio |
| RUNNING | "Cancelar" (amarelo) | desabilitados | linhas + barra de progresso |
| DONE | "Processar novamente" + "Abrir saída" | desabilitados até reset manual | linhas + ✔ verde |
| ERROR | "Tentar de novo" + "Copiar erro" | habilitados | linhas + ✕ vermelho |
| CANCELLED | "Processar" | habilitados | linhas + "cancelado" |

Transição DONE → READY/IDLE é manual (usuário clica "Processar novamente" ou troca um input). Isso preserva o resultado da rodada anterior à vista do usuário.

### Categorias de erro

1. **Erros esperados e atribuíveis** (PDF ilegível, planilha sem coluna MOTIVO, código inválido) → worker emite `error("mensagem amigável", traceback)`. UI exibe linha vermelha no LogPanel + botão "Detalhes" (abre `QDialog` com traceback). **Não usa `QMessageBox` modal** — preserva a leitura do log.

2. **Erros inesperados** (qualquer `Exception` não tratada) → `try/except Exception` no topo do `run()` do worker captura, emite `error("Erro inesperado: <repr>", traceback)`. Mesmo tratamento visual + botão "Copiar erro" pro usuário mandar pro suporte.

3. **Erros de UI/inicialização** (config corrompido, asset faltando, falha ao salvar histórico) → log em `stderr` + toast não-modal no canto inferior; app continua funcionando. Config corrompido é tratado igual hoje: cai pra `{}` ([app.py:117-121](../../../app.py#L117)).

### Licença

Sem mudança no fluxo. Bootstrap acontece em `app.py` antes da splash (igual hoje em `bootstrap_license()`); loop de retry chama `ui.license_dialogs.show_activation_window()`; se o usuário cancela, app fecha. Falha online tolerada por 24h igual hoje.

---

## Persistência

| Arquivo | Conteúdo | Quem escreve | Formato |
|---|---|---|---|
| `~/.ocorrencias_config.json` | API key Gemini, tema (`"dark"`/`"light"`), última pasta usada, geometria da janela | `ui/settings.py` | JSON |
| `~/.ocorrencias_history.json` | Lista append-only de execuções (cap 500, FIFO) | `ui/history.py` | JSON (lista de objetos) |
| `~/.ocorrencias_license.json` | (intacto — gerenciado por `license_client.py`) | — | — |

Todas as escritas são **atômicas**: escreve em `<path>.tmp` e usa `os.replace(tmp, path)`. Protege contra corrupção se o app for fechado durante o write.

**Schema de entrada do histórico:**

```json
{
  "timestamp": "2026-05-25T14:32:11",
  "tipo": "ocorrencias",
  "inputs": ["jornada_jan.pdf", "jornada_fev.pdf", "pedido_jan.xlsx"],
  "output": "pedido_jan_out.xlsx",
  "status": "ok",
  "duration_seconds": 12.4,
  "rows_processed": 187,
  "error": null
}
```

---

## Tema e identidade visual

Paleta GitHub-dark refinada (escolha do brainstorming):

| Token | Valor | Uso |
|---|---|---|
| `bg` | `#0d1117` | Fundo da janela |
| `surface` | `#161b22` | Cards, dropzones, tabela |
| `surface_alt` | `#21262d` | Botões secundários, hover |
| `border` | `#30363d` | Bordas, separadores |
| `fg` | `#c9d1d9` | Texto principal |
| `fg_bright` | `#f0f6fc` | Títulos |
| `fg_dim` | `#8b949e` | Labels, secundário |
| `success` | `#238636` | Botão "Processar", status ✔ |
| `success_hover` | `#2ea043` | Hover do verde |
| `accent` | `#58a6ff` | Links, info, dropzone ativa |
| `warning` | `#d29922` | Botão "Cancelar", status cancelado |
| `danger` | `#f85149` | Erros, status ✕ |

Tema claro é gerado pelo mesmo `theme.py` invertendo a polaridade dos tokens (paleta `light` separada). `theme.py` expõe:

```python
def qss_for(mode: Literal["dark", "light"]) -> str: ...
def apply_theme(app: QApplication, mode: Literal["dark", "light"]) -> None: ...
```

Fontes Inter (sans) e JetBrains Mono (mono) registradas via `QFontDatabase.addApplicationFont` na inicialização, lendo de `assets/fonts/` (caminho resolvido igual hoje, com `sys._MEIPASS` quando empacotado).

---

## Build e packaging

### `ProcessadorOcorrencias-v2.0.spec`

Diferenças versus [ProcessadorOcorrencias-v1.60.spec](../../../ProcessadorOcorrencias-v1.60.spec):

- `hiddenimports` adiciona `PySide6.QtCore`, `PySide6.QtGui`, `PySide6.QtWidgets` (e quaisquer outros módulos Qt usados — confirmar na implementação).
- `datas` continua incluindo `assets/fonts/*.ttf`.
- `excludes` adiciona `tkinter`, `_tkinter` — reduz tamanho do exe.
- `--onefile` mantido.
- Splash via `QSplashScreen` (não usa o splash do PyInstaller).

**Tamanho esperado:** ~80-110 MB (vs ~40 MB de v1.x). Aceitável pro caso de uso.

### `deploy.py`

Ajustes pontuais: aponta para `ProcessadorOcorrencias-v2.0.spec` e produz `ProcessadorOcorrencias-v2.0.exe`.

### `auto_update.py`

Uma string com o nome do exe muda. Protocolo com o servidor (manifest endpoint) não muda.

### `license_client.py`

`APP_VERSION = "2.0"`. Sem outras mudanças.

---

## Testes

### Cobertura existente

[conftest.py](../../../conftest.py) + pasta `tests/` cobrem a lógica de [processador.py](../../../processador.py) e [vt_caixa_processador.py](../../../vt_caixa_processador.py). Como esses módulos não mudam, **os testes existentes devem continuar passando sem alteração**. Confirmar na fase de plano.

### Novos testes

- **Módulos puros** (`ui/settings.py`, `ui/history.py`, `ui/theme.py`):
  - I/O atômico (escreve `.tmp`, `os.replace`, recupera de corrupção).
  - `history`: append, cap em 500 (FIFO), remoção por índice.
  - `theme`: gera QSS válido para `dark` e `light`; tokens corretos.
- **Camada Qt** (via `pytest-qt`):
  - Smoke test: cada aba constrói sem crashar.
  - Integração mínima: dropar arquivo na `DropZone` → estado vira READY → click no botão Processar → worker emite `finished` (com worker mockado).
- **Verificação manual obrigatória antes do release:** rodar o `.exe` empacotado em uma VM Windows limpa (sem Python instalado): bootstrap de licença, drop de PDFs reais, processar, abrir histórico, alternar tema, fechar e reabrir mantendo geometria.

### Dependências de teste

Novo arquivo `requirements-dev.txt`:

```
pytest>=8.0
pytest-qt>=4.4
```

---

## Plano de transição (big bang)

Sequência sugerida — a skill `writing-plans` vai detalhar cada passo:

1. Cria branch `v2-pyside6`. `main` (v1.60) continua recebendo bugfix se necessário.
2. Adiciona `PySide6>=6.7` em `requirements.txt`, cria `requirements-dev.txt` com `pytest-qt`.
3. Cria esqueleto de `ui/` (módulos vazios com TODO + `MainWindow` básica com 4 abas vazias). App roda, abre janela em branco.
4. Implementa `ui/theme.py` (paleta + QSS dark/light) e carregamento de fontes.
5. Implementa `ui/widgets/` (DropZone, LogPanel, PrimaryButton, SectionCard).
6. Implementa aba Ocorrências end-to-end com `QThread` worker, validando contra um PDF real.
7. Implementa aba VT-Caixa (inventariando primeiro os inputs de `ProcessadorVTCaixa`).
8. Implementa `ui/history.py` + aba Histórico.
9. Implementa `ui/settings.py` + aba Configurações + toggle dark/light em runtime.
10. Reescreve `ui/license_dialogs.py` em Qt; integra `ui/splash.py`; substitui [app.py](../../../app.py) pelo novo entrypoint.
11. Gera `ProcessadorOcorrencias-v2.0.spec`, ajusta `deploy.py` e `auto_update.py`; bump `APP_VERSION = "2.0"`.
12. Build, teste em VM Windows limpa, merge `v2-pyside6` → `main`.

Cada passo é um commit (ou poucos). Em caso de bug crítico durante a transição, `main` continua deployável a partir do código v1.x.

---

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Tamanho do exe dobra (~40 MB → ~100 MB) | Aceito como custo da migração; uso `excludes` (tkinter) pra mitigar. Auto-update se beneficia de delta updates se virar problema. |
| Conjunto de inputs do VT-Caixa não foi inventariado neste spec | Plano de implementação inclui passo específico de inventário antes de codar a aba. |
| `pytest-qt` em CI/Windows pode ter quirks com display | Smoke tests rodam com `QApplication([])` sem janela visível; se travar em CI, fallback é rodar só local. |
| Usuários acostumados com Tk podem estranhar mudanças visuais | Funcionalidade core (Processar) preserva fluxo: arquivo → arquivo → botão → log. Wizard numerado torna isso mais claro, não menos. |
| Remoção de "Deduzir dias" pode ser pedida de volta | Código removido fica no histórico Git; reintroduzir é viável se necessário. |

---

## Referências

- App atual (Tk): [app.py](../../../app.py) — 3609 linhas, ponto de partida.
- Lógica de processamento (intacta): [processador.py](../../../processador.py), [vt_caixa_processador.py](../../../vt_caixa_processador.py).
- Licença (intacta): [license_client.py](../../../license_client.py), `license-server/`.
- UI de licença a reescrever: [license_ui.py](../../../license_ui.py).
- Auto-update: [auto_update.py](../../../auto_update.py).
- Spec atual: [ProcessadorOcorrencias-v1.60.spec](../../../ProcessadorOcorrencias-v1.60.spec).
- Brainstormings anteriores no projeto: `docs/superpowers/specs/2026-04-29-dupla-verificacao-ocorrencias-design.md`, `docs/superpowers/specs/2026-05-19-validacao-acesso-servidor-design.md`.
