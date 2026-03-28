#!/usr/bin/env python3
"""
Processador de Ocorrências v1.6
================================
Aplicação desktop para extrair ocorrências de PDFs de jornada
e preencher a coluna MOTIVO em planilhas Excel de pedido.

Autor: Nicolas Almeida Hader Dias
Uso: python app.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
from processador import ProcessadorOcorrencias

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

        self.processador = ProcessadorOcorrencias()
        self._criar_interface()
        self._centralizar_janela()

    def _centralizar_janela(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f'{w}x{h}+{x}+{y}')

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

        tk.Label(topbar, text="v1.6",
                 font=("Segoe UI", 9), fg=CORES['fg_dim'],
                 bg=CORES['bg']).pack(side='left', padx=(6, 0), pady=(4, 0))

        # Botões de aba alinhados à direita
        self._tab_btns = {}
        self._tab_frames = {}
        tabs_container = tk.Frame(topbar, bg=CORES['bg'])
        tabs_container.pack(side='right')

        for tab_id, label in [('processar', '⚙  Processar'), ('historico', '🕘  Histórico'), ('sobre', 'ℹ  Sobre')]:
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

    def _criar_aba_sobre(self, parent):
        frame = tk.Frame(parent, bg=CORES['bg'])
        frame.pack(fill='both', expand=True, padx=40, pady=30)

        tk.Label(frame, text="⚙", font=("Segoe UI", 48),
                 fg=CORES['accent'], bg=CORES['bg']).pack()

        tk.Label(frame, text="Processador de Ocorrências",
                 font=("Segoe UI", 20, "bold"), fg=CORES['fg_bright'],
                 bg=CORES['bg']).pack(pady=(4, 0))

        tk.Label(frame, text="Versão 1.6",
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
                                  args=(pdf, xlsx, output, codigos))
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

    def _processar(self, pdf_path, xlsx_path, output_path, codigos):
        def cb(pct, msg):
            self.after(0, lambda p=pct, m=msg: self._atualizar_progresso(p, m))

        try:
            resultado = self.processador.processar(pdf_path, xlsx_path, output_path, codigos, cb)
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
