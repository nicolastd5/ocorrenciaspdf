#!/usr/bin/env python3
"""
Processador de Ocorrências v1.2
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
    'bg':              '#0c0c1d',
    'bg_card':         '#141428',
    'bg_input':        '#1c1c38',
    'fg':              '#d1d5f0',
    'fg_dim':          '#4a5080',
    'fg_bright':       '#eef0ff',
    'accent':          '#7c6af7',
    'accent_light':    '#a59bf8',
    'accent_hover':    '#6558e8',
    'success':         '#4ade80',
    'error':           '#f87171',
    'warning':         '#fbbf24',
    'border':          '#1e1e3c',
    'btn_bg':          '#7c6af7',
    'btn_fg':          '#ffffff',
    'btn_hover':       '#6558e8',
    'chip_on':         '#1c1c38',
    'chip_off':        '#141428',
    'chip_border_on':  '#7c6af7',
    'chip_border_off': '#1e1e3c',
    'table_header':    '#1c1c38',
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

        tk.Label(topbar, text="v1.2",
                 font=("Segoe UI", 9), fg=CORES['fg_dim'],
                 bg=CORES['bg']).pack(side='left', padx=(6, 0), pady=(4, 0))

        # Botões de aba alinhados à direita
        self._tab_btns = {}
        self._tab_frames = {}
        tabs_container = tk.Frame(topbar, bg=CORES['bg'])
        tabs_container.pack(side='right')

        for tab_id, label in [('processar', '⚙  Processar'), ('sobre', 'ℹ  Sobre')]:
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

        # Barra de progresso
        style = ttk.Style()
        style.theme_use('default')
        style.configure("Accent.Horizontal.TProgressbar",
                        troughcolor=CORES['bg_card'],
                        background=CORES['accent'],
                        borderwidth=0, lightcolor=CORES['accent'],
                        darkcolor=CORES['accent'])
        self.progress = ttk.Progressbar(parent, mode='indeterminate',
                                        style="Accent.Horizontal.TProgressbar")

        # Área de Resultados
        self.resultado_frame = tk.Frame(parent, bg=CORES['bg'])
        self.resultado_frame.pack(fill='both', expand=True, pady=(8, 0))

    def _criar_aba_sobre(self, parent):
        frame = tk.Frame(parent, bg=CORES['bg'])
        frame.pack(fill='both', expand=True, padx=40, pady=30)

        tk.Label(frame, text="⚙", font=("Segoe UI", 48),
                 fg=CORES['accent'], bg=CORES['bg']).pack()

        tk.Label(frame, text="Processador de Ocorrências",
                 font=("Segoe UI", 20, "bold"), fg=CORES['fg_bright'],
                 bg=CORES['bg']).pack(pady=(4, 0))

        tk.Label(frame, text="Versão 1.2",
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
        self.btn_processar.configure(state='disabled', bg=CORES['bg_input'])
        self.progress.pack(fill='x', pady=(6, 0))
        self.progress.start(15)

        for w in self.resultado_frame.winfo_children():
            w.destroy()

        self._iniciar_animacao()

        thread = threading.Thread(target=self._processar,
                                  args=(pdf, xlsx, output, codigos))
        thread.daemon = True
        thread.start()

    def _processar(self, pdf_path, xlsx_path, output_path, codigos):
        try:
            resultado = self.processador.processar(pdf_path, xlsx_path, output_path, codigos)
            self.after(0, lambda: self._mostrar_resultados(resultado, output_path))
        except Exception as e:
            self.after(0, lambda: self._mostrar_erro(str(e)))
        finally:
            self.after(0, self._finalizar_processamento)

    def _iniciar_animacao(self):
        frames = [
            "⠋  Processando...",
            "⠙  Processando...",
            "⠹  Processando...",
            "⠸  Processando...",
            "⠼  Processando...",
            "⠴  Processando...",
            "⠦  Processando...",
            "⠧  Processando...",
            "⠇  Processando...",
            "⠏  Processando...",
        ]
        self._anim_frames = frames
        self._anim_frame = 0
        self._animar_btn()

    def _animar_btn(self):
        if not self.processando:
            return
        self.btn_processar.configure(text=self._anim_frames[self._anim_frame])
        self._anim_frame = (self._anim_frame + 1) % len(self._anim_frames)
        self._anim_job = self.after(100, self._animar_btn)

    def _finalizar_processamento(self):
        self.processando = False
        if self._anim_job:
            self.after_cancel(self._anim_job)
            self._anim_job = None
        self.btn_processar.configure(text="▶  PROCESSAR ARQUIVOS", state='normal',
                                     bg=CORES['btn_bg'])
        self.progress.stop()
        self.progress.pack_forget()

    def _mostrar_erro(self, msg):
        messagebox.showerror("Erro no Processamento", msg)

    def _mostrar_resultados(self, resultado, output_path):
        frame = self.resultado_frame

        # Cards de estatísticas
        stats_frame = tk.Frame(frame, bg=CORES['bg'])
        stats_frame.pack(fill='x', pady=(0, 10))

        stats = [
            ("No PDF", str(resultado['total_pdf']), CORES['accent_light']),
            ("Atualizados", str(resultado['matched']), CORES['success']),
            ("Sem match", str(len(resultado['nao_encontrados'])),
             CORES['error'] if resultado['nao_encontrados'] else CORES['success']),
        ]

        for i, (label, value, color) in enumerate(stats):
            # Borda superior colorida
            outer = tk.Frame(stats_frame, bg=color)
            outer.pack(side='left', fill='x', expand=True, padx=(0 if i == 0 else 6, 0))

            tk.Frame(outer, bg=color, height=3).pack(fill='x')

            card = tk.Frame(outer, bg=CORES['bg_card'],
                            highlightbackground=CORES['border'], highlightthickness=1)
            card.pack(fill='both', expand=True)

            tk.Label(card, text=value, font=("Segoe UI", 28, "bold"),
                     fg=color, bg=CORES['bg_card']).pack(pady=(10, 0))
            tk.Label(card, text=label, font=("Segoe UI", 9),
                     fg=CORES['fg_dim'], bg=CORES['bg_card']).pack(pady=(0, 10))

        # Botão abrir pasta
        btn_row = tk.Frame(frame, bg=CORES['bg'])
        btn_row.pack(fill='x', pady=(0, 8))

        open_btn = tk.Button(
            btn_row, text="📂  Abrir pasta do arquivo",
            font=("Segoe UI", 10), fg=CORES['success'],
            bg=CORES['bg_card'], activeforeground=CORES['success'],
            activebackground=CORES['bg_input'],
            relief='flat', cursor='hand2', pady=8, borderwidth=0,
            command=lambda: os.startfile(os.path.dirname(output_path))
            if os.name == 'nt' else None
        )
        open_btn.pack(side='left', fill='x', expand=True)
        self._bind_hover(open_btn, CORES['bg_card'], CORES['bg_input'])

        tk.Label(btn_row, text=f"💾  {os.path.basename(output_path)}",
                 font=("Consolas", 9), fg=CORES['fg_dim'],
                 bg=CORES['bg']).pack(side='right', padx=(8, 0))

        if resultado['atualizados']:
            self._criar_tabela(frame, "✅  Registros Atualizados",
                               resultado['atualizados'], CORES['success'])

        if resultado['nao_encontrados']:
            self._criar_tabela(frame, "⚠  Sem Correspondência na Planilha",
                               resultado['nao_encontrados'], CORES['error'])

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
                            height=min(len(dados), 8))
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
