# Feedback visual durante a auto-atualização — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mostrar barra de progresso (% e MB) durante o download da auto-atualização e o status "reiniciando", sem que a UI congele.

**Architecture:** `auto_update.py` ganha callbacks opcionais (`on_progress`, `on_status`) e para de chamar `sys.exit` quando em modo callback. `app.py` roda `check_and_update` numa thread separada enquanto a thread principal (Tkinter) desenha o progresso na `SplashScreen`, que ganha uma barra de progresso opcional.

**Tech Stack:** Python 3.12, Tkinter, `requests`, `threading`, pytest.

**Rodar testes:** `python -m pytest tests/test_auto_update.py -v` (a partir da raiz do projeto; `conftest.py` já insere `tests/` no path).

---

## File Structure

- `auto_update.py` (modificar) — callbacks de progresso/status; leitura de `Content-Length`; supressão do `sys.exit` em modo callback. Continua **sem importar Tkinter**.
- `app.py` (modificar) — `main()` roda o update em thread + loop de desenho; `SplashScreen` ganha `set_progress`/`hide_progress`.
- `tests/test_auto_update.py` (criar) — testes das funções puras de `auto_update`.

Toda a lógica testável (progresso, callbacks, não-exit) fica em `auto_update.py`, isolada do Tkinter. A parte de UI (`SplashScreen`, threading no `main`) é validada manualmente.

---

## Task 1: `_download_and_relaunch` reporta progresso via callback

**Files:**
- Modify: `auto_update.py` (função `_download_and_relaunch`, linhas 48-128)
- Test: `tests/test_auto_update.py`

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_auto_update.py`:

```python
# tests/test_auto_update.py
import auto_update


class FakeResponse:
    """Simula um requests.Response usado como context manager + stream."""
    def __init__(self, chunks, content_length=None):
        self._chunks = chunks
        self.headers = {}
        if content_length is not None:
            self.headers['Content-Length'] = str(content_length)

    def __enter__(self): return self
    def __exit__(self, *a): pass
    def raise_for_status(self): pass
    def iter_content(self, chunk_size=65536):
        for c in self._chunks:
            yield c


def _patch_download(monkeypatch, response, tmp_path):
    """Faz requests.get devolver `response` e isola exit/subprocess/tempdir."""
    monkeypatch.setattr(auto_update.requests, 'get', lambda *a, **k: response)
    monkeypatch.setattr(auto_update.tempfile, 'mkdtemp', lambda: str(tmp_path))
    monkeypatch.setattr(auto_update.subprocess, 'Popen', lambda *a, **k: None)
    # sys.exit some é chamado no modo legado; intercepta para nao matar o teste
    def _no_exit(code=0):
        raise SystemExit(code)
    monkeypatch.setattr(auto_update.sys, 'exit', _no_exit)
    # sys.executable aponta para um caminho dentro de tmp_path (current_exe)
    monkeypatch.setattr(auto_update.sys, 'executable',
                        str(tmp_path / 'ProcessadorOcorrencias-v1.00.exe'))


def test_download_chama_on_progress_com_baixado_e_total(monkeypatch, tmp_path):
    chunks = [b'x' * 100, b'y' * 50]  # total 150 bytes
    resp = FakeResponse(chunks, content_length=150)
    _patch_download(monkeypatch, resp, tmp_path)

    eventos = []
    auto_update._download_and_relaunch(
        'novo.exe',
        on_progress=lambda baixado, total: eventos.append((baixado, total)),
        on_status=lambda estado: None,
    )

    assert eventos == [(100, 150), (150, 150)]
```

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `python -m pytest tests/test_auto_update.py::test_download_chama_on_progress_com_baixado_e_total -v`
Expected: FAIL — `_download_and_relaunch() got an unexpected keyword argument 'on_progress'`.

- [ ] **Step 3: Implementar — adicionar parâmetros e callback de progresso**

Em `auto_update.py`, alterar a assinatura e o laço de download de `_download_and_relaunch`. Substituir o trecho atual (linhas 48-65):

```python
def _download_and_relaunch(filename: str, on_progress=None, on_status=None) -> None:
    url = f"{SERVER_URL}/api/download/{filename}"
    logger.info("Baixando atualização: %s", url)

    current_exe = Path(sys.executable)
    target_exe = current_exe.parent / filename
    tmp_dir = Path(tempfile.mkdtemp())
    new_exe = tmp_dir / filename

    try:
        with requests.get(url, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length", 0) or 0)
            baixado = 0
            with open(new_exe, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
                    baixado += len(chunk)
                    if on_progress:
                        on_progress(baixado, total)
    except requests.RequestException as e:
        logger.warning("Falha ao baixar atualização: %s", e)
        return
```

(O restante da função — geração do `.bat` — permanece **inalterado por enquanto**; a Task 3 mexe no `sys.exit`.)

- [ ] **Step 4: Rodar o teste e ver passar**

Run: `python -m pytest tests/test_auto_update.py::test_download_chama_on_progress_com_baixado_e_total -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add auto_update.py tests/test_auto_update.py
git commit -m "feat: auto_update reporta progresso de download via callback"
```

---

## Task 2: Total = 0 quando o servidor não envia Content-Length

**Files:**
- Modify: `auto_update.py` (já feito na Task 1 — este teste valida o comportamento)
- Test: `tests/test_auto_update.py`

- [ ] **Step 1: Escrever o teste que falha**

Adicionar em `tests/test_auto_update.py`:

```python
def test_download_sem_content_length_reporta_total_zero(monkeypatch, tmp_path):
    chunks = [b'a' * 30]
    resp = FakeResponse(chunks, content_length=None)  # sem header
    _patch_download(monkeypatch, resp, tmp_path)

    eventos = []
    auto_update._download_and_relaunch(
        'novo.exe',
        on_progress=lambda baixado, total: eventos.append((baixado, total)),
        on_status=lambda estado: None,
    )

    assert eventos == [(30, 0)]
```

- [ ] **Step 2: Rodar o teste**

Run: `python -m pytest tests/test_auto_update.py::test_download_sem_content_length_reporta_total_zero -v`
Expected: PASS já na primeira vez (o `or 0` da Task 1 cobre o caso). Se passar, o comportamento está correto — seguir.

> Nota: este teste documenta um caminho já implementado na Task 1. Se ele falhar, revisar a leitura de `Content-Length` antes de prosseguir.

- [ ] **Step 3: Commit**

```bash
git add tests/test_auto_update.py
git commit -m "test: cobre download sem Content-Length (total=0)"
```

---

## Task 3: Modo callback não chama sys.exit; chama on_status("reiniciando")

**Files:**
- Modify: `auto_update.py` (final de `_download_and_relaunch`, linhas 126-128)
- Test: `tests/test_auto_update.py`

- [ ] **Step 1: Escrever o teste que falha**

Adicionar em `tests/test_auto_update.py`:

```python
def test_modo_callback_nao_chama_sys_exit_e_sinaliza_reiniciando(monkeypatch, tmp_path):
    resp = FakeResponse([b'z' * 10], content_length=10)
    _patch_download(monkeypatch, resp, tmp_path)

    estados = []
    # Se _download_and_relaunch chamar sys.exit, o _no_exit levanta SystemExit
    # e o teste falha — exatamente o que queremos detectar.
    auto_update._download_and_relaunch(
        'novo.exe',
        on_progress=lambda b, t: None,
        on_status=lambda estado: estados.append(estado),
    )

    assert estados == ["reiniciando"]


def test_modo_legado_sem_callbacks_chama_sys_exit(monkeypatch, tmp_path):
    resp = FakeResponse([b'z' * 10], content_length=10)
    _patch_download(monkeypatch, resp, tmp_path)

    import pytest
    with pytest.raises(SystemExit):
        auto_update._download_and_relaunch('novo.exe')
```

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `python -m pytest tests/test_auto_update.py::test_modo_callback_nao_chama_sys_exit_e_sinaliza_reiniciando -v`
Expected: FAIL com `SystemExit` (a função ainda chama `sys.exit(0)` sempre).

- [ ] **Step 3: Implementar — condicionar o sys.exit**

Em `auto_update.py`, substituir as 3 últimas linhas de `_download_and_relaunch` (atualmente):

```python
    logger.info("Relançando via updater.bat -> %s (log: %s)", target_exe, log_path)
    subprocess.Popen(["cmd", "/c", str(bat)], creationflags=subprocess.CREATE_NO_WINDOW)
    sys.exit(0)
```

por:

```python
    logger.info("Relançando via updater.bat -> %s (log: %s)", target_exe, log_path)
    subprocess.Popen(["cmd", "/c", str(bat)], creationflags=subprocess.CREATE_NO_WINDOW)
    if on_status:
        # Modo callback: a thread principal cuida de fechar a UI e encerrar o
        # processo após mostrar "reiniciando". sys.exit numa thread secundária
        # só encerraria a thread, não o processo.
        on_status("reiniciando")
        return
    sys.exit(0)
```

- [ ] **Step 4: Rodar os testes e ver passar**

Run: `python -m pytest tests/test_auto_update.py -v`
Expected: todos PASS (incluindo o teste do modo legado que ainda espera `SystemExit`).

- [ ] **Step 5: Commit**

```bash
git add auto_update.py tests/test_auto_update.py
git commit -m "feat: modo callback sinaliza reiniciando sem chamar sys.exit"
```

---

## Task 4: check_and_update repassa callbacks

**Files:**
- Modify: `auto_update.py` (função `check_and_update`, linhas 131-151)
- Test: `tests/test_auto_update.py`

- [ ] **Step 1: Escrever o teste que falha**

Adicionar em `tests/test_auto_update.py`:

```python
def test_check_and_update_repassa_callbacks(monkeypatch):
    # Força "é frozen" e versão nova disponível
    monkeypatch.setattr(auto_update, '_is_frozen', lambda: True)
    monkeypatch.setattr(auto_update, '_fetch_latest',
                        lambda: {"version": "9.99", "filename": "novo.exe"})
    monkeypatch.setattr(auto_update, '_current_version', lambda: "1.00")

    recebidos = {}
    def fake_download(filename, on_progress=None, on_status=None):
        recebidos['filename'] = filename
        recebidos['on_progress'] = on_progress
        recebidos['on_status'] = on_status
    monkeypatch.setattr(auto_update, '_download_and_relaunch', fake_download)

    prog = lambda b, t: None
    stat = lambda e: None
    auto_update.check_and_update(on_progress=prog, on_status=stat)

    assert recebidos['filename'] == "novo.exe"
    assert recebidos['on_progress'] is prog
    assert recebidos['on_status'] is stat
```

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `python -m pytest tests/test_auto_update.py::test_check_and_update_repassa_callbacks -v`
Expected: FAIL — `check_and_update() got an unexpected keyword argument 'on_progress'`.

- [ ] **Step 3: Implementar — assinatura e repasse**

Em `auto_update.py`, substituir a definição de `check_and_update` (linhas 131-151) por:

```python
def check_and_update(on_progress=None, on_status=None) -> None:
    """Verifica e aplica atualização. Chame antes de abrir a janela principal.

    on_progress(baixado:int, total:int) e on_status(estado:str) são opcionais;
    sem eles, mantém o comportamento legado (download síncrono + sys.exit).
    """
    if not _is_frozen():
        logger.debug("Não é executável — auto-update ignorado")
        return

    latest = _fetch_latest()
    if not latest:
        return

    latest_ver = latest.get("version", "0.0")
    filename = latest.get("filename")

    if not filename:
        return

    current = _current_version()
    if _parse_version(latest_ver) > _parse_version(current):
        logger.info("Atualização disponível: %s → %s", current, latest_ver)
        _download_and_relaunch(filename, on_progress=on_progress, on_status=on_status)
```

- [ ] **Step 4: Rodar a suíte e ver passar**

Run: `python -m pytest tests/test_auto_update.py -v`
Expected: todos PASS.

- [ ] **Step 5: Commit**

```bash
git add auto_update.py tests/test_auto_update.py
git commit -m "feat: check_and_update aceita e repassa callbacks de progresso"
```

---

## Task 5: SplashScreen ganha barra de progresso

**Files:**
- Modify: `app.py` (`SplashScreen`, ~linhas 3529-3607)

> UI Tkinter — sem teste automatizado (requer display). Validação manual no final.

- [ ] **Step 1: Adicionar widgets da barra no `__init__`**

Em `app.py`, logo após o bloco do `self._lbl_status` (que termina na linha `self._lbl_status.pack(side='left')`, ~3574), adicionar:

```python
        # Barra de progresso (escondida por padrão; usada só no download de update)
        self._PROG_W = 320
        self._PROG_H = 6
        self._prog_track = tk.Frame(self, bg=self._TRACK,
                                    width=self._PROG_W, height=self._PROG_H)
        self._prog_fill = tk.Frame(self._prog_track, bg=self._ACCENT,
                                   width=0, height=self._PROG_H)
        self._prog_fill.place(x=0, y=0)
        self._prog_visivel = False
```

(Não dar `pack` no `_prog_track` aqui — ele aparece só em `set_progress`.)

- [ ] **Step 2: Adicionar os métodos `set_progress` e `hide_progress`**

Em `app.py`, logo após o método `set_status` (que termina em `self.update()`, ~linha 3602), adicionar:

```python
    def set_progress(self, frac, texto):
        """Mostra/atualiza a barra de progresso. frac em 0.0–1.0; texto no status.
        frac=None => modo indeterminado (barra cheia, sem proporção)."""
        if not self._prog_visivel:
            self._prog_track.pack(pady=(14, 0))
            self._prog_track.pack_propagate(False)
            self._prog_visivel = True
        if frac is None:
            largura = self._PROG_W
        else:
            frac = max(0.0, min(1.0, frac))
            largura = int(self._PROG_W * frac)
        self._prog_fill.configure(width=largura)
        self._lbl_status.configure(text=texto)
        self.update()

    def hide_progress(self):
        if self._prog_visivel:
            self._prog_track.pack_forget()
            self._prog_visivel = False
```

- [ ] **Step 3: Verificar sintaxe**

Run: `python -c "import ast; ast.parse(open('app.py', encoding='utf-8').read()); print('OK')"`
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: SplashScreen com barra de progresso opcional"
```

---

## Task 6: main() roda update em thread e desenha o progresso

**Files:**
- Modify: `app.py` (`main()`, ~linhas 3621-3655)

> Threading + Tkinter — sem teste automatizado. Validação manual no final.

- [ ] **Step 1: Substituir o bloco de atualização em `main()`**

Em `app.py`, substituir o trecho atual (linhas ~3627-3631):

```python
    # 1. Verificar e aplicar atualização
    splash.set_status("Procurando atualizações...")
    t0 = time.monotonic()
    check_and_update()
    _splash_wait(splash, int((time.monotonic() - t0) * 1000), min_ms=1200)
```

por:

```python
    # 1. Verificar e aplicar atualização (download em thread; UI responsiva)
    import threading

    splash.set_status("Procurando atualizações...")
    prog = {"baixado": 0, "total": 0, "estado": "verificando"}

    def _on_progress(baixado, total):
        prog["baixado"] = baixado
        prog["total"] = total
        prog["estado"] = "baixando"

    def _on_status(estado):
        prog["estado"] = estado

    th = threading.Thread(
        target=check_and_update,
        kwargs={"on_progress": _on_progress, "on_status": _on_status},
        daemon=True,
    )
    t0 = time.monotonic()
    th.start()

    while th.is_alive():
        if prog["estado"] == "baixando":
            total = prog["total"]
            mb_b = prog["baixado"] / (1024 * 1024)
            if total > 0:
                frac = prog["baixado"] / total
                mb_t = total / (1024 * 1024)
                splash.set_progress(frac, f"Baixando atualização... {int(frac*100)}% — {mb_b:.1f} / {mb_t:.1f} MB")
            else:
                splash.set_progress(None, f"Baixando atualização... {mb_b:.1f} MB")
        splash.update()
        splash.after(30)

    # Atualização aplicada: a thread sinalizou "reiniciando" — fecha e encerra.
    if prog["estado"] == "reiniciando":
        splash.set_progress(1.0, "Atualização concluída — reiniciando...")
        _splash_wait(splash, 0, min_ms=1000)
        splash.fechar()
        sys.exit(0)

    splash.hide_progress()
    _splash_wait(splash, int((time.monotonic() - t0) * 1000), min_ms=1200)
```

- [ ] **Step 2: Verificar sintaxe e import de `sys`**

`sys` já é importado no topo de `main()` (`import sys, time` na primeira linha da função). Confirmar:

Run: `python -c "import ast; ast.parse(open('app.py', encoding='utf-8').read()); print('OK')"`
Expected: `OK`.

- [ ] **Step 3: Smoke test do import (não-frozen ignora update)**

Run: `python -c "import app; print('import OK')"`
Expected: `import OK` (em ambiente não-frozen, `check_and_update` retorna cedo; nada baixa).

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: download de atualizacao em thread com barra de progresso na splash"
```

---

## Task 7: Tratamento de erro de download (não trava)

**Files:**
- Modify: `app.py` (`main()` — o loop da Task 6)
- Modify: `auto_update.py` (`_download_and_relaunch` — sinalizar erro)

- [ ] **Step 1: Sinalizar erro no callback ao falhar o download**

Em `auto_update.py`, no `except requests.RequestException` de `_download_and_relaunch` (adicionado na Task 1), trocar:

```python
    except requests.RequestException as e:
        logger.warning("Falha ao baixar atualização: %s", e)
        return
```

por:

```python
    except requests.RequestException as e:
        logger.warning("Falha ao baixar atualização: %s", e)
        if on_status:
            on_status("erro")
        return
```

- [ ] **Step 2: Tratar "erro" no `main()`**

Em `app.py`, no bloco da Task 6, logo antes de `splash.hide_progress()`, inserir:

```python
    if prog["estado"] == "erro":
        splash.set_status("Não foi possível atualizar, continuando...")
        _splash_wait(splash, 0, min_ms=1200)
```

- [ ] **Step 3: Verificar sintaxe**

Run: `python -c "import ast; ast.parse(open('app.py', encoding='utf-8').read()); print('OK')" && python -c "import ast; ast.parse(open('auto_update.py', encoding='utf-8').read()); print('OK')"`
Expected: `OK` / `OK`.

- [ ] **Step 4: Rodar a suíte completa**

Run: `python -m pytest tests/test_auto_update.py -v`
Expected: todos PASS (o teste de erro não foi alterado; o `on_status("erro")` não afeta os testes existentes pois nenhum simula falha de rede ainda).

- [ ] **Step 5: Commit**

```bash
git add app.py auto_update.py
git commit -m "feat: download com falha mostra aviso e abre na versao atual"
```

---

## Task 8: Verificação final e validação manual

- [ ] **Step 1: Suíte completa do projeto**

Run: `python -m pytest -q`
Expected: os testes novos de `test_auto_update.py` passam; nenhum teste pré-existente quebra. (Nota: `test_processador_verificacao.py::test_verificar_com_ia_parseia_json_valido` já falha por incompatibilidade do pacote `google.generativeai`, **não relacionada** a esta mudança.)

- [ ] **Step 2: Build do exe**

Run: `python -m PyInstaller --noconfirm ProcessadorOcorrencias-v1.62.spec`
Expected: `dist/ProcessadorOcorrencias-v1.62.exe` gerado, exit 0.

- [ ] **Step 3: Validação manual da barra (requer 2 versões)**

Para ver a barra de verdade é preciso o servidor anunciar uma versão maior que a do exe local. Opções:
- Rodar um exe com `APP_VERSION` antiga contra a VPS atual (que serve a versão nova), ou
- Validar visualmente apenas o desenho da barra abrindo a splash isolada num script de teste manual.

Conferir: spinner continua girando durante o download; barra enche; texto mostra "% — X / Y MB"; ao concluir aparece "Atualização concluída — reiniciando..." por ~1s; app reabre atualizado.

- [ ] **Step 4: Commit final (se houve ajuste no spec do build)**

```bash
git add -A
git commit -m "chore: ajustes finais feedback auto-update"
```

---

## Self-Review

**Cobertura do spec:**
- Barra com % e MB → Task 5 (widget) + Task 6 (texto/cálculo). ✓
- UI não congela (thread) → Task 6. ✓
- "Reiniciando..." antes de fechar → Task 3 (sinal) + Task 6 (exibição ~1s + exit na thread principal). ✓
- Sem update → barra nunca aparece → Task 6 (`hide_progress`, barra só em estado "baixando"). ✓
- `sys.exit` em thread secundária tratado → Task 3 + Task 6. ✓
- Retrocompat sem callbacks → Task 3 (`test_modo_legado...`) + Task 4. ✓
- Content-Length ausente → Task 2. ✓
- Erro de download não trava → Task 7. ✓
- Testes do auto_update → Tasks 1-4, 7. ✓

**Placeholder scan:** sem TBD/TODO; todo passo de código mostra o código.

**Consistência de tipos/nomes:** `on_progress(baixado, total)`, `on_status(estado)`, estados `"baixando"`/`"reiniciando"`/`"erro"`, métodos `set_progress(frac, texto)`/`hide_progress()` — usados de forma consistente entre `auto_update.py`, `main()` e `SplashScreen`.
