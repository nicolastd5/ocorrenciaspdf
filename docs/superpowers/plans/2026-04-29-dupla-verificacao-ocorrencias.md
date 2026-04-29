# Dupla Verificação + IA em Ocorrências — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar dupla varredura independente do PDF e verificação opcional via Gemini Vision ao processamento de ocorrências, com resolução manual de conflitos antes de gravar.

**Architecture:** O `processador.py` ganha dois novos métodos de extração (`extrair_ocorrencias_texto` via regex e `verificar_com_ia` via Gemini Vision) e um método `reconciliar` que compara os resultados das camadas ativas. O `app.py` recebe um card de seleção de modo de verificação, uma janela modal de conflitos e um bloco de resumo da verificação — sem quebrar o fluxo atual de varredura única.

**Tech Stack:** Python 3.14, pdfplumber, pypdfium2 (já no projeto), google-generativeai (já no projeto), tkinter

---

## Mapa de arquivos

| Arquivo | Ação | Responsabilidade |
|---------|------|-----------------|
| `processador.py` | Modificar | Adicionar `extrair_ocorrencias_texto`, `verificar_com_ia`, `reconciliar` |
| `app.py` | Modificar | Card de verificação, janela de conflitos, bloco de resumo, etapas de progresso |
| `tests/test_processador_verificacao.py` | Criar | Testes unitários para os três novos métodos |

---

## Task 1: `extrair_ocorrencias_texto` — segunda varredura via regex

**Files:**
- Modify: `processador.py` (após o método `extrair_ocorrencias`)
- Create: `tests/test_processador_verificacao.py`

- [ ] **Step 1: Criar arquivo de testes e escrever o teste que falha**

```python
# tests/test_processador_verificacao.py
import pytest
from processador import ProcessadorOcorrencias

proc = ProcessadorOcorrencias()

class FakePage:
    """Simula uma página do pdfplumber com extract_text()."""
    def __init__(self, text):
        self._text = text
    def extract_text(self):
        return self._text

class FakePDF:
    def __init__(self, pages):
        self.pages = pages
    def __enter__(self): return self
    def __exit__(self, *a): pass


def test_extrair_ocorrencias_texto_basico(monkeypatch):
    texto = (
        "SILVA JOAO          12345  ... AT AT FA\n"
        "SOUZA MARIA         67890  ... AT AT AT\n"
    )
    import pdfplumber

    class FakePDF2:
        pages = [FakePage(texto)]
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr(pdfplumber, 'open', lambda path: FakePDF2())
    resultado = proc.extrair_ocorrencias_texto('fake.pdf', ['AT', 'FA'])

    assert '12345' in resultado
    assert resultado['12345']['ocorrencias']['AT'] == 2
    assert resultado['12345']['ocorrencias']['FA'] == 1
    assert '67890' in resultado
    assert resultado['67890']['ocorrencias']['AT'] == 3


def test_extrair_ocorrencias_texto_sem_ocorrencias(monkeypatch):
    import pdfplumber

    class FakePDF2:
        pages = [FakePage("SILVA JOAO  12345  SD SD\n")]
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr(pdfplumber, 'open', lambda path: FakePDF2())
    resultado = proc.extrair_ocorrencias_texto('fake.pdf', ['AT'])
    assert resultado == {}
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

```bash
cd /c/Users/apoio/OneDrive/Documentos/ocorrenciaspdf
.venv/Scripts/pytest tests/test_processador_verificacao.py -v
```
Esperado: `AttributeError: 'ProcessadorOcorrencias' object has no attribute 'extrair_ocorrencias_texto'`

- [ ] **Step 3: Implementar `extrair_ocorrencias_texto` em `processador.py`**

Adicionar após o método `extrair_ocorrencias` (linha ~81):

```python
def extrair_ocorrencias_texto(self, pdf_path, codigos_alvo):
    """
    Segunda varredura: extrai ocorrências via extract_text() + regex posicional.
    Independente de detecção de tabelas. Mesmo formato de retorno que
    extrair_ocorrencias: {re: {'nome': str, 'ocorrencias': {codigo: contagem}}}
    """
    import re as _re
    resultados = {}
    codigos_set = set(codigos_alvo)
    # RE: 5+ dígitos no início ou após espaços, precedido de nome
    re_linha = _re.compile(r'^(.+?)\s{2,}(\d{5,})\b')

    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if not texto:
                continue
            for linha in texto.splitlines():
                m = re_linha.match(linha.strip())
                if not m:
                    continue
                nome = m.group(1).strip()
                codigo_re = m.group(2).strip()
                tokens = linha.split()
                ocorrencias = {}
                for tok in tokens:
                    tok_clean = tok.strip()
                    if tok_clean in codigos_set:
                        ocorrencias[tok_clean] = ocorrencias.get(tok_clean, 0) + 1
                if ocorrencias:
                    if codigo_re not in resultados:
                        resultados[codigo_re] = {'nome': nome, 'ocorrencias': {}}
                    for k, v in ocorrencias.items():
                        resultados[codigo_re]['ocorrencias'][k] = (
                            resultados[codigo_re]['ocorrencias'].get(k, 0) + v
                        )
    return resultados
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

```bash
.venv/Scripts/pytest tests/test_processador_verificacao.py::test_extrair_ocorrencias_texto_basico tests/test_processador_verificacao.py::test_extrair_ocorrencias_texto_sem_ocorrencias -v
```
Esperado: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add processador.py tests/test_processador_verificacao.py
git commit -m "feat: adicionar extrair_ocorrencias_texto (segunda varredura via regex)"
```

---

## Task 2: `reconciliar` — comparar camadas e detectar conflitos

**Files:**
- Modify: `processador.py`
- Modify: `tests/test_processador_verificacao.py`

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao final de `tests/test_processador_verificacao.py`:

```python
def test_reconciliar_sem_conflito():
    v1 = {'12345': {'nome': 'SILVA', 'ocorrencias': {'AT': 2, 'FA': 1}}}
    v2 = {'12345': {'nome': 'SILVA', 'ocorrencias': {'AT': 2, 'FA': 1}}}
    resultado = proc.reconciliar([v1, v2], ['AT', 'FA'])
    assert '12345' in resultado['concordantes']
    assert resultado['conflitos'] == []


def test_reconciliar_com_conflito():
    v1 = {'12345': {'nome': 'SILVA', 'ocorrencias': {'AT': 2}}}
    v2 = {'12345': {'nome': 'SILVA', 'ocorrencias': {'AT': 1}}}
    resultado = proc.reconciliar([v1, v2], ['AT'])
    assert resultado['concordantes'] == {}
    assert len(resultado['conflitos']) == 1
    c = resultado['conflitos'][0]
    assert c['re'] == '12345'
    assert c['codigo'] == 'AT'
    assert c['valores']['v1'] == 2
    assert c['valores']['v2'] == 1
    assert c['sugestao'] == 2  # v1 e v2 empatam → usa o maior


def test_reconciliar_maioria_vence():
    v1 = {'12345': {'nome': 'SILVA', 'ocorrencias': {'AT': 2}}}
    v2 = {'12345': {'nome': 'SILVA', 'ocorrencias': {'AT': 1}}}
    ia = {'12345': {'nome': 'SILVA', 'ocorrencias': {'AT': 2}}}
    resultado = proc.reconciliar([v1, v2, ia], ['AT'])
    # 2 votos em AT=2, 1 voto em AT=1 → sugestao=2 e sem conflito (maioria clara)
    assert '12345' in resultado['concordantes']
    assert resultado['concordantes']['12345']['ocorrencias']['AT'] == 2
    assert resultado['conflitos'] == []


def test_reconciliar_re_ausente_em_uma_camada():
    # RE presente na V1 mas não na V2 → conflito com v2=0
    v1 = {'12345': {'nome': 'SILVA', 'ocorrencias': {'AT': 1}}}
    v2 = {}
    resultado = proc.reconciliar([v1, v2], ['AT'])
    assert len(resultado['conflitos']) == 1
    c = resultado['conflitos'][0]
    assert c['valores']['v1'] == 1
    assert c['valores']['v2'] == 0
```

- [ ] **Step 2: Rodar para confirmar que falham**

```bash
.venv/Scripts/pytest tests/test_processador_verificacao.py::test_reconciliar_sem_conflito tests/test_processador_verificacao.py::test_reconciliar_com_conflito tests/test_processador_verificacao.py::test_reconciliar_maioria_vence tests/test_processador_verificacao.py::test_reconciliar_re_ausente_em_uma_camada -v
```
Esperado: 4 FAILED com `AttributeError`

- [ ] **Step 3: Implementar `reconciliar` em `processador.py`**

Adicionar após `extrair_ocorrencias_texto`:

```python
def reconciliar(self, resultados, codigos_alvo):
    """
    Compara resultados de 2 ou 3 camadas de extração.

    Args:
        resultados: lista de dicts no formato {re: {'nome', 'ocorrencias'}}
                    Ordem: [v1, v2] ou [v1, v2, ia]
    Returns:
        {
          'concordantes': {re: {'nome', 'ocorrencias'}},
          'conflitos': [{re, nome, codigo, valores, sugestao}]
        }
    """
    from collections import Counter

    nomes = ['v1', 'v2', 'ia']
    camadas = resultados  # lista de dicts

    # Todos os REs presentes em qualquer camada
    todos_res = set()
    for c in camadas:
        todos_res.update(c.keys())

    concordantes = {}
    conflitos = []

    for re_val in todos_res:
        # Nome: pegar do primeiro que tiver
        nome = next(
            (c[re_val]['nome'] for c in camadas if re_val in c), ''
        )

        # Todos os códigos que aparecem em qualquer camada para este RE
        todos_codigos = set()
        for c in camadas:
            if re_val in c:
                todos_codigos.update(c[re_val]['ocorrencias'].keys())
        todos_codigos = todos_codigos.intersection(set(codigos_alvo))

        re_conflitos = []
        ocorrencias_finais = {}

        for cod in todos_codigos:
            valores_por_camada = {}
            for i, c in enumerate(camadas):
                chave = nomes[i]
                val = c.get(re_val, {}).get('ocorrencias', {}).get(cod, 0)
                valores_por_camada[chave] = val

            vals = list(valores_por_camada.values())
            counter = Counter(vals)
            valor_majoritario, votos = counter.most_common(1)[0]

            todos_iguais = len(set(vals)) == 1
            maioria_clara = votos > len(camadas) / 2

            if todos_iguais or maioria_clara:
                ocorrencias_finais[cod] = valor_majoritario
            else:
                # Empate sem maioria: sugestao = maior valor
                sugestao = max(vals)
                re_conflitos.append({
                    're': re_val,
                    'nome': nome,
                    'codigo': cod,
                    'valores': valores_por_camada,
                    'sugestao': sugestao,
                })

        if re_conflitos:
            conflitos.extend(re_conflitos)
        else:
            if ocorrencias_finais:
                concordantes[re_val] = {'nome': nome, 'ocorrencias': ocorrencias_finais}

    return {'concordantes': concordantes, 'conflitos': conflitos}
```

- [ ] **Step 4: Rodar os testes**

```bash
.venv/Scripts/pytest tests/test_processador_verificacao.py -v
```
Esperado: todos PASSED

- [ ] **Step 5: Commit**

```bash
git add processador.py tests/test_processador_verificacao.py
git commit -m "feat: adicionar reconciliar (comparação de camadas com detecção de conflitos)"
```

---

## Task 3: `verificar_com_ia` — terceira camada Gemini Vision

**Files:**
- Modify: `processador.py`
- Modify: `tests/test_processador_verificacao.py`

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao final de `tests/test_processador_verificacao.py`:

```python
def test_verificar_com_ia_retorna_none_sem_api_key(monkeypatch):
    resultado = proc.verificar_com_ia('fake.pdf', ['AT', 'FA'], api_key='', modelo='gemini-1.5-flash')
    assert resultado is None


def test_verificar_com_ia_retorna_none_em_erro(monkeypatch):
    import pypdfium2 as pdfium

    monkeypatch.setattr(pdfium, 'PdfDocument', lambda path: (_ for _ in ()).throw(Exception("pdf error")))
    resultado = proc.verificar_com_ia('fake.pdf', ['AT'], api_key='fake-key', modelo='gemini-1.5-flash')
    assert resultado is None


def test_verificar_com_ia_parseia_json_valido(monkeypatch):
    import pypdfium2 as pdfium
    import google.generativeai as genai

    resposta_json = '[{"re": "12345", "nome": "SILVA", "ocorrencias": {"AT": 2, "FA": 1}}]'

    class FakeResponse:
        text = resposta_json

    class FakeModel:
        def generate_content(self, parts): return FakeResponse()

    class FakePage:
        def render(self, scale): return self
        def to_pil(self): 
            from PIL import Image
            return Image.new('RGB', (10, 10))

    class FakeDoc:
        def __len__(self): return 1
        def __getitem__(self, i): return FakePage()
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr(pdfium, 'PdfDocument', lambda path: FakeDoc())
    monkeypatch.setattr(genai, 'configure', lambda **kw: None)
    monkeypatch.setattr(genai, 'GenerativeModel', lambda model: FakeModel())

    resultado = proc.verificar_com_ia('fake.pdf', ['AT', 'FA'], api_key='fake-key', modelo='gemini-1.5-flash')
    assert resultado is not None
    assert '12345' in resultado
    assert resultado['12345']['ocorrencias']['AT'] == 2
```

- [ ] **Step 2: Rodar para confirmar que falham**

```bash
.venv/Scripts/pytest tests/test_processador_verificacao.py::test_verificar_com_ia_retorna_none_sem_api_key tests/test_processador_verificacao.py::test_verificar_com_ia_retorna_none_em_erro tests/test_processador_verificacao.py::test_verificar_com_ia_parseia_json_valido -v
```
Esperado: 3 FAILED com `AttributeError`

- [ ] **Step 3: Implementar `verificar_com_ia` em `processador.py`**

Adicionar após `reconciliar`:

```python
def verificar_com_ia(self, pdf_path, codigos_alvo, api_key, modelo):
    """
    Terceira camada opcional: Gemini Vision re-extrai ocorrências a partir
    de imagens das páginas do PDF.

    Returns:
        dict no formato {re: {'nome', 'ocorrencias'}} ou None em caso de erro.
    """
    if not api_key:
        return None

    try:
        import pypdfium2 as pdfium
        import google.generativeai as genai
        import json as _json

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(modelo)

        codigos_str = ', '.join(codigos_alvo)
        prompt = (
            f"Analise esta folha de ponto. Para cada linha que contenha um RE numérico "
            f"(número de matrícula com 5+ dígitos), identifique o RE, o nome do funcionário "
            f"e a contagem de cada código de ocorrência presente na linha. "
            f"Códigos a procurar: {codigos_str}. "
            f"Responda APENAS em JSON válido, sem markdown, no formato: "
            f'[{{"re": "12345", "nome": "NOME", "ocorrencias": {{"AT": 2, "FA": 1}}}}]'
        )

        doc = pdfium.PdfDocument(pdf_path)
        resultados = {}

        for i in range(len(doc)):
            page = doc[i]
            bitmap = page.render(scale=2)
            img = bitmap.to_pil()

            response = model.generate_content([prompt, img])
            raw = response.text.strip()

            # Remover blocos markdown se presentes
            if raw.startswith('```'):
                raw = raw.split('```')[1]
                if raw.startswith('json'):
                    raw = raw[4:]
                raw = raw.strip()

            try:
                registros = _json.loads(raw)
            except _json.JSONDecodeError:
                continue

            for reg in registros:
                re_val = str(reg.get('re', '')).strip()
                nome = str(reg.get('nome', '')).strip()
                ocorr = reg.get('ocorrencias', {})
                if not re_val:
                    continue
                if re_val not in resultados:
                    resultados[re_val] = {'nome': nome, 'ocorrencias': {}}
                for cod, cnt in ocorr.items():
                    if cod in set(codigos_alvo):
                        resultados[re_val]['ocorrencias'][cod] = (
                            resultados[re_val]['ocorrencias'].get(cod, 0) + int(cnt)
                        )

        return resultados if resultados else {}

    except Exception:
        return None
```

- [ ] **Step 4: Rodar os testes**

```bash
.venv/Scripts/pytest tests/test_processador_verificacao.py -v
```
Esperado: todos PASSED

- [ ] **Step 5: Commit**

```bash
git add processador.py tests/test_processador_verificacao.py
git commit -m "feat: adicionar verificar_com_ia (Gemini Vision terceira camada)"
```

---

## Task 4: Card de verificação na UI (`app.py`)

**Files:**
- Modify: `app.py` — método `__init__`, `_criar_aba_processar`

- [ ] **Step 1: Adicionar variáveis de estado no `__init__`**

Em `app.py`, no `__init__`, após a linha `self.qt_vt_var = tk.BooleanVar(value=True)` (linha ~108), adicionar:

```python
        # Modo de verificação: 'unica', 'dupla', 'ia'
        self.modo_verificacao = tk.StringVar(value='unica')
        self.verif_api_key = tk.StringVar(value='')
        self.verif_modelo = tk.StringVar(value='')
        self._verif_api_row = None
```

Também no `__init__`, após o bloco de carregamento de config do VT Caixa (que já carrega `_cfg`), carregar as preferências salvas de verificação:

```python
        _cfg_v = _carregar_config()
        self.verif_api_key.set(_cfg_v.get('gemini_api_key_ocorrencias', ''))
        self.verif_modelo.set(_cfg_v.get('gemini_modelo_ocorrencias', ''))
```

- [ ] **Step 2: Adicionar card de verificação em `_criar_aba_processar`**

Em `_criar_aba_processar`, logo após o bloco que termina com `codes_grid.columnconfigure(col, weight=1)` e antes do card de Opções, inserir:

```python
        # ── Card Verificação ────────────────────────────────────────
        verif_frame = self._criar_card(parent, "🔍  Verificação")

        modo_row = tk.Frame(verif_frame, bg=CORES['bg_card'])
        modo_row.pack(fill='x', pady=(0, 6))

        modos = [
            ('unica',  'Varredura única',    'Comportamento atual'),
            ('dupla',  'Dupla varredura',    'V1 (tabelas) + V2 (texto/regex)'),
            ('ia',     'Dupla + IA (Gemini)','V1 + V2 + Gemini Vision'),
        ]

        def _atualizar_modo():
            modo = self.modo_verificacao.get()
            if modo == 'ia':
                self._verif_api_row.pack(fill='x', pady=(6, 0))
            else:
                self._verif_api_row.pack_forget()
            for m, btn in _modo_btns.items():
                on = (m == modo)
                btn.configure(
                    bg=CORES['chip_on'] if on else CORES['chip_off'],
                    fg=CORES['accent_light'] if on else CORES['fg_dim'],
                    highlightbackground=CORES['chip_border_on'] if on else CORES['chip_border_off'],
                )

        _modo_btns = {}
        for val, label, tooltip in modos:
            btn = tk.Label(
                modo_row, text=label,
                font=("Segoe UI", 9, "bold"),
                fg=CORES['fg_dim'], bg=CORES['chip_off'],
                padx=12, pady=5, cursor='hand2',
                highlightbackground=CORES['chip_border_off'], highlightthickness=1,
            )
            btn.pack(side='left', padx=(0, 6))
            btn.bind('<Button-1>', lambda e, v=val: (self.modo_verificacao.set(v), _atualizar_modo()))
            _modo_btns[val] = btn

        # Subpainel da API Key (visível só em modo 'ia')
        self._verif_api_row = tk.Frame(verif_frame, bg=CORES['bg_card'])

        api_linha = tk.Frame(self._verif_api_row, bg=CORES['bg_card'])
        api_linha.pack(fill='x', pady=(0, 4))
        tk.Label(api_linha, text="API Key Gemini:",
                 font=("Segoe UI", 10), fg=CORES['fg_dim'],
                 bg=CORES['bg_card']).pack(side='left', padx=(0, 8))
        tk.Entry(api_linha, textvariable=self.verif_api_key,
                 font=("Segoe UI", 10), fg=CORES['fg_bright'],
                 bg=CORES['bg_input'], insertbackground=CORES['fg'],
                 relief='flat', highlightbackground=CORES['accent'],
                 highlightthickness=1, show='*', width=36).pack(side='left')

        modelo_linha = tk.Frame(self._verif_api_row, bg=CORES['bg_card'])
        modelo_linha.pack(fill='x', pady=(0, 2))
        tk.Label(modelo_linha, text="Modelo:",
                 font=("Segoe UI", 10), fg=CORES['fg_dim'],
                 bg=CORES['bg_card']).pack(side='left', padx=(0, 8))
        self._verif_modelo_combo = ttk.Combobox(
            modelo_linha, textvariable=self.verif_modelo,
            font=("Segoe UI", 10), width=30, state='readonly')
        self._verif_modelo_combo.pack(side='left')
        self._criar_mini_btn(
            modelo_linha, "Carregar modelos",
            self._verif_carregar_modelos
        ).pack(side='left', padx=(8, 0))

        _atualizar_modo()
```

- [ ] **Step 3: Adicionar método `_verif_carregar_modelos` em `app.py`**

Adicionar após o método `_vtc_carregar_modelos` (busque o final desse método para posicionar):

```python
    def _verif_carregar_modelos(self):
        api_key = self.verif_api_key.get().strip()
        if not api_key:
            messagebox.showerror("Erro", "Informe a API Key antes de carregar os modelos.")
            return

        def _buscar():
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                modelos = [m.name for m in genai.list_models()
                           if 'generateContent' in m.supported_generation_methods
                           and 'vision' in m.name.lower() or 'gemini' in m.name.lower()]
                modelos = sorted(set(modelos))
                self.after(0, lambda: self._verif_popular_modelos(modelos))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Erro", f"Falha ao carregar modelos:\n{e}"))

        threading.Thread(target=_buscar, daemon=True).start()

    def _verif_popular_modelos(self, modelos):
        self._verif_modelo_combo['values'] = modelos
        if modelos:
            atual = self.verif_modelo.get()
            if atual not in modelos:
                self.verif_modelo.set(modelos[0])
```

- [ ] **Step 4: Verificar visualmente**

Rodar `python app.py` e confirmar:
- Card "🔍 Verificação" aparece na aba Processar abaixo dos chips de códigos
- Clicar "Varredura única" / "Dupla varredura" / "Dupla + IA" alterna o estado visual dos chips
- O subpainel da API Key aparece apenas quando "Dupla + IA" está selecionado

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: card de verificação na UI (modo único/dupla/IA)"
```

---

## Task 5: Integrar verificação no fluxo de processamento

**Files:**
- Modify: `app.py` — métodos `_iniciar_processamento`, `_processar`, `_abrir_janela_progresso`, `_inferir_etapa_progresso`, `_atualizar_etapas_progresso`

- [ ] **Step 1: Salvar config de API Key e modelo ao processar**

No método `_iniciar_processamento`, logo antes de criar a thread (após `self.processando = True`), adicionar:

```python
        # Persistir config de verificação IA
        if self.modo_verificacao.get() == 'ia':
            _salvar_config({
                'gemini_api_key_ocorrencias': self.verif_api_key.get().strip(),
                'gemini_modelo_ocorrencias':  self.verif_modelo.get().strip(),
            })
```

- [ ] **Step 2: Passar modo e config para a thread**

Na chamada `threading.Thread` dentro de `_iniciar_processamento`, adicionar os parâmetros extras:

```python
        modo_verif   = self.modo_verificacao.get()
        verif_key    = self.verif_api_key.get().strip()
        verif_modelo = self.verif_modelo.get().strip()

        thread = threading.Thread(
            target=self._processar,
            args=(pdf, xlsx, output, codigos, dias_mes, colunas_qt,
                  modo_verif, verif_key, verif_modelo)
        )
```

- [ ] **Step 3: Atualizar assinatura e corpo de `_processar`**

Substituir o método `_processar` existente por:

```python
    def _processar(self, pdf_path, xlsx_path, output_path, codigos,
                   dias_mes=None, colunas_qt=None,
                   modo_verif='unica', verif_key='', verif_modelo=''):
        def cb(pct, msg):
            self.after(0, lambda p=pct, m=msg: self._atualizar_progresso(p, m))

        try:
            # Varredura 1 — sempre
            cb(5, "Lendo PDF (varredura 1)...")
            v1 = self.processador.extrair_ocorrencias(pdf_path, codigos)

            dados_reconciliados = v1
            info_verif = {'modo': modo_verif, 'ia_usada': False, 'ia_fallback': False}

            if modo_verif in ('dupla', 'ia'):
                # Varredura 2
                cb(20, "Varredura 2 (texto/regex)...")
                v2 = self.processador.extrair_ocorrencias_texto(pdf_path, codigos)

                if not v2:
                    # V2 não encontrou nada — avisa e continua com V1
                    continuar = self.after(
                        0,
                        lambda: messagebox.askyesno(
                            "Varredura 2",
                            "A segunda varredura não encontrou REs no PDF.\n"
                            "Isso pode indicar um layout não suportado.\n\n"
                            "Continuar com varredura única?"
                        )
                    )
                    # fallback silencioso para única
                    camadas = [v1]
                else:
                    camadas = [v1, v2]

                # Varredura 3 — IA
                if modo_verif == 'ia':
                    cb(35, "Verificando com IA (Gemini Vision)...")
                    v3 = self.processador.verificar_com_ia(
                        pdf_path, codigos, verif_key, verif_modelo
                    )
                    if v3 is not None:
                        camadas.append(v3)
                        info_verif['ia_usada'] = True
                    else:
                        info_verif['ia_fallback'] = True

                # Reconciliar
                cb(45, "Reconciliando resultados...")
                rec = self.processador.reconciliar(camadas, codigos)

                concordantes = rec['concordantes']
                conflitos    = rec['conflitos']

                if conflitos:
                    # Pausar thread e abrir modal na thread principal
                    import queue
                    q = queue.Queue()
                    self.after(0, lambda: self._abrir_modal_conflitos(conflitos, q))
                    escolhas = q.get()  # bloqueia até usuário confirmar ou cancelar

                    if escolhas is None:
                        # Usuário cancelou
                        self.after(0, self._finalizar_processamento)
                        return

                    # Aplicar escolhas do usuário sobre os concordantes
                    for re_val, cod, val in escolhas:
                        if re_val not in concordantes:
                            # Buscar nome
                            nome = next(
                                (c.get(re_val, {}).get('nome', '') for c in camadas if re_val in c), ''
                            )
                            concordantes[re_val] = {'nome': nome, 'ocorrencias': {}}
                        concordantes[re_val]['ocorrencias'][cod] = val

                dados_reconciliados = concordantes
                info_verif['concordantes'] = len(concordantes)
                info_verif['conflitos_resolvidos'] = len(conflitos)

            resultado = self.processador.processar(
                pdf_path, xlsx_path, output_path, codigos, cb, dias_mes, colunas_qt,
                dados_externos=dados_reconciliados if modo_verif != 'unica' else None
            )
            resultado['info_verif'] = info_verif

            self.after(0, self._marcar_sucesso_progresso)
            self.after(750, lambda: self._mostrar_resultados(resultado, output_path))
        except Exception as e:
            self.after(0, lambda: self._mostrar_erro(str(e)))
            self.after(0, self._finalizar_processamento)
```

- [ ] **Step 4: Adicionar parâmetro `dados_externos` ao método `processar` em `processador.py`**

Alterar a assinatura de `processar`:

```python
    def processar(self, pdf_path, xlsx_path, output_path, codigos,
                  progress_cb=None, dias_mes=None, colunas_qt_sel=None,
                  dados_externos=None):
```

E no início do passo "1. Extrair ocorrências do PDF" (logo após `_prog(5, ...)`), substituir:

```python
        # 1. Extrair ocorrências do PDF
        _prog(5, "Lendo PDF...")
        if dados_externos is not None:
            resultados_pdf = dados_externos
            _prog(50, "Dados reconciliados recebidos. Abrindo planilha...")
        else:
            resultados_pdf = self.extrair_ocorrencias(pdf_path, codigos)
            _prog(50, "PDF lido. Abrindo planilha...")
```

- [ ] **Step 5: Atualizar etapas de progresso para incluir novas fases**

No método `_abrir_janela_progresso`, substituir a lista `steps`:

```python
        steps = [
            ("prepare",  "Preparar"),
            ("pdf",      "Ler PDF (V1)"),
            ("pdf2",     "Varredura 2"),
            ("ia",       "Verificar com IA"),
            ("reconcile","Reconciliar"),
            ("sheet",    "Abrir planilha"),
            ("match",    "Cruzar dados"),
            ("save",     "Salvar"),
            ("done",     "Concluir"),
        ]
```

No método `_inferir_etapa_progresso`, adicionar os novos casos antes do `if "pdf" in texto`:

```python
        if "reconcil" in texto:
            return "reconcile", "Reconciliando"
        if "gemini" in texto or "ia" in texto or "intelig" in texto:
            return "ia", "Verificando com IA"
        if "varredura 2" in texto:
            return "pdf2", "Varredura 2"
```

No método `_atualizar_etapas_progresso`, atualizar a lista `order`:

```python
        order = ["prepare", "pdf", "pdf2", "ia", "reconcile", "sheet", "match", "save", "done"]
```

- [ ] **Step 6: Commit**

```bash
git add app.py processador.py
git commit -m "feat: integrar dupla varredura e IA no fluxo de processamento"
```

---

## Task 6: Modal de conflitos

**Files:**
- Modify: `app.py` — novo método `_abrir_modal_conflitos`

- [ ] **Step 1: Implementar o método `_abrir_modal_conflitos`**

Adicionar após o método `_abrir_tela_resumo`:

```python
    def _abrir_modal_conflitos(self, conflitos, resultado_queue):
        """
        Abre janela modal listando conflitos entre camadas.
        Coloca as escolhas do usuário em resultado_queue como lista de
        (re, codigo, valor) ou None se cancelado.
        """
        win = tk.Toplevel(self)
        win.title("Conflitos encontrados")
        win.configure(bg=CORES['bg'])
        win.geometry("760x540")
        win.minsize(640, 400)
        win.grab_set()
        win.protocol("WM_DELETE_WINDOW", lambda: None)

        win.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 380
        y = self.winfo_y() + (self.winfo_height() // 2) - 270
        win.geometry(f"760x540+{x}+{y}")

        main = tk.Frame(win, bg=CORES['bg'])
        main.pack(fill='both', expand=True, padx=20, pady=16)

        tk.Label(main,
                 text=f"Conflitos encontrados — {len(conflitos)} item(s) precisam de revisão",
                 font=("Segoe UI", 13, "bold"), fg=CORES['fg_bright'],
                 bg=CORES['bg']).pack(anchor='w', pady=(0, 4))
        tk.Label(main,
                 text="Selecione o valor correto para cada conflito. A sugestão já está pré-selecionada.",
                 font=("Segoe UI", 9), fg=CORES['fg_dim'],
                 bg=CORES['bg']).pack(anchor='w', pady=(0, 12))

        # Área scrollável
        canvas = tk.Canvas(main, bg=CORES['bg'], highlightthickness=0)
        sb = ttk.Scrollbar(main, orient='vertical', command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=CORES['bg'])
        scroll_frame.bind('<Configure>',
                          lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        canvas.bind('<Enter>', lambda e: canvas.bind_all(
            '<MouseWheel>', lambda ev: canvas.yview_scroll(-1*(ev.delta//120), 'units')))
        canvas.bind('<Leave>', lambda e: canvas.unbind_all('<MouseWheel>'))

        # Variáveis de escolha: {(re, codigo): IntVar}
        escolha_vars = {}

        for conflito in conflitos:
            re_val = conflito['re']
            nome   = conflito['nome']
            cod    = conflito['codigo']
            vals   = conflito['valores']   # {'v1': int, 'v2': int, 'ia': int|None}
            sug    = conflito['sugestao']

            card = tk.Frame(scroll_frame, bg=CORES['bg_card'],
                            highlightbackground=CORES['border'], highlightthickness=1)
            card.pack(fill='x', pady=(0, 8))

            top = tk.Frame(card, bg=CORES['bg_card'])
            top.pack(fill='x', padx=14, pady=(10, 6))
            tk.Label(top, text=f"RE {re_val}  —  {nome}",
                     font=("Segoe UI", 10, "bold"), fg=CORES['fg_bright'],
                     bg=CORES['bg_card']).pack(side='left')
            tk.Label(top, text=f"Código: {cod}",
                     font=("Segoe UI", 9), fg=CORES['accent_light'],
                     bg=CORES['bg_card']).pack(side='right')

            opcoes_row = tk.Frame(card, bg=CORES['bg_card'])
            opcoes_row.pack(fill='x', padx=14, pady=(0, 12))

            var = tk.IntVar(value=sug)
            escolha_vars[(re_val, cod)] = var

            rotulos = {'v1': 'V1 (tabelas)', 'v2': 'V2 (texto)', 'ia': 'IA (Gemini)'}
            valores_unicos = {}
            for chave, val in vals.items():
                if val is None:
                    continue
                label_camada = rotulos.get(chave, chave)
                if val not in valores_unicos:
                    valores_unicos[val] = []
                valores_unicos[val].append(label_camada)

            for val_opcao, camadas_label in sorted(valores_unicos.items()):
                texto_btn = f"{val_opcao} {cod}  ({', '.join(camadas_label)})"
                is_sug = (val_opcao == sug)
                rb = tk.Radiobutton(
                    opcoes_row, text=texto_btn,
                    variable=var, value=val_opcao,
                    font=("Segoe UI", 9, "bold" if is_sug else "normal"),
                    fg=CORES['accent_light'] if is_sug else CORES['fg'],
                    bg=CORES['bg_card'],
                    activebackground=CORES['bg_card'],
                    selectcolor=CORES['bg_input'],
                )
                rb.pack(side='left', padx=(0, 16))

        # Botões
        btn_row = tk.Frame(main, bg=CORES['bg'])
        btn_row.pack(fill='x', pady=(12, 0))

        def confirmar():
            escolhas = [(re_val, cod, var.get())
                        for (re_val, cod), var in escolha_vars.items()]
            win.destroy()
            resultado_queue.put(escolhas)

        def cancelar():
            win.destroy()
            resultado_queue.put(None)

        tk.Button(btn_row, text="Confirmar e gravar",
                  font=("Segoe UI", 11, "bold"),
                  fg=CORES['btn_fg'], bg=CORES['btn_bg'],
                  activeforeground=CORES['btn_fg'], activebackground=CORES['btn_hover'],
                  relief='flat', cursor='hand2', padx=18, pady=8, borderwidth=0,
                  command=confirmar).pack(side='left')

        tk.Button(btn_row, text="Cancelar",
                  font=("Segoe UI", 11),
                  fg=CORES['fg_dim'], bg=CORES['bg_input'],
                  activeforeground=CORES['fg'], activebackground=CORES['border'],
                  relief='flat', cursor='hand2', padx=18, pady=8, borderwidth=0,
                  command=cancelar).pack(side='left', padx=(10, 0))
```

- [ ] **Step 2: Verificar visualmente**

Para testar o modal sem precisar de um PDF real, adicionar temporariamente no `__init__` após `self._criar_interface()`:

```python
        # TESTE TEMPORÁRIO — remover após verificar
        import queue; q = queue.Queue()
        self.after(500, lambda: self._abrir_modal_conflitos([
            {'re': '12345', 'nome': 'SILVA JOAO', 'codigo': 'AT',
             'valores': {'v1': 2, 'v2': 1, 'ia': None}, 'sugestao': 2},
            {'re': '67890', 'nome': 'SOUZA MARIA', 'codigo': 'FA',
             'valores': {'v1': 1, 'v2': 3, 'ia': 1}, 'sugestao': 1},
        ], q))
```

Rodar `python app.py`, confirmar que o modal abre, mostra os conflitos, botões funcionam. **Remover o trecho de teste após validar.**

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: modal de resolução de conflitos entre camadas de verificação"
```

---

## Task 7: Bloco de verificação no resumo

**Files:**
- Modify: `app.py` — métodos `_mostrar_resultados`, `_abrir_tela_resumo`

- [ ] **Step 1: Passar `info_verif` para o histórico e para a tela de resumo**

No método `_mostrar_resultados`, o `resultado` agora contém `info_verif`. Atualizar:

```python
    def _mostrar_resultados(self, resultado, output_path):
        from datetime import datetime
        self._historico.append({
            'arquivo': os.path.basename(output_path),
            'data': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'total_pdf': resultado['total_pdf'],
            'matched': resultado['matched'],
            'nao_encontrados': len(resultado['nao_encontrados']),
            'lista_nao_encontrados': resultado['nao_encontrados'],
            'info_verif': resultado.get('info_verif', {'modo': 'unica'}),
        })
        self._atualizar_historico()
        self._abrir_tela_resumo(resultado, output_path)
```

- [ ] **Step 2: Adicionar bloco de verificação na tela de resumo**

No método `_abrir_tela_resumo`, após o bloco de cards de estatísticas (procure por `stats_frame`) e antes do bloco de "Registros atualizados", inserir:

```python
        # Bloco de verificação
        info_verif = resultado.get('info_verif', {'modo': 'unica'})
        modo = info_verif.get('modo', 'unica')
        if modo != 'unica':
            vf = tk.Frame(main, bg=CORES['bg_card'],
                          highlightbackground=CORES['border'], highlightthickness=1)
            vf.pack(fill='x', pady=(0, 14))
            vf_inner = tk.Frame(vf, bg=CORES['bg_card'])
            vf_inner.pack(fill='x', padx=14, pady=10)

            modo_labels = {'dupla': 'Dupla varredura', 'ia': 'Dupla + IA (Gemini)'}
            tk.Label(vf_inner,
                     text=f"🔍  {modo_labels.get(modo, modo)}",
                     font=("Segoe UI", 10, "bold"), fg=CORES['accent_light'],
                     bg=CORES['bg_card']).pack(anchor='w', pady=(0, 6))

            stats_v = tk.Frame(vf_inner, bg=CORES['bg_card'])
            stats_v.pack(fill='x')

            conc = info_verif.get('concordantes', 0)
            conf = info_verif.get('conflitos_resolvidos', 0)
            ia_usada = info_verif.get('ia_usada', False)
            ia_fallback = info_verif.get('ia_fallback', False)

            for label, valor, cor in [
                ("Automáticos",         str(conc), CORES['success']),
                ("Conflitos resolvidos", str(conf),
                 CORES['warning'] if conf else CORES['fg_dim']),
            ]:
                bloco = tk.Frame(stats_v, bg=CORES['bg_input'])
                bloco.pack(side='left', padx=(0, 6))
                tk.Label(bloco, text=valor, font=("Segoe UI", 12, "bold"),
                         fg=cor, bg=CORES['bg_input']).pack(side='left', padx=(8, 4), pady=4)
                tk.Label(bloco, text=label, font=("Segoe UI", 8),
                         fg=CORES['fg_dim'], bg=CORES['bg_input']).pack(side='left', padx=(0, 8))

            if modo == 'ia':
                if ia_usada:
                    ia_txt, ia_cor = "IA utilizada", CORES['success']
                elif ia_fallback:
                    ia_txt, ia_cor = "IA indisponível — usou dupla varredura", CORES['warning']
                else:
                    ia_txt, ia_cor = "IA não ativada", CORES['fg_dim']
                tk.Label(vf_inner, text=ia_txt,
                         font=("Segoe UI", 9), fg=ia_cor,
                         bg=CORES['bg_card']).pack(anchor='w', pady=(6, 0))
```

- [ ] **Step 3: Verificar visualmente**

Rodar `python app.py` e processar com cada modo para confirmar que o bloco aparece corretamente no resumo.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: bloco de verificação na tela de resumo"
```

---

## Task 8: Bump de versão, build e tag

**Files:**
- Modify: `app.py` — VERSION
- Create: `ProcessadorOcorrencias-v1.29.spec`

- [ ] **Step 1: Bump de versão**

Em `app.py`, alterar:
```python
VERSION = "1.28"
```
para:
```python
VERSION = "1.29"
```

- [ ] **Step 2: Criar spec v1.29**

Copiar `ProcessadorOcorrencias-v1.28.spec` para `ProcessadorOcorrencias-v1.29.spec` e alterar o `name`:
```python
    name='ProcessadorOcorrencias-v1.29',
```

- [ ] **Step 3: Rodar todos os testes**

```bash
.venv/Scripts/pytest tests/test_processador_verificacao.py -v
```
Esperado: todos PASSED

- [ ] **Step 4: Build do executável**

```bash
.venv/Scripts/pyinstaller ProcessadorOcorrencias-v1.29.spec
```
Esperado: `dist/ProcessadorOcorrencias-v1.29.exe` gerado sem erros.

- [ ] **Step 5: Commit final**

```bash
git add app.py ProcessadorOcorrencias-v1.29.spec
git commit -m "feat: dupla verificação + IA em ocorrências + bump v1.29"
```
