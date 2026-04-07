#!/usr/bin/env python3
"""
Processador de Ocorrências v1.16
==================================
Aplicação desktop para extrair ocorrências de PDFs de jornada
e preencher a coluna MOTIVO em planilhas Excel de pedido.

Autor: Nicolas Almeida Hader Dias
Uso: python app.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import urllib.request
import urllib.error
import json
import webbrowser
from processador import ProcessadorOcorrencias
from vt_caixa_processador import ProcessadorVTCaixa

# ── Config local (API keys e preferências — não versionado) ─────────────────
_CONFIG_PATH = os.path.join(os.path.expanduser('~'), '.ocorrencias_config.json')


def _carregar_config():
    """Carrega config local. Retorna {} se o arquivo não existe (primeira execução)."""
    try:
        with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        # JSON corrompido ou permissão negada — avisa mas não quebra a UI
        import sys
        print(f'[config] Falha ao carregar {_CONFIG_PATH}: {e}', file=sys.stderr)
        return {}


def _salvar_config(dados):
    """Salva config local. Retorna mensagem de erro se falhar, ou None se OK."""
    try:
        cfg = _carregar_config()
        cfg.update(dados)
        with open(_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)
        return None
    except Exception as e:
        return str(e)

VERSION = "1.16"
GITHUB_API_RELEASES = "https://api.github.com/repos/nicolastd5/ocorrenciaspdf/releases/latest"
GITHUB_RELEASES_PAGE = "https://github.com/nicolastd5/ocorrenciaspdf/releases/latest"

# ============================================================
# Configurações visuais
# ============================================================
CORES = {
    'bg':              '#1e1e1e',
    'bg_card':         '#252526',
    'bg_input':        '#2d2d2d',
    'fg':              '#cccccc',
    'fg_dim':          '#6b737f',
    'fg_bright':       '#ffffff',
    'accent':          '#007acc',
    'accent_light':    '#4db8ff',
    'accent_hover':    '#005f9e',
    'success':         '#4ec994',
    'error':           '#f14c4c',
    'warning':         '#cca700',
    'border':          '#3c3c3c',
    'btn_bg':          '#007acc',
    'btn_fg':          '#ffffff',
    'btn_hover':       '#005f9e',
    'chip_on':         '#2d2d2d',
    'chip_off':        '#252526',
    'chip_border_on':  '#007acc',
    'chip_border_off': '#3c3c3c',
    'table_header':    '#2d2d2d',
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Processador de Ocorrências")
        self.geometry("920x780")
        self.configure(bg=CORES['bg'])
        self.minsize(800, 650)

        self.pdf_path = tk.StringVar()
        self.xlsx_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.codigos_vars = {}
        self.codigos_update_fns = {}
        self.processando = False
        self._anim_job = None
        self._anim_frame = 0
        self._historico = []
        self._janela_progresso = None
        self.deduzir_dias = tk.BooleanVar(value=False)
        self.dias_mes = tk.StringVar(value="")
        self.qt_va_var = tk.BooleanVar(value=True)
        self.qt_vr_var = tk.BooleanVar(value=True)
        self.qt_vt_var = tk.BooleanVar(value=True)

        # VT Caixa
        _cfg = _carregar_config()
        self.vtc_pdf_path    = tk.StringVar()
        self.vtc_xls_path    = tk.StringVar()
        self.vtc_output_path = tk.StringVar()
        self.vtc_usar_ia     = tk.BooleanVar(value=False)
        self.vtc_api_key     = tk.StringVar(value=_cfg.get('vtc_api_key', ''))
        self.vtc_model_id    = tk.StringVar(value=_cfg.get('vtc_model_id', 'gemini-2.5-flash'))
        self.vtc_models_map       = {}   # "display — id" → model_id puro
        self.vtc_processando      = False
        self._vtc_janela_progresso = None

        self.processador = ProcessadorOcorrencias()
        self._criar_interface()
        self._centralizar_janela()
        self.after(1500, self._verificar_atualizacao)

    def _centralizar_janela(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f'{w}x{h}+{x}+{y}')

    # ------------------------------------------------------------------
    # Auto-update
    # ------------------------------------------------------------------

    def _verificar_atualizacao(self):
        """Verifica nova versão no GitHub em background (chamada automática ao iniciar)."""
        def _checar():
            tag, erro = self._buscar_versao_github()
            if tag and tag != VERSION:
                self.after(0, lambda: self._mostrar_banner_update(tag))

        threading.Thread(target=_checar, daemon=True).start()

    def _buscar_versao_github(self):
        """Consulta a API do GitHub e retorna (tag, erro). Síncrono — chamar em thread."""
        try:
            req = urllib.request.Request(
                GITHUB_API_RELEASES,
                headers={"User-Agent": "ProcessadorOcorrencias/" + VERSION}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode())
            tag = data.get("tag_name", "").lstrip("v")
            return tag, None
        except urllib.error.URLError:
            return None, "Sem conexão com a internet."
        except Exception as e:
            return None, str(e)

    def _mostrar_banner_update(self, nova_versao):
        """Exibe um banner discreto de atualização disponível."""
        if hasattr(self, '_banner_update') and self._banner_update.winfo_exists():
            return  # já está visível

        banner = tk.Frame(self, bg='#1a3a1a',
                          highlightbackground='#4ec994', highlightthickness=1)
        banner.pack(fill='x', padx=20, pady=(4, 0))
        self._banner_update = banner

        inner = tk.Frame(banner, bg='#1a3a1a')
        inner.pack(fill='x', padx=14, pady=8)

        tk.Label(inner,
                 text=f"Nova versão disponível: v{nova_versao}",
                 font=("Segoe UI", 10, "bold"),
                 fg='#4ec994', bg='#1a3a1a').pack(side='left')

        tk.Button(inner, text="Baixar",
                  font=("Segoe UI", 9, "bold"),
                  fg='#1e1e1e', bg='#4ec994',
                  activeforeground='#1e1e1e', activebackground='#3ab87a',
                  relief='flat', cursor='hand2', padx=10, pady=2, borderwidth=0,
                  command=lambda: webbrowser.open(GITHUB_RELEASES_PAGE)
                  ).pack(side='right', padx=(8, 0))

        tk.Button(inner, text="✕",
                  font=("Segoe UI", 9),
                  fg='#4ec994', bg='#1a3a1a',
                  activeforeground='#ffffff', activebackground='#1a3a1a',
                  relief='flat', cursor='hand2', padx=6, pady=2, borderwidth=0,
                  command=banner.destroy
                  ).pack(side='right')

    def _bind_hover(self, widget, bg_normal, bg_hover, fg_normal=None, fg_hover=None):
        def on_enter(e):
            if str(widget.cget('state')) != 'disabled':
                widget.configure(bg=bg_hover)
                if fg_hover:
                    widget.configure(fg=fg_hover)
        def on_leave(e):
            if str(widget.cget('state')) != 'disabled':
                widget.configure(bg=bg_normal)
                if fg_normal:
                    widget.configure(fg=fg_normal)
        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)

    def _criar_interface(self):
        # Barra de acento no topo
        tk.Frame(self, bg=CORES['accent'], height=3).pack(fill='x', side='top')

        # Cabeçalho com título e abas
        topbar = tk.Frame(self, bg=CORES['bg'])
        topbar.pack(fill='x', padx=20, pady=(14, 0))

        tk.Label(topbar, text="Processador de Ocorrências",
                 font=("Segoe UI", 13, "bold"), fg=CORES['fg_bright'],
                 bg=CORES['bg']).pack(side='left')

        tk.Label(topbar, text=f"v{VERSION}",
                 font=("Segoe UI", 9), fg=CORES['fg_dim'],
                 bg=CORES['bg']).pack(side='left', padx=(6, 0), pady=(4, 0))

        # Botões de aba alinhados à direita
        self._tab_btns = {}
        self._tab_frames = {}
        tabs_container = tk.Frame(topbar, bg=CORES['bg'])
        tabs_container.pack(side='right')

        for tab_id, label in [('processar', '⚙  Processar'), ('historico', '🕘  Histórico'), ('vtcaixa', '💳  VT Caixa'), ('sobre', 'ℹ  Sobre')]:
            btn = tk.Button(tabs_container, text=label,
                            font=("Segoe UI", 10),
                            fg=CORES['fg_dim'], bg=CORES['bg'],
                            relief='flat', cursor='hand2',
                            padx=14, pady=6, borderwidth=0,
                            command=lambda t=tab_id: self._mostrar_aba(t))
            btn.pack(side='left', padx=(0, 2))
            self._tab_btns[tab_id] = btn

        # Linha separadora
        tk.Frame(self, bg=CORES['border'], height=1).pack(fill='x', padx=20, pady=(10, 0))

        # Área de conteúdo
        content = tk.Frame(self, bg=CORES['bg'])
        content.pack(fill='both', expand=True, padx=20, pady=14)

        frame_processar = tk.Frame(content, bg=CORES['bg'])
        self._criar_aba_processar(frame_processar)
        self._tab_frames['processar'] = frame_processar

        frame_historico = tk.Frame(content, bg=CORES['bg'])
        self._criar_aba_historico(frame_historico)
        self._tab_frames['historico'] = frame_historico

        frame_vtcaixa = tk.Frame(content, bg=CORES['bg'])
        self._criar_aba_vtcaixa(frame_vtcaixa)
        self._tab_frames['vtcaixa'] = frame_vtcaixa

        frame_sobre = tk.Frame(content, bg=CORES['bg'])
        self._criar_aba_sobre(frame_sobre)
        self._tab_frames['sobre'] = frame_sobre

        self._mostrar_aba('processar')

    def _mostrar_aba(self, tab_id):
        for fid, frame in self._tab_frames.items():
            frame.pack_forget()
            if fid == tab_id:
                self._tab_btns[fid].configure(
                    fg=CORES['accent_light'], bg=CORES['bg_card'],
                    font=("Segoe UI", 10, "bold"))
            else:
                self._tab_btns[fid].configure(
                    fg=CORES['fg_dim'], bg=CORES['bg'],
                    font=("Segoe UI", 10))
        self._tab_frames[tab_id].pack(fill='both', expand=True)

    def _criar_aba_processar(self, parent):
        # Seleção de Arquivos
        files_frame = self._criar_card(parent, "📁  Arquivos de Entrada")
        self._criar_file_picker(files_frame, "PDF de Faltas", self.pdf_path,
                                [("PDF", "*.pdf")], "Selecionar")
        self._criar_file_picker(files_frame, "Planilha Excel", self.xlsx_path,
                                [("Excel", "*.xlsx")], "Selecionar")

        # Códigos de Ocorrência
        codigos_frame = self._criar_card(parent, "🏷  Códigos de Ocorrência")

        btn_row = tk.Frame(codigos_frame, bg=CORES['bg_card'])
        btn_row.pack(fill='x', pady=(0, 10))

        self._criar_mini_btn(btn_row, "Selecionar Todos",
                             self._selecionar_todos).pack(side='left')
        self._criar_mini_btn(btn_row, "Limpar Seleção",
                             self._limpar_selecao).pack(side='left', padx=(8, 0))

        codes_grid = tk.Frame(codigos_frame, bg=CORES['bg_card'])
        codes_grid.pack(fill='x')

        codigos_info = [
            ('AT', 'Atestado', True),
            ('FA', 'Faltas', True),
            ('AP', 'Afast. Previdenciário', False),
            ('LM', 'Afast. Maternidade', False),
            ('LC', 'Licença Casamento', True),
            ('SD', 'Suspensão Disciplinar', True),
            ('AA', 'Ausência Autorizada', True),
            ('FE', 'Férias', False),
        ]

        for i, (codigo, desc, tem_qtd) in enumerate(codigos_info):
            var = tk.BooleanVar(value=True)
            self.codigos_vars[codigo] = var
            self._criar_chip(codes_grid, codigo, desc, tem_qtd, var, i // 4, i % 4)

        for col in range(4):
            codes_grid.columnconfigure(col, weight=1)

        # Opções adicionais
        opcoes_frame = self._criar_card(parent, "⚙  Opções")

        self._criar_checkbox(
            opcoes_frame,
            "Preencher e deduzir dias nas colunas Qt",
            "Preenche as colunas Qt selecionadas com a quantidade de dias do mês informada, "
            "deduzindo os dias de ocorrências FA, AT, SD e LC para quem as tiver.",
            self.deduzir_dias,
            on_toggle=self._toggle_dias_mes,
        )

        # Subpainel (visível só quando checkbox ativo)
        self._dias_mes_row = tk.Frame(opcoes_frame, bg=CORES['bg_card'])

        # Linha 1: campo de dias
        linha_dias = tk.Frame(self._dias_mes_row, bg=CORES['bg_card'])
        linha_dias.pack(fill='x', pady=(2, 6))
        tk.Label(linha_dias, text="Dias do mês:",
                 font=("Segoe UI", 10), fg=CORES['fg_dim'],
                 bg=CORES['bg_card']).pack(side='left', padx=(28, 8))
        vcmd = (self.register(lambda s: s.isdigit() and int(s) <= 31 if s else True), '%P')
        self._entry_dias = tk.Entry(
            linha_dias, textvariable=self.dias_mes,
            font=("Segoe UI", 11, "bold"), width=5,
            fg=CORES['fg_bright'], bg=CORES['bg_input'],
            insertbackground=CORES['fg'], relief='flat',
            highlightbackground=CORES['accent'], highlightthickness=1,
            justify='center', validate='key', validatecommand=vcmd,
        )
        self._entry_dias.pack(side='left')
        tk.Label(linha_dias, text="dias",
                 font=("Segoe UI", 10), fg=CORES['fg_dim'],
                 bg=CORES['bg_card']).pack(side='left', padx=(6, 0))

        # Linha 2: seleção de colunas Qt
        linha_qt = tk.Frame(self._dias_mes_row, bg=CORES['bg_card'])
        linha_qt.pack(fill='x', pady=(0, 4))
        tk.Label(linha_qt, text="Colunas:",
                 font=("Segoe UI", 10), fg=CORES['fg_dim'],
                 bg=CORES['bg_card']).pack(side='left', padx=(28, 12))

        for sigla, label, var in [
            ("VA", "Qt VA", self.qt_va_var),
            ("VR", "Qt VR", self.qt_vr_var),
            ("VT", "Qt VT", self.qt_vt_var),
        ]:
            self._criar_toggle_qt(linha_qt, sigla, label, var)

        # Botão Processar
        self.btn_processar = tk.Button(
            parent, text="▶  PROCESSAR ARQUIVOS",
            font=("Segoe UI", 13, "bold"),
            fg=CORES['btn_fg'], bg=CORES['btn_bg'],
            activeforeground=CORES['btn_fg'], activebackground=CORES['btn_hover'],
            relief='flat', cursor='hand2', pady=14, borderwidth=0,
            command=self._iniciar_processamento
        )
        self.btn_processar.pack(fill='x', pady=(4, 0))
        self._bind_hover(self.btn_processar, CORES['btn_bg'], CORES['btn_hover'])

        # Área de Resultados
        self.resultado_frame = tk.Frame(parent, bg=CORES['bg'])
        self.resultado_frame.pack(fill='both', expand=True, pady=(8, 0))

    def _criar_aba_historico(self, parent):
        self._historico_frame = parent

        header = tk.Frame(parent, bg=CORES['bg'])
        header.pack(fill='x', pady=(0, 12))

        tk.Label(header, text="🕘  Histórico de Processamentos",
                 font=("Segoe UI", 14, "bold"), fg=CORES['fg_bright'],
                 bg=CORES['bg']).pack(side='left')

        tk.Button(header, text="Limpar", font=("Segoe UI", 9),
                  fg=CORES['fg_dim'], bg=CORES['bg_input'],
                  activeforeground=CORES['fg'], activebackground=CORES['border'],
                  relief='flat', cursor='hand2', padx=10, pady=3, borderwidth=0,
                  command=self._limpar_historico).pack(side='right')

        self._historico_lista = tk.Frame(parent, bg=CORES['bg'])
        self._historico_lista.pack(fill='both', expand=True)

        self._historico_vazio = tk.Label(
            self._historico_lista,
            text="Nenhum processamento realizado ainda.",
            font=("Segoe UI", 11), fg=CORES['fg_dim'], bg=CORES['bg'])
        self._historico_vazio.pack(pady=40)

    def _limpar_historico(self):
        self._historico.clear()
        self._atualizar_historico()

    def _atualizar_historico(self):
        for w in self._historico_lista.winfo_children():
            w.destroy()

        if not self._historico:
            tk.Label(self._historico_lista,
                     text="Nenhum processamento realizado ainda.",
                     font=("Segoe UI", 11), fg=CORES['fg_dim'],
                     bg=CORES['bg']).pack(pady=40)
            return

        canvas = tk.Canvas(self._historico_lista, bg=CORES['bg'], highlightthickness=0)
        sb = ttk.Scrollbar(self._historico_lista, orient='vertical', command=canvas.yview)
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

        for i, entrada in enumerate(reversed(self._historico)):
            card = tk.Frame(scroll_frame, bg=CORES['bg_card'],
                            highlightbackground=CORES['border'], highlightthickness=1)
            card.pack(fill='x', pady=(0, 8))

            # Cabeçalho do card
            top = tk.Frame(card, bg=CORES['bg_card'])
            top.pack(fill='x', padx=14, pady=(10, 6))

            tk.Label(top, text=f"#{len(self._historico) - i}  {entrada['arquivo']}",
                     font=("Segoe UI", 10, "bold"), fg=CORES['fg_bright'],
                     bg=CORES['bg_card']).pack(side='left')
            tk.Label(top, text=entrada['data'],
                     font=("Segoe UI", 9), fg=CORES['fg_dim'],
                     bg=CORES['bg_card']).pack(side='right')

            # Stats inline
            stats_row = tk.Frame(card, bg=CORES['bg_card'])
            stats_row.pack(fill='x', padx=14, pady=(0, 8))

            nao_enc = entrada['nao_encontrados']
            for label, valor, cor in [
                ("No PDF", str(entrada['total_pdf']), CORES['accent_light']),
                ("Aplicados", str(entrada['matched']), CORES['success']),
                ("Não localizados", str(nao_enc),
                 CORES['error'] if nao_enc else CORES['success']),
            ]:
                bloco = tk.Frame(stats_row, bg=CORES['bg_input'])
                bloco.pack(side='left', padx=(0, 6))
                tk.Label(bloco, text=valor, font=("Segoe UI", 13, "bold"),
                         fg=cor, bg=CORES['bg_input']).pack(side='left', padx=(8, 4), pady=4)
                tk.Label(bloco, text=label, font=("Segoe UI", 8),
                         fg=CORES['fg_dim'], bg=CORES['bg_input']).pack(side='left', padx=(0, 8))

            # Não localizados
            if entrada['lista_nao_encontrados']:
                det = tk.Frame(card, bg=CORES['bg_card'])
                det.pack(fill='x', padx=14, pady=(0, 10))

                tk.Label(det, text="Não localizados:",
                         font=("Segoe UI", 9, "bold"), fg=CORES['error'],
                         bg=CORES['bg_card']).pack(anchor='w', pady=(0, 4))

                for p in entrada['lista_nao_encontrados']:
                    tk.Label(det,
                             text=f"  RE {p['re']}  —  {p['nome']}  —  {p['motivo']}",
                             font=("Consolas", 9), fg=CORES['fg_dim'],
                             bg=CORES['bg_card'], anchor='w').pack(fill='x')

    def _criar_aba_vtcaixa(self, parent):
        # ── Card: Arquivos ──────────────────────────────────────────────
        files_frame = self._criar_card(parent, "📁  Arquivos")
        self._criar_file_picker(files_frame, "PDF Nautilus", self.vtc_pdf_path,
                                [("PDF", "*.pdf")], "Selecionar")
        self._criar_file_picker(files_frame, "Excel Cadastral", self.vtc_xls_path,
                                [("Excel .xls", "*.xls")], "Selecionar")

        # File picker de saída (salvar como)
        out_row = tk.Frame(files_frame, bg=CORES['bg_card'])
        out_row.pack(fill='x', pady=5)
        tk.Label(out_row, text="CSV de Saída", font=("Segoe UI", 10),
                 fg=CORES['fg_dim'], bg=CORES['bg_card'], width=14,
                 anchor='w').pack(side='left')
        out_entry = tk.Entry(out_row, textvariable=self.vtc_output_path,
                             font=("Consolas", 9), fg=CORES['fg'],
                             bg=CORES['bg_input'], insertbackground=CORES['fg'],
                             relief='flat', highlightbackground=CORES['border'],
                             highlightthickness=1)
        out_entry.pack(side='left', fill='x', expand=True, padx=(0, 8), ipady=5)

        def _on_out_change(*_):
            color = CORES['accent'] if self.vtc_output_path.get().strip() else CORES['border']
            out_entry.configure(highlightbackground=color)
        self.vtc_output_path.trace_add('write', _on_out_change)

        def _escolher_saida():
            path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV", "*.csv")],
                title="Salvar CSV de importação VT Caixa como...")
            if path:
                self.vtc_output_path.set(path)

        btn_out = tk.Button(out_row, text="Salvar como", font=("Segoe UI", 9),
                            fg=CORES['accent_light'], bg=CORES['bg_input'],
                            activeforeground=CORES['accent'],
                            activebackground=CORES['bg_card'],
                            relief='flat', cursor='hand2', padx=14, pady=5,
                            borderwidth=0, command=_escolher_saida)
        btn_out.pack(side='right')
        self._bind_hover(btn_out, CORES['bg_input'], CORES['bg_card'],
                         CORES['accent_light'], CORES['accent'])

        # ── Card: Opções IA ─────────────────────────────────────────────
        ia_card = self._criar_card(parent, "🤖  Verificação com IA (opcional)")

        ia_chk_row = tk.Frame(ia_card, bg=CORES['bg_card'])
        ia_chk_row.pack(fill='x', pady=(0, 4))

        def _toggle_ia():
            self.vtc_usar_ia.set(not self.vtc_usar_ia.get())
            _atualizar_ia()

        def _atualizar_ia(*_):
            on = self.vtc_usar_ia.get()
            ia_dot.configure(text="☑" if on else "☐",
                             fg=CORES['accent_light'] if on else CORES['fg_dim'])
            ia_lbl.configure(fg=CORES['fg_bright'] if on else CORES['fg'])
            if on:
                self._vtc_ia_key_frame.pack(fill='x', pady=(4, 0))
            else:
                self._vtc_ia_key_frame.pack_forget()

        ia_dot = tk.Label(ia_chk_row, text="☐", font=("Segoe UI", 13),
                          fg=CORES['fg_dim'], bg=CORES['bg_card'], cursor='hand2')
        ia_dot.pack(side='left', padx=(0, 8))
        ia_lbl = tk.Label(ia_chk_row,
                          text="Verificar dados utilizando Google Gemma 4 IA",
                          font=("Segoe UI", 10), fg=CORES['fg'],
                          bg=CORES['bg_card'], cursor='hand2')
        ia_lbl.pack(side='left')
        for w in (ia_dot, ia_lbl, ia_chk_row):
            w.bind('<Button-1>', lambda e: _toggle_ia())

        self._vtc_ia_key_frame = tk.Frame(ia_card, bg=CORES['bg_card'])
        # (não empacotado inicialmente — aparece ao marcar o checkbox)

        # Linha 1: API Key + botão Carregar Modelos
        key_row = tk.Frame(self._vtc_ia_key_frame, bg=CORES['bg_card'])
        key_row.pack(fill='x', pady=(2, 4))
        tk.Label(key_row, text="API Key:", font=("Segoe UI", 10),
                 fg=CORES['fg_dim'], bg=CORES['bg_card'],
                 width=14, anchor='w').pack(side='left')
        tk.Entry(key_row, textvariable=self.vtc_api_key,
                 font=("Consolas", 9), fg=CORES['fg'], bg=CORES['bg_input'],
                 insertbackground=CORES['fg'], relief='flat',
                 highlightbackground=CORES['border'], highlightthickness=1,
                 show='*').pack(side='left', fill='x', expand=True, padx=(0, 8), ipady=5)

        self._vtc_btn_carregar = tk.Button(
            key_row, text="↻  Carregar modelos",
            font=("Segoe UI", 9), fg=CORES['accent_light'], bg=CORES['bg_input'],
            activeforeground=CORES['accent'], activebackground=CORES['bg_card'],
            relief='flat', cursor='hand2', padx=10, pady=5, borderwidth=0,
            command=self._vtc_carregar_modelos,
        )
        self._vtc_btn_carregar.pack(side='right')
        self._bind_hover(self._vtc_btn_carregar, CORES['bg_input'], CORES['bg_card'],
                         CORES['accent_light'], CORES['accent'])

        # Linha 2: Seleção de modelo
        model_row = tk.Frame(self._vtc_ia_key_frame, bg=CORES['bg_card'])
        model_row.pack(fill='x', pady=(0, 2))
        tk.Label(model_row, text="Modelo:", font=("Segoe UI", 10),
                 fg=CORES['fg_dim'], bg=CORES['bg_card'],
                 width=14, anchor='w').pack(side='left')

        # Sem textvariable — vtc_model_id é gerenciado manualmente para
        # garantir que contenha sempre o model_id puro, nunca o texto do display.
        self._vtc_model_combo = ttk.Combobox(
            model_row, font=("Segoe UI", 9), state='readonly', width=40,
        )
        self._vtc_model_combo['values'] = ('gemini-2.5-flash — Gemini 2.5 Flash',)
        self._vtc_model_combo.set(f"{self.vtc_model_id.get()} — Gemini 2.5 Flash")
        if self.vtc_model_id.get().strip() != 'gemini-2.5-flash':
            self._vtc_model_combo.set(self.vtc_model_id.get().strip())
        self._vtc_model_combo.pack(side='left', ipady=4)

        def _on_model_select(event):
            sel = self._vtc_model_combo.get()
            mid = self.vtc_models_map.get(sel, sel.split(' — ')[0])
            self.vtc_model_id.set(mid)

        self._vtc_model_combo.bind('<<ComboboxSelected>>', _on_model_select)
        self._vtc_lbl_modelo_status = tk.Label(
            model_row, text="(clique ↻ para carregar)",
            font=("Segoe UI", 8), fg=CORES['fg_dim'], bg=CORES['bg_card'])
        self._vtc_lbl_modelo_status.pack(side='left', padx=(8, 0))

        # ── Botão Gerar CSV ─────────────────────────────────────────────
        self.vtc_btn_gerar = tk.Button(
            parent, text="▶  GERAR CSV VT CAIXA",
            font=("Segoe UI", 13, "bold"),
            fg=CORES['btn_fg'], bg=CORES['btn_bg'],
            activeforeground=CORES['btn_fg'], activebackground=CORES['btn_hover'],
            relief='flat', cursor='hand2', pady=14, borderwidth=0,
            command=self._gerar_vtcaixa,
        )
        self.vtc_btn_gerar.pack(fill='x', pady=(4, 0))
        self._bind_hover(self.vtc_btn_gerar, CORES['btn_bg'], CORES['btn_hover'])

        # ── Card: Log ───────────────────────────────────────────────────
        log_wrapper = tk.Frame(parent, bg=CORES['bg_card'],
                               highlightbackground=CORES['border'],
                               highlightthickness=1)
        log_wrapper.pack(fill='both', expand=True, pady=(12, 0))
        tk.Frame(log_wrapper, bg=CORES['accent'], width=3).pack(side='left', fill='y')
        log_inner = tk.Frame(log_wrapper, bg=CORES['bg_card'])
        log_inner.pack(side='left', fill='both', expand=True)
        tk.Label(log_inner, text="Log", font=("Segoe UI", 11, "bold"),
                 fg=CORES['fg_bright'], bg=CORES['bg_card']).pack(
                     anchor='w', padx=16, pady=(12, 6))

        log_text_frame = tk.Frame(log_inner, bg=CORES['bg_card'])
        log_text_frame.pack(fill='both', expand=True, padx=16, pady=(0, 14))

        self.vtc_log = tk.Text(log_text_frame, font=("Consolas", 9),
                               fg=CORES['fg'], bg=CORES['bg_input'],
                               insertbackground=CORES['fg'], relief='flat',
                               highlightthickness=0, state='disabled',
                               wrap='word', height=8)
        sb_log = ttk.Scrollbar(log_text_frame, orient='vertical',
                               command=self.vtc_log.yview)
        self.vtc_log.configure(yscrollcommand=sb_log.set)
        self.vtc_log.pack(side='left', fill='both', expand=True)
        sb_log.pack(side='right', fill='y')

        # Tags de cor
        self.vtc_log.tag_configure('ok',   foreground=CORES['success'])
        self.vtc_log.tag_configure('warn', foreground=CORES['warning'])
        self.vtc_log.tag_configure('err',  foreground=CORES['error'])
        self.vtc_log.tag_configure('info', foreground=CORES['accent_light'])

    def _vtc_carregar_modelos(self):
        """Busca modelos disponíveis na API do Google AI e popula o combobox."""
        api_key = self.vtc_api_key.get().strip()
        if not api_key:
            messagebox.showerror("Erro", "Informe a API Key antes de carregar os modelos.")
            return

        self._vtc_btn_carregar.configure(state='disabled', text="Carregando...")
        self._vtc_lbl_modelo_status.configure(text="Buscando modelos...", fg=CORES['fg_dim'])

        def _worker():
            try:
                from vt_caixa_processador import ProcessadorVTCaixa
                modelos = ProcessadorVTCaixa.listar_modelos(api_key)
                self.after(0, lambda m=modelos: self._vtc_popular_modelos(m))
            except Exception as e:
                self.after(0, lambda err=str(e): self._vtc_lbl_modelo_status.configure(
                    text=f"Erro: {err[:60]}", fg=CORES['error']))
                self.after(0, lambda: self._vtc_btn_carregar.configure(
                    state='normal', text="↻  Carregar modelos"))

        threading.Thread(target=_worker, daemon=True).start()

    def _vtc_popular_modelos(self, modelos):
        """Popula o combobox com os modelos recebidos."""
        self._vtc_btn_carregar.configure(state='normal', text="↻  Carregar modelos")
        if not modelos:
            self._vtc_lbl_modelo_status.configure(
                text="Nenhum modelo encontrado.", fg=CORES['warning'])
            return

        # vtc_models_map: "display — id" → model_id puro
        self.vtc_models_map = {f"{mid} — {name}": mid for name, mid in modelos}
        opcoes = list(self.vtc_models_map.keys())
        self._vtc_model_combo['values'] = opcoes

        # Mantém seleção atual (por model_id puro) se ainda disponível
        atual_id = self.vtc_model_id.get()
        match = next((op for op in opcoes if op.split(' — ')[0] == atual_id), None)
        if not match:
            match = next((op for op in opcoes if 'gemini-2.5-flash' in op
                          and 'lite' not in op and 'preview' not in op), opcoes[0])
        self._vtc_model_combo.set(match)
        self.vtc_model_id.set(self.vtc_models_map[match])

        self._vtc_lbl_modelo_status.configure(
            text=f"{len(modelos)} modelo(s) disponível(is)", fg=CORES['success'])

    def _vtc_log_append(self, msg, tag=None):
        """Adiciona linha ao log da aba VT Caixa (thread-safe via self.after)."""
        self.vtc_log.configure(state='normal')
        if tag:
            self.vtc_log.insert(tk.END, msg + '\n', tag)
        else:
            self.vtc_log.insert(tk.END, msg + '\n')
        self.vtc_log.see(tk.END)
        self.vtc_log.configure(state='disabled')

    def _gerar_vtcaixa(self):
        pdf  = self.vtc_pdf_path.get().strip()
        xls  = self.vtc_xls_path.get().strip()
        out  = self.vtc_output_path.get().strip()

        if not pdf or not os.path.exists(pdf):
            messagebox.showerror("Erro", "Selecione um arquivo PDF válido.")
            return
        if not xls or not os.path.exists(xls):
            messagebox.showerror("Erro", "Selecione um arquivo Excel cadastral (.xls) válido.")
            return
        if not out:
            messagebox.showerror("Erro", "Informe o caminho de saída do CSV.")
            return

        usar_ia  = self.vtc_usar_ia.get()
        api_key  = self.vtc_api_key.get().strip()
        model_id = self.vtc_model_id.get().strip() or 'gemini-2.5-flash'
        if usar_ia and not api_key:
            messagebox.showerror("Erro", "Informe a API Key do Google AI Studio para usar a IA.")
            return

        # Limpa log e bloqueia botão
        self.vtc_log.configure(state='normal')
        self.vtc_log.delete('1.0', tk.END)
        self.vtc_log.configure(state='disabled')
        self.vtc_btn_gerar.configure(state='disabled', bg=CORES['bg_input'],
                                     text="◐  Gerando...")
        self.vtc_processando = True
        self._vtc_janela_progresso = self._abrir_janela_progresso()

        def _cb(pct, msg):
            self.after(0, lambda p=pct, m=msg: self._vtc_atualizar_progresso(p, m))

        def _worker():
            try:
                proc = ProcessadorVTCaixa()
                resultado = proc.processar(pdf, xls, out,
                                           progress_cb=_cb,
                                           usar_ia=usar_ia,
                                           api_key=api_key,
                                           model_id=model_id)
                self.after(0, lambda r=resultado: self._vtc_mostrar_resultado(r, out))
            except Exception as e:
                self.after(0, lambda err=str(e): self._vtc_log_append(f"Erro: {err}", 'err'))
                self.after(0, lambda: messagebox.showerror("Erro ao gerar CSV", str(e)))
            finally:
                self.after(0, self._vtc_finalizar)

        threading.Thread(target=_worker, daemon=True).start()

    def _vtc_mostrar_resultado(self, resultado, output_path):
        # Persiste configurações localmente (fora do repositório)
        err_cfg = _salvar_config({
            'vtc_api_key':  self.vtc_api_key.get().strip(),
            'vtc_model_id': self.vtc_model_id.get().strip(),
        })
        if err_cfg:
            self._vtc_log_append(f'Aviso: não foi possível salvar configuração: {err_cfg}', 'warn')

        total   = resultado['total_pdf']
        ok      = resultado['total_ok']
        nao_enc = resultado['nao_encontrados']
        alertas = resultado['alertas_ia']
        avisos_csv = resultado.get('avisos_csv', [])

        self._vtc_log_append('─' * 50)
        self._vtc_log_append(f"✔ {ok} registro(s) processado(s) com sucesso.", 'ok')
        self._vtc_log_append(f"  Total no PDF: {total}")

        if nao_enc:
            self._vtc_log_append(
                f"⚠ {len(nao_enc)} matrícula(s) sem correspondência no Excel:", 'warn')
            for item in nao_enc:
                self._vtc_log_append(f"   • {item}", 'warn')
        else:
            self._vtc_log_append("  Todas as matrículas foram encontradas no Excel.", 'ok')

        self._vtc_log_append(f"\nCSV salvo em: {output_path}", 'info')

        if avisos_csv:
            self._vtc_log_append(f'\n⚠ {len(avisos_csv)} campo(s) com caracteres fora do latin-1 (substituídos por ?):', 'warn')
            for av in avisos_csv:
                self._vtc_log_append(f"   • {av}", 'warn')

        if alertas:
            self._vtc_log_append(f'\n🤖 Relatório IA ({self.vtc_model_id.get()}):', 'info')
            for linha in alertas:
                tag = 'err' if any(k in linha.lower() for k in ('erro', 'inconsistência', 'alerta', 'vazio', 'zerado')) else None
                self._vtc_log_append(f"   {linha}", tag)

    def _vtc_atualizar_progresso(self, pct, msg):
        """Atualiza a janela de progresso do VT Caixa e appenda no log."""
        win = self._vtc_janela_progresso
        if win and win.winfo_exists():
            win._lbl_status.configure(text=msg[:60])
            win._pbar.configure(value=pct)
            win._lbl_pct.configure(text=f"{pct}%")
        self._vtc_log_append(f"[{pct:3d}%] {msg}", 'info')

    def _vtc_finalizar(self):
        self.vtc_processando = False
        self.vtc_btn_gerar.configure(state='normal', bg=CORES['btn_bg'],
                                     text="▶  GERAR CSV VT CAIXA")
        if self._vtc_janela_progresso and self._vtc_janela_progresso.winfo_exists():
            if hasattr(self._vtc_janela_progresso, '_spin_job'):
                try:
                    self._vtc_janela_progresso.after_cancel(
                        self._vtc_janela_progresso._spin_job)
                except Exception:
                    pass
            self._vtc_janela_progresso.destroy()
        self._vtc_janela_progresso = None

    def _criar_aba_sobre(self, parent):
        frame = tk.Frame(parent, bg=CORES['bg'])
        frame.pack(fill='both', expand=True, padx=40, pady=30)

        tk.Label(frame, text="⚙", font=("Segoe UI", 48),
                 fg=CORES['accent'], bg=CORES['bg']).pack()

        tk.Label(frame, text="Processador de Ocorrências",
                 font=("Segoe UI", 20, "bold"), fg=CORES['fg_bright'],
                 bg=CORES['bg']).pack(pady=(4, 0))

        tk.Label(frame, text=f"Versão {VERSION}",
                 font=("Segoe UI", 10), fg=CORES['fg_dim'],
                 bg=CORES['bg']).pack(pady=(2, 0))

        tk.Frame(frame, bg=CORES['border'], height=1).pack(fill='x', pady=20)

        tk.Label(frame,
                 text="Extrai ocorrências de PDFs de jornada de trabalho\n"
                      "e preenche automaticamente em planilhas Excel.",
                 font=("Segoe UI", 11), fg=CORES['fg'], bg=CORES['bg'],
                 justify='center').pack()

        tk.Frame(frame, bg=CORES['border'], height=1).pack(fill='x', pady=20)

        info_content = self._criar_card(frame, "Informações")

        campos = [
            ("Autor", "Nicolas Almeida Hader Dias"),
            ("Tecnologia", "Python 3  •  tkinter  •  pdfplumber  •  openpyxl"),
            ("Plataforma", "Windows"),
        ]

        for label, valor in campos:
            row = tk.Frame(info_content, bg=CORES['bg_card'])
            row.pack(fill='x', pady=3)
            tk.Label(row, text=f"{label}:", font=("Segoe UI", 10, "bold"),
                     fg=CORES['fg_dim'], bg=CORES['bg_card'], width=12,
                     anchor='w').pack(side='left')
            tk.Label(row, text=valor, font=("Segoe UI", 10),
                     fg=CORES['fg'], bg=CORES['bg_card'],
                     anchor='w').pack(side='left')

        # Botão de verificar atualizações
        tk.Frame(frame, bg=CORES['border'], height=1).pack(fill='x', pady=(20, 16))

        update_row = tk.Frame(frame, bg=CORES['bg'])
        update_row.pack()

        self._lbl_update_status = tk.Label(
            update_row, text="",
            font=("Segoe UI", 10), fg=CORES['fg_dim'], bg=CORES['bg'])
        self._lbl_update_status.pack(pady=(0, 10))

        self._btn_buscar_update = tk.Button(
            update_row, text="🔍  Buscar Atualizações",
            font=("Segoe UI", 10, "bold"),
            fg=CORES['btn_fg'], bg=CORES['accent'],
            activeforeground=CORES['btn_fg'], activebackground=CORES['accent_hover'],
            relief='flat', cursor='hand2', padx=18, pady=8, borderwidth=0,
            command=self._buscar_update_manual,
        )
        self._btn_buscar_update.pack()
        self._bind_hover(self._btn_buscar_update, CORES['accent'], CORES['accent_hover'])

    def _buscar_update_manual(self):
        """Chamado pelo botão na aba Sobre."""
        self._btn_buscar_update.configure(state='disabled', text="Verificando...")
        self._lbl_update_status.configure(text="", fg=CORES['fg_dim'])

        def _checar():
            tag, erro = self._buscar_versao_github()
            self.after(0, lambda: self._exibir_resultado_update(tag, erro))

        threading.Thread(target=_checar, daemon=True).start()

    def _exibir_resultado_update(self, tag, erro):
        self._btn_buscar_update.configure(state='normal', text="🔍  Buscar Atualizações")
        if erro:
            self._lbl_update_status.configure(
                text=f"Erro: {erro}", fg=CORES['error'])
        elif tag and tag != VERSION:
            self._lbl_update_status.configure(
                text=f"Nova versão disponível: v{tag}", fg=CORES['success'])
            self._mostrar_banner_update(tag)
            # Adiciona botão de download inline
            if not hasattr(self, '_btn_download_update') or not self._btn_download_update.winfo_exists():
                self._btn_download_update = tk.Button(
                    self._btn_buscar_update.master,
                    text="⬇  Baixar v" + tag,
                    font=("Segoe UI", 10),
                    fg=CORES['success'], bg=CORES['bg_card'],
                    activeforeground=CORES['success'], activebackground=CORES['bg_input'],
                    relief='flat', cursor='hand2', padx=14, pady=6, borderwidth=0,
                    command=lambda: webbrowser.open(GITHUB_RELEASES_PAGE),
                )
                self._btn_download_update.pack(pady=(8, 0))
        else:
            self._lbl_update_status.configure(
                text=f"Você já está na versão mais recente (v{VERSION}).",
                fg=CORES['fg_dim'])

    # ------------------------------------------------------------------
    # Componentes reutilizáveis
    # ------------------------------------------------------------------

    def _criar_card(self, parent, titulo):
        """Card com borda lateral colorida e título."""
        wrapper = tk.Frame(parent, bg=CORES['bg_card'],
                           highlightbackground=CORES['border'], highlightthickness=1)
        wrapper.pack(fill='x', pady=(0, 12))

        # Faixa lateral de acento
        tk.Frame(wrapper, bg=CORES['accent'], width=3).pack(side='left', fill='y')

        card = tk.Frame(wrapper, bg=CORES['bg_card'])
        card.pack(side='left', fill='both', expand=True)

        header = tk.Frame(card, bg=CORES['bg_card'])
        header.pack(fill='x', padx=16, pady=(12, 8))
        tk.Label(header, text=titulo, font=("Segoe UI", 11, "bold"),
                 fg=CORES['fg_bright'], bg=CORES['bg_card']).pack(side='left')

        content = tk.Frame(card, bg=CORES['bg_card'])
        content.pack(fill='x', padx=16, pady=(0, 14))
        return content

    def _criar_file_picker(self, parent, label, var, filetypes, btn_text):
        row = tk.Frame(parent, bg=CORES['bg_card'])
        row.pack(fill='x', pady=5)

        tk.Label(row, text=label, font=("Segoe UI", 10),
                 fg=CORES['fg_dim'], bg=CORES['bg_card'], width=14,
                 anchor='w').pack(side='left')

        entry = tk.Entry(row, textvariable=var, font=("Consolas", 9),
                         fg=CORES['fg'], bg=CORES['bg_input'],
                         insertbackground=CORES['fg'], relief='flat',
                         highlightbackground=CORES['border'], highlightthickness=1)
        entry.pack(side='left', fill='x', expand=True, padx=(0, 8), ipady=5)

        def on_change(*_):
            color = CORES['accent'] if var.get().strip() else CORES['border']
            entry.configure(highlightbackground=color)

        var.trace_add('write', on_change)

        btn = tk.Button(row, text=btn_text, font=("Segoe UI", 9),
                        fg=CORES['accent_light'], bg=CORES['bg_input'],
                        activeforeground=CORES['accent'],
                        activebackground=CORES['bg_card'],
                        relief='flat', cursor='hand2', padx=14, pady=5,
                        borderwidth=0,
                        command=lambda: self._escolher_arquivo(var, filetypes))
        btn.pack(side='right')
        self._bind_hover(btn, CORES['bg_input'], CORES['bg_card'],
                         CORES['accent_light'], CORES['accent'])

    def _escolher_arquivo(self, var, filetypes):
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            var.set(path)

    def _criar_mini_btn(self, parent, text, command):
        btn = tk.Button(parent, text=text, font=("Segoe UI", 9),
                        fg=CORES['fg_dim'], bg=CORES['bg_input'],
                        activeforeground=CORES['fg'],
                        activebackground=CORES['bg_input'],
                        relief='flat', cursor='hand2', padx=12, pady=4,
                        borderwidth=0, command=command)
        self._bind_hover(btn, CORES['bg_input'], CORES['border'],
                         CORES['fg_dim'], CORES['fg'])
        return btn

    def _toggle_dias_mes(self, on):
        if on:
            self._dias_mes_row.pack(fill='x', pady=(4, 0))
            self._entry_dias.focus_set()
        else:
            self._dias_mes_row.pack_forget()
            self.dias_mes.set("")

    def _criar_checkbox(self, parent, label, descricao, var, on_toggle=None):
        row = tk.Frame(parent, bg=CORES['bg_card'])
        row.pack(fill='x', pady=4)

        def toggle():
            var.set(not var.get())
            _atualizar()

        def _atualizar():
            on = var.get()
            dot.configure(
                text="☑" if on else "☐",
                fg=CORES['accent_light'] if on else CORES['fg_dim'],
            )
            lbl.configure(fg=CORES['fg_bright'] if on else CORES['fg'])
            if on_toggle:
                on_toggle(on)

        dot = tk.Label(row, text="☐", font=("Segoe UI", 13),
                       fg=CORES['fg_dim'], bg=CORES['bg_card'], cursor='hand2')
        dot.pack(side='left', padx=(0, 8))

        text_col = tk.Frame(row, bg=CORES['bg_card'])
        text_col.pack(side='left', fill='x', expand=True)

        lbl = tk.Label(text_col, text=label, font=("Segoe UI", 10),
                       fg=CORES['fg'], bg=CORES['bg_card'], anchor='w', cursor='hand2')
        lbl.pack(anchor='w')

        tk.Label(text_col, text=descricao, font=("Segoe UI", 8),
                 fg=CORES['fg_dim'], bg=CORES['bg_card'], anchor='w',
                 wraplength=560, justify='left').pack(anchor='w')

        for w in (dot, lbl, row, text_col):
            w.bind('<Button-1>', lambda e: toggle())

    def _criar_toggle_qt(self, parent, sigla, label, var):
        """Botão toggle pequeno para selecionar coluna Qt VA/VR/VT."""
        def _atualizar():
            on = var.get()
            btn.configure(
                bg=CORES['accent'] if on else CORES['bg_input'],
                fg=CORES['btn_fg'] if on else CORES['fg_dim'],
                highlightbackground=CORES['accent'] if on else CORES['border'],
            )

        def toggle():
            var.set(not var.get())
            _atualizar()

        btn = tk.Label(
            parent,
            text=f"{sigla}  {label}",
            font=("Segoe UI", 9, "bold"),
            fg=CORES['btn_fg'], bg=CORES['accent'],
            padx=12, pady=5, cursor='hand2',
            highlightbackground=CORES['accent'], highlightthickness=1,
        )
        btn.pack(side='left', padx=(0, 6))
        btn.bind('<Button-1>', lambda e: toggle())
        _atualizar()

    def _criar_chip(self, parent, codigo, desc, tem_qtd, var, row, col):
        frame = tk.Frame(parent, bg=CORES['bg_card'])
        frame.grid(row=row, column=col, padx=4, pady=4, sticky='ew')

        def toggle():
            var.set(not var.get())
            atualizar_visual()

        def atualizar_visual():
            on = var.get()
            bg = CORES['chip_on'] if on else CORES['chip_off']
            border = CORES['chip_border_on'] if on else CORES['chip_border_off']
            dot_text = '●' if on else '○'
            dot_fg = CORES['success'] if on else CORES['fg_dim']
            cod_fg = CORES['accent_light'] if on else CORES['fg_dim']
            desc_fg = CORES['fg'] if on else CORES['fg_dim']

            chip.configure(bg=bg, highlightbackground=border)
            inner.configure(bg=bg)
            lbl_dot.configure(bg=bg, fg=dot_fg, text=dot_text)
            lbl_cod.configure(bg=bg, fg=cod_fg)
            lbl_desc.configure(bg=bg, fg=desc_fg)
            if lbl_badge:
                lbl_badge.configure(bg=bg)

        chip = tk.Frame(frame, bg=CORES['chip_on'], cursor='hand2',
                        highlightbackground=CORES['chip_border_on'],
                        highlightthickness=1)
        chip.pack(fill='x')

        inner = tk.Frame(chip, bg=CORES['chip_on'])
        inner.pack(fill='x', padx=10, pady=7)

        lbl_dot = tk.Label(inner, text='●', font=("Segoe UI", 8),
                           fg=CORES['success'], bg=CORES['chip_on'])
        lbl_dot.pack(side='left', padx=(0, 5))

        lbl_cod = tk.Label(inner, text=codigo, font=("Consolas", 11, "bold"),
                           fg=CORES['accent_light'], bg=CORES['chip_on'])
        lbl_cod.pack(side='left')

        lbl_desc = tk.Label(inner, text=desc, font=("Segoe UI", 8),
                            fg=CORES['fg'], bg=CORES['chip_on'])
        lbl_desc.pack(side='left', padx=(6, 0))

        lbl_badge = None
        if not tem_qtd:
            lbl_badge = tk.Label(inner, text="sem qtd", font=("Segoe UI", 7),
                                 fg=CORES['warning'], bg=CORES['chip_on'])
            lbl_badge.pack(side='right')

        self.codigos_update_fns[codigo] = atualizar_visual

        for widget in [chip, inner, lbl_dot, lbl_cod, lbl_desc]:
            widget.bind('<Button-1>', lambda e: toggle())
        if lbl_badge:
            lbl_badge.bind('<Button-1>', lambda e: toggle())

    # ------------------------------------------------------------------
    # Lógica de processamento
    # ------------------------------------------------------------------

    def _selecionar_todos(self):
        for var in self.codigos_vars.values():
            var.set(True)
        self._recriar_chips()

    def _limpar_selecao(self):
        for var in self.codigos_vars.values():
            var.set(False)
        self._recriar_chips()

    def _recriar_chips(self):
        for fn in self.codigos_update_fns.values():
            fn()

    def _iniciar_processamento(self):
        pdf = self.pdf_path.get().strip()
        xlsx = self.xlsx_path.get().strip()

        if not pdf or not os.path.exists(pdf):
            messagebox.showerror("Erro", "Selecione um arquivo PDF válido.")
            return
        if not xlsx or not os.path.exists(xlsx):
            messagebox.showerror("Erro", "Selecione um arquivo Excel válido.")
            return

        codigos = [c for c, v in self.codigos_vars.items() if v.get()]
        if not codigos:
            messagebox.showerror("Erro", "Selecione pelo menos um código de ocorrência.")
            return

        dias_mes = None
        colunas_qt = []
        if self.deduzir_dias.get():
            val = self.dias_mes.get().strip()
            if not val or not val.isdigit() or int(val) < 1:
                messagebox.showerror("Erro", "Informe a quantidade de dias do mês (1–31).")
                return
            dias_mes = int(val)
            colunas_qt = [
                col for col, var in [
                    ('qt va', self.qt_va_var),
                    ('qt vr', self.qt_vr_var),
                    ('qt vt', self.qt_vt_var),
                ] if var.get()
            ]
            if not colunas_qt:
                messagebox.showerror("Erro", "Selecione pelo menos uma coluna Qt (VA, VR ou VT).")
                return

        base, ext = os.path.splitext(xlsx)
        sugestao = f"{base}_ATUALIZADO{ext}"
        output = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile=os.path.basename(sugestao),
            initialdir=os.path.dirname(xlsx),
            title="Salvar planilha atualizada como..."
        )
        if not output:
            return

        self.processando = True
        self.btn_processar.configure(state='disabled', bg=CORES['bg_input'],
                                     text="◐  Processando...")

        for w in self.resultado_frame.winfo_children():
            w.destroy()

        self._janela_progresso = self._abrir_janela_progresso()
        self._iniciar_animacao()

        thread = threading.Thread(target=self._processar,
                                  args=(pdf, xlsx, output, codigos, dias_mes, colunas_qt))
        thread.daemon = True
        thread.start()

    def _abrir_janela_progresso(self):
        win = tk.Toplevel(self)
        win.title("Processando...")
        win.configure(bg=CORES['bg'])
        win.geometry("380x220")
        win.resizable(False, False)
        win.grab_set()
        win.protocol("WM_DELETE_WINDOW", lambda: None)  # bloquear fechar

        win.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 190
        y = self.winfo_y() + (self.winfo_height() // 2) - 110
        win.geometry(f"380x220+{x}+{y}")

        main = tk.Frame(win, bg=CORES['bg'])
        main.pack(fill='both', expand=True, padx=30, pady=24)

        # Canvas da animação estilo Win11 (arco girando)
        RAIO = 28
        SIZE = RAIO * 2 + 12
        canvas = tk.Canvas(main, width=SIZE, height=SIZE,
                           bg=CORES['bg'], highlightthickness=0)
        canvas.pack(pady=(0, 16))

        # Trilha do círculo
        PAD = 6
        canvas.create_oval(PAD, PAD, SIZE - PAD, SIZE - PAD,
                           outline=CORES['border'], width=4)
        # Arco animado
        arc_id = canvas.create_arc(PAD, PAD, SIZE - PAD, SIZE - PAD,
                                   start=90, extent=90,
                                   outline=CORES['accent'], width=4,
                                   style='arc')

        win._arc_angle = 0

        def _girar():
            if not win.winfo_exists():
                return
            win._arc_angle = (win._arc_angle - 8) % 360
            canvas.itemconfigure(arc_id, start=win._arc_angle)
            win._spin_job = win.after(16, _girar)

        win._spin_job = win.after(16, _girar)

        # Label de status
        lbl_status = tk.Label(main, text="Iniciando...",
                              font=("Segoe UI", 10), fg=CORES['fg'],
                              bg=CORES['bg'])
        lbl_status.pack(pady=(0, 10))

        # Barra de progresso
        style = ttk.Style()
        style.theme_use('default')
        style.configure("Win.Horizontal.TProgressbar",
                        troughcolor=CORES['border'],
                        background=CORES['accent'],
                        borderwidth=0,
                        lightcolor=CORES['accent'],
                        darkcolor=CORES['accent'])
        pbar = ttk.Progressbar(main, orient='horizontal', length=320,
                               mode='determinate', maximum=100,
                               style="Win.Horizontal.TProgressbar")
        pbar.pack(fill='x')

        # Label de porcentagem
        lbl_pct = tk.Label(main, text="0%",
                           font=("Segoe UI", 9), fg=CORES['fg_dim'],
                           bg=CORES['bg'])
        lbl_pct.pack(pady=(6, 0))

        win._lbl_status = lbl_status
        win._pbar = pbar
        win._lbl_pct = lbl_pct
        return win

    def _atualizar_progresso(self, pct, msg):
        """Chamado da thread de processamento via self.after."""
        win = self._janela_progresso
        if win and win.winfo_exists():
            win._lbl_status.configure(text=msg)
            win._pbar.configure(value=pct)
            win._lbl_pct.configure(text=f"{pct}%")

    def _processar(self, pdf_path, xlsx_path, output_path, codigos, dias_mes=None, colunas_qt=None):
        def cb(pct, msg):
            self.after(0, lambda p=pct, m=msg: self._atualizar_progresso(p, m))

        try:
            resultado = self.processador.processar(pdf_path, xlsx_path, output_path, codigos, cb, dias_mes, colunas_qt)
            self.after(0, lambda: self._mostrar_resultados(resultado, output_path))
        except Exception as e:
            self.after(0, lambda: self._mostrar_erro(str(e)))
        finally:
            self.after(0, self._finalizar_processamento)

    def _iniciar_animacao(self):
        frames = [
            "◐  Processando...",
            "◓  Processando...",
            "◑  Processando...",
            "◒  Processando...",
        ]
        self._anim_frames = frames
        self._anim_frame = 0
        self._animar_btn()

    def _animar_btn(self):
        if not self.processando:
            return
        self.btn_processar.configure(text=self._anim_frames[self._anim_frame])
        self._anim_frame = (self._anim_frame + 1) % len(self._anim_frames)
        self._anim_job = self.after(200, self._animar_btn)

    def _finalizar_processamento(self):
        self.processando = False
        if self._anim_job:
            self.after_cancel(self._anim_job)
            self._anim_job = None
        self.btn_processar.configure(text="▶  PROCESSAR ARQUIVOS", state='normal',
                                     bg=CORES['btn_bg'])
        if self._janela_progresso and self._janela_progresso.winfo_exists():
            if hasattr(self._janela_progresso, '_spin_job'):
                try:
                    self._janela_progresso.after_cancel(self._janela_progresso._spin_job)
                except Exception:
                    pass
            self._janela_progresso.destroy()
        self._janela_progresso = None

    def _mostrar_erro(self, msg):
        messagebox.showerror("Erro no Processamento", msg)

    def _mostrar_resultados(self, resultado, output_path):
        from datetime import datetime
        self._historico.append({
            'arquivo': os.path.basename(output_path),
            'data': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'total_pdf': resultado['total_pdf'],
            'matched': resultado['matched'],
            'nao_encontrados': len(resultado['nao_encontrados']),
            'lista_nao_encontrados': resultado['nao_encontrados'],
        })
        self._atualizar_historico()
        self._abrir_tela_resumo(resultado, output_path)

    def _abrir_tela_resumo(self, resultado, output_path):
        win = tk.Toplevel(self)
        win.title("Resumo do Processamento")
        win.configure(bg=CORES['bg'])
        win.geometry("820x580")
        win.minsize(700, 450)
        win.grab_set()

        # Centralizar
        win.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 410
        y = self.winfo_y() + (self.winfo_height() // 2) - 290
        win.geometry(f"820x580+{x}+{y}")

        main = tk.Frame(win, bg=CORES['bg'])
        main.pack(fill='both', expand=True, padx=24, pady=20)

        # Título
        tk.Label(main, text="Resumo do Processamento",
                 font=("Segoe UI", 16, "bold"), fg=CORES['fg_bright'],
                 bg=CORES['bg']).pack(anchor='w')
        tk.Label(main, text=f"Arquivo: {os.path.basename(output_path)}",
                 font=("Consolas", 9), fg=CORES['fg_dim'],
                 bg=CORES['bg']).pack(anchor='w', pady=(2, 12))

        # Cards de estatísticas
        stats_frame = tk.Frame(main, bg=CORES['bg'])
        stats_frame.pack(fill='x', pady=(0, 16))

        nao_enc = len(resultado['nao_encontrados'])
        stats = [
            ("Encontrados no PDF", str(resultado['total_pdf']), CORES['accent_light']),
            ("Aplicados na planilha", str(resultado['matched']), CORES['success']),
            ("Não localizados", str(nao_enc),
             CORES['error'] if nao_enc else CORES['success']),
        ]

        for i, (label, value, color) in enumerate(stats):
            card = tk.Frame(stats_frame, bg=CORES['bg_card'],
                            highlightbackground=color, highlightthickness=1)
            card.pack(side='left', fill='x', expand=True, padx=(0 if i == 0 else 8, 0))
            tk.Label(card, text=value, font=("Segoe UI", 22, "bold"),
                     fg=color, bg=CORES['bg_card']).pack(pady=(10, 0))
            tk.Label(card, text=label, font=("Segoe UI", 9),
                     fg=CORES['fg_dim'], bg=CORES['bg_card']).pack(pady=(0, 10))

        # Tabela de não localizados
        if resultado['nao_encontrados']:
            tk.Frame(main, bg=CORES['border'], height=1).pack(fill='x', pady=(0, 10))

            tk.Label(main, text=f"⚠  Pessoas não localizadas na planilha ({nao_enc})",
                     font=("Segoe UI", 11, "bold"), fg=CORES['error'],
                     bg=CORES['bg'], anchor='w').pack(fill='x', pady=(0, 6))

            tree_frame = tk.Frame(main, bg=CORES['bg'])
            tree_frame.pack(fill='both', expand=True)

            style = ttk.Style()
            style.configure("Resumo.Treeview",
                            background=CORES['bg_card'], foreground=CORES['fg'],
                            fieldbackground=CORES['bg_card'], borderwidth=0,
                            font=("Consolas", 10), rowheight=26)
            style.configure("Resumo.Treeview.Heading",
                            background=CORES['table_header'], foreground=CORES['fg_dim'],
                            font=("Segoe UI", 9, "bold"), borderwidth=0, relief='flat')
            style.map("Resumo.Treeview",
                      background=[('selected', CORES['bg_input'])],
                      foreground=[('selected', CORES['accent_light'])])

            tree = ttk.Treeview(tree_frame, columns=('re', 'nome', 'ocorrencia'),
                                show='headings', style="Resumo.Treeview")
            tree.heading('re', text='RE', anchor='w')
            tree.heading('nome', text='Nome', anchor='w')
            tree.heading('ocorrencia', text='Ocorrência', anchor='w')
            tree.column('re', width=80, minwidth=60, stretch=False)
            tree.column('nome', width=380, minwidth=200, stretch=True)
            tree.column('ocorrencia', width=160, minwidth=100, stretch=False)

            sb = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=sb.set)
            tree.pack(side='left', fill='both', expand=True)
            sb.pack(side='right', fill='y')

            for item in resultado['nao_encontrados']:
                tree.insert('', 'end', values=(item['re'], item['nome'], item['motivo']))

        # Botões rodapé
        btn_frame = tk.Frame(main, bg=CORES['bg'])
        btn_frame.pack(fill='x', pady=(14, 0))

        tk.Button(
            btn_frame, text="📂  Abrir pasta",
            font=("Segoe UI", 10), fg=CORES['success'],
            bg=CORES['bg_card'], activeforeground=CORES['success'],
            activebackground=CORES['bg_input'],
            relief='flat', cursor='hand2', padx=14, pady=6, borderwidth=0,
            command=lambda: os.startfile(os.path.dirname(output_path))
        ).pack(side='left')

        tk.Button(
            btn_frame, text="Fechar",
            font=("Segoe UI", 10), fg=CORES['fg_dim'],
            bg=CORES['bg_card'], activeforeground=CORES['fg'],
            activebackground=CORES['bg_input'],
            relief='flat', cursor='hand2', padx=14, pady=6, borderwidth=0,
            command=win.destroy
        ).pack(side='right')

    def _criar_tabela(self, parent, titulo, dados, cor_titulo):
        wrapper = tk.Frame(parent, bg=CORES['bg_card'],
                           highlightbackground=CORES['border'], highlightthickness=1)
        wrapper.pack(fill='both', expand=True, pady=(0, 8))

        tk.Frame(wrapper, bg=cor_titulo, width=3).pack(side='left', fill='y')

        card = tk.Frame(wrapper, bg=CORES['bg_card'])
        card.pack(side='left', fill='both', expand=True)

        tk.Label(card, text=f"{titulo} ({len(dados)})",
                 font=("Segoe UI", 11, "bold"), fg=cor_titulo,
                 bg=CORES['bg_card'], anchor='w').pack(fill='x', padx=14, pady=(12, 6))

        tree_frame = tk.Frame(card, bg=CORES['bg_card'])
        tree_frame.pack(fill='both', expand=True, padx=14, pady=(0, 12))

        style = ttk.Style()
        style.theme_use('default')
        style.configure("Custom.Treeview",
                        background=CORES['bg_card'],
                        foreground=CORES['fg'],
                        fieldbackground=CORES['bg_card'],
                        borderwidth=0,
                        font=("Consolas", 10),
                        rowheight=26)
        style.configure("Custom.Treeview.Heading",
                        background=CORES['table_header'],
                        foreground=CORES['fg_dim'],
                        font=("Segoe UI", 9, "bold"),
                        borderwidth=0, relief='flat')
        style.map("Custom.Treeview",
                  background=[('selected', CORES['bg_input'])],
                  foreground=[('selected', CORES['accent_light'])])

        tree = ttk.Treeview(tree_frame, columns=('re', 'nome', 'motivo'),
                            show='headings', style="Custom.Treeview",
                            height=min(len(dados), 5))
        tree.heading('re', text='RE', anchor='w')
        tree.heading('nome', text='Nome', anchor='w')
        tree.heading('motivo', text='Motivo', anchor='w')
        tree.column('re', width=70, minwidth=60)
        tree.column('nome', width=350, minwidth=200)
        tree.column('motivo', width=200, minwidth=100)

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        for item in dados:
            tree.insert('', 'end', values=(item['re'], item['nome'], item['motivo']))


def main():
    app = App()
    app.mainloop()


if __name__ == '__main__':
    main()
