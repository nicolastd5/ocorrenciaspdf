# Feedback visual durante a auto-atualização

**Data:** 2026-05-27
**Status:** Aprovado para implementação

## Problema

Ao abrir o programa, `main()` chama `check_and_update()` (em [auto_update.py](../../../auto_update.py)) antes da janela principal. Quando há versão nova, `_download_and_relaunch` baixa o `.exe` (~45 MB) de forma **síncrona** na thread principal do Tkinter (`requests.get(...).iter_content(...)`).

Durante esse download a thread principal fica bloqueada: o `after(30)` que anima o spinner da `SplashScreen` nunca dispara, o spinner **congela** e o status fica preso em "Procurando atualizações...". O usuário vê uma tela travada por vários segundos até o app relançar atualizado, sem saber que algo está sendo baixado.

## Objetivo

Exibir feedback real de progresso durante o download (barra + porcentagem + MB baixados) mantendo a UI responsiva, e indicar o relançamento ("reiniciando...") antes de fechar.

## Decisões de design

- **Feedback:** barra de progresso com porcentagem **e** MB baixados. Ex.: `Baixando atualização... 45% — 20.3 / 45.0 MB`.
- **Pós-download (100%):** mostrar `Atualização concluída — reiniciando...` por ~1s antes de fechar a splash, para o usuário entender que o app vai reabrir sozinho.
- **Sem atualização disponível:** a barra nunca aparece; o fluxo segue direto para "Validando licença..." como hoje.

## Arquitetura

A causa da "trava" é o download síncrono na thread de UI. A correção é mover o download para uma **thread separada**, enquanto a thread principal (Tkinter) continua seu loop de eventos desenhando o progresso.

Tkinter não é thread-safe: **somente a thread principal toca a UI**. A thread de download apenas grava números numa estrutura de progresso compartilhada; a thread principal lê esses números e redesenha.

### 1. `auto_update.py` — desacoplar do Tkinter via callback

- `check_and_update(on_progress=None, on_status=None)` — dois callbacks opcionais.
  - `on_progress(baixado: int, total: int)` — chamado a cada chunk durante o download. `total` é 0 quando o servidor não envia `Content-Length`.
  - `on_status(estado: str)` — chamado com `"reiniciando"` imediatamente antes de relançar.
- `_download_and_relaunch(filename, on_progress=None, on_status=None)`:
  - Lê `Content-Length` do response para obter o total.
  - A cada chunk escrito, acumula bytes e chama `on_progress(baixado, total)` se fornecido.
  - Antes do `subprocess.Popen`/`sys.exit(0)`, chama `on_status("reiniciando")` se fornecido.
- **Retrocompatibilidade:** sem callbacks, o comportamento é idêntico ao atual. O módulo continua **sem importar Tkinter**.
- O `chunk_size` atual (65536) é mantido; isso dá ~720 callbacks para 45 MB — granularidade suficiente, custo desprezível.

### 2. `app.py` `main()` — download fora da thread de UI

- Estrutura de progresso compartilhada (um `dict` mutável ou dataclass simples): `{baixado, total, estado, terminou}`.
- `on_progress`/`on_status` apenas atualizam essa estrutura (thread-safe para tipos simples em CPython; não desenham nada).
- `check_and_update(...)` roda numa `threading.Thread(daemon=True)`.
- A thread principal entra num loop `while thread.is_alive()` que: lê a estrutura, chama `splash.set_progress(...)` ou `splash.set_status(...)`, depois `splash.update()` + `splash.after(30)`. Isso mantém spinner e barra animados.
- Caso especial do relançamento: quando o download foi aplicado, `_download_and_relaunch` chama `sys.exit(0)` **dentro da thread**. `sys.exit` numa thread secundária só encerra a thread, não o processo. Portanto:
  - `on_status("reiniciando")` sinaliza `estado="reiniciando"` na estrutura.
  - O `subprocess.Popen` do `.bat` (que espera o PID encerrar) é disparado pela thread; o encerramento real do processo principal passa a ser responsabilidade da thread principal: ao detectar `estado == "reiniciando"`, ela mostra "Atualização concluída — reiniciando...", aguarda ~1s, fecha a splash e chama `sys.exit(0)` na thread principal.
  - Para isso, `_download_and_relaunch` **não** deve chamar `sys.exit(0)` quando rodando com callbacks — ele apenas dispara o `.bat` e sinaliza via `on_status`. Sem callbacks (modo legado), mantém o `sys.exit(0)` como hoje.

### 3. `SplashScreen` — barra de progresso opcional

- Novo widget de barra (um `Frame` track + um `Frame` fill cuja largura é `frac * largura_track`, ou um `Canvas` com retângulo), criado escondido (`pack_forget`).
- `set_progress(frac: float, texto: str)`:
  - Mostra a barra (se escondida), ajusta o preenchimento para `frac` (0.0–1.0), atualiza o `_lbl_status` com `texto`, chama `self.update()`.
  - Quando `total == 0` (sem Content-Length), `frac` indeterminado: a barra fica em modo "cheia/animada" ou oculta, e o texto mostra só os MB (`Baixando atualização... 20.3 MB`).
- `hide_progress()`: esconde a barra (`pack_forget`) e volta ao layout padrão.
- A barra só aparece durante o download; nas etapas de licença e carregamento permanece escondida — layout idêntico ao atual.

## Fluxo

```
splash "Procurando atualizações..."
  ├─ sem update → segue para "Validando licença..." (barra nunca aparece)
  └─ com update:
       thread baixa em background; thread principal desenha:
         "Baixando atualização... X% — Y / Z MB"   (spinner gira, barra enche)
       → 100% → estado "reiniciando"
       → "Atualização concluída — reiniciando..." (~1s)
       → splash fecha, processo encerra, .bat relança → app abre atualizado
```

## Tratamento de erros

- Download falha no meio (rede cai): `_download_and_relaunch` já captura `requests.RequestException` e retorna sem relançar. Acrescentar: sinalizar `estado="erro"` para a thread principal mostrar brevemente "Não foi possível atualizar, continuando..." e o app abrir na versão atual — nunca travar.
- Falha ao mover o exe (Defender): já tratada pelo `.bat` com retry e `msg *`. Fora do escopo desta mudança.

## Testes (TDD)

`auto_update` é testável sem display (mockando `requests.get`):

1. `on_progress` é chamado com `(baixado, total)` crescentes e `total` = `Content-Length`.
2. Sem callbacks, o download funciona como antes (não levanta exceção, escreve o arquivo).
3. `Content-Length` ausente → `total == 0` repassado ao callback, sem quebrar.
4. Com callbacks, `_download_and_relaunch` chama `on_status("reiniciando")` e **não** chama `sys.exit` (o `subprocess.Popen` é mockado).
5. `check_and_update` repassa os callbacks a `_download_and_relaunch` quando há versão nova.

A integração visual com `SplashScreen` é validada manualmente (Tkinter requer display).

## Arquivos afetados

- [auto_update.py](../../../auto_update.py) — callbacks, leitura de Content-Length, não-exit em modo callback.
- [app.py](../../../app.py) — `main()` (thread + loop de desenho), `SplashScreen` (`set_progress`/`hide_progress`).
- `tests/test_auto_update.py` — novo arquivo de testes.

## Fora de escopo

- Mudar a lógica do `.bat` updater (mover/retry/Defender) — funciona e não é a causa do travamento.
- Verificação de integridade (hash) do exe baixado.
- Atualização em background com o app já aberto (continua sendo no startup).
