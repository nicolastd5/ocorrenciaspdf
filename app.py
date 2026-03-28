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
    'bg': '#1e1e2e',
    'bg_card': '#282840',
    'bg_input': '#313150',
    'fg': '#cdd6f4',
    'fg_dim': '#6c7086',
    'fg_bright': '#ffffff',
    'accent': '#89b4fa',
    'accent_hover': '#74c7ec',
    'success': '#a6e3a1',
    'error': '#f38ba8',
    'warning': '#f9e2af',
    'border': '#45475a',
    'btn_bg': '#89b4fa',
    'btn_fg': '#1e1e2e',
    'btn_hover': '#74c7ec',
    'chip_on': '#313150',
    'chip_off': '#1e1e2e',
    'chip_border_on': '#89b4fa',
    'chip_border_off': '#45475a',
    'table_header': '#313150',
    'table_row1': '#282840',
    'table_row2': '#2a2a45',
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Processador de Ocorrências")
        self.geometry("900x750")
        self.configure(bg=CORES['bg'])
        self.minsize(800, 650)

        # Estado
        self.pdf_path = tk.StringVar()
        self.xlsx_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.codigos_vars = {}
        self.codigos_update_fns = {}
        self.processando = False

        # Processador
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

    def _criar_interface(self):
        # ---- Notebook (abas) ----
        style = ttk.Style()
        style.theme_use('default')
        style.configure("App.TNotebook", background=CORES['bg'], borderwidth=0)
        style.configure("App.TNotebook.Tab",
                        background=CORES['bg_input'], foreground=CORES['fg_dim'],
                        font=("Segoe UI", 10), padding=(16, 6))
        style.map("App.TNotebook.Tab",
                  background=[('selected', CORES['bg_card'])],
                  foreground=[('selected', CORES['fg'])])

        notebook = ttk.Notebook(self, style="App.TNotebook")
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # ===== ABA PROCESSAR =====
        aba_processar = tk.Frame(notebook, bg=CORES['bg'])
        notebook.add(aba_processar, text="⚙  Processar")
        self._criar_aba_processar(aba_processar)

        # ===== ABA SOBRE =====
        aba_sobre = tk.Frame(notebook, bg=CORES['bg'])
        notebook.add(aba_sobre, text="ℹ  Sobre")
        self._criar_aba_sobre(aba_sobre)

    def _criar_aba_processar(self, parent):
        main_frame = tk.Frame(parent, bg=CORES['bg'])
        main_frame.pack(fill='both', expand=True, padx=20, pady=10)

        # ---- Cabeçalho ----
        header = tk.Frame(main_frame, bg=CORES['bg'])
        header.pack(fill='x', pady=(5, 15))

        tk.Label(header, text="⚙  Processador de Ocorrências",
                 font=("Segoe UI", 20, "bold"), fg=CORES['fg_bright'],
                 bg=CORES['bg']).pack(side='left')

        tk.Label(header, text="v1.2",
                 font=("Segoe UI", 10), fg=CORES['fg_dim'],
                 bg=CORES['bg']).pack(side='left', padx=(8, 0), pady=(8, 0))

        # ---- Seleção de Arquivos ----
        files_frame = self._criar_card(main_frame, "📁  Arquivos")

        self._criar_file_picker(files_frame, "PDF de Faltas:", self.pdf_path,
                                [("PDF", "*.pdf")], "Selecionar PDF")
        self._criar_file_picker(files_frame, "Planilha Excel:", self.xlsx_path,
                                [("Excel", "*.xlsx")], "Selecionar Excel")

        # ---- Códigos de Ocorrência ----
        codigos_frame = self._criar_card(main_frame, "🏷  Códigos de Ocorrência")

        # Botões selecionar todos / nenhum
        btn_row = tk.Frame(codigos_frame, bg=CORES['bg_card'])
        btn_row.pack(fill='x', pady=(0, 8))

        self._criar_mini_btn(btn_row, "Selecionar Todos", self._selecionar_todos).pack(side='left')
        self._criar_mini_btn(btn_row, "Limpar Seleção", self._limpar_selecao).pack(side='left', padx=(8, 0))

        # Grid de códigos
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

        # ---- Botão Processar ----
        self.btn_processar = tk.Button(
            main_frame, text="▶  PROCESSAR ARQUIVOS",
            font=("Segoe UI", 14, "bold"),
            fg=CORES['btn_fg'], bg=CORES['btn_bg'],
            activeforeground=CORES['btn_fg'], activebackground=CORES['btn_hover'],
            relief='flat', cursor='hand2', pady=12,
            command=self._iniciar_processamento
        )
        self.btn_processar.pack(fill='x', pady=(10, 5))

        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate', length=200)

        # ---- Área de Resultados ----
        self.resultado_frame = tk.Frame(main_frame, bg=CORES['bg'])
        self.resultado_frame.pack(fill='both', expand=True, pady=(5, 0))

    def _criar_aba_sobre(self, parent):
        frame = tk.Frame(parent, bg=CORES['bg'])
        frame.pack(fill='both', expand=True, padx=40, pady=40)

        # Logo / ícone
        tk.Label(frame, text="⚙", font=("Segoe UI", 56),
                 fg=CORES['accent'], bg=CORES['bg']).pack()

        # Nome do app
        tk.Label(frame, text="Processador de Ocorrências",
                 font=("Segoe UI", 22, "bold"), fg=CORES['fg_bright'],
                 bg=CORES['bg']).pack(pady=(8, 0))

        tk.Label(frame, text="Versão 1.2",
                 font=("Segoe UI", 11), fg=CORES['fg_dim'],
                 bg=CORES['bg']).pack(pady=(4, 0))

        # Separador
        tk.Frame(frame, bg=CORES['border'], height=1).pack(fill='x', pady=24)

        # Descrição
        tk.Label(frame,
                 text="Extrai ocorrências de PDFs de jornada de trabalho\n"
                      "e preenche automaticamente\n"
                      "em planilhas Excel.",
                 font=("Segoe UI", 11), fg=CORES['fg'], bg=CORES['bg'],
                 justify='center').pack()

        # Separador
        tk.Frame(frame, bg=CORES['border'], height=1).pack(fill='x', pady=24)

        # Informações do autor
        info_frame = tk.Frame(frame, bg=CORES['bg_card'],
                              highlightbackground=CORES['border'], highlightthickness=1)
        info_frame.pack(ipadx=20, ipady=16)

        campos = [
            ("Autor", "Nicolas Almeida Hader Dias"),
            ("Tecnologia", "Python 3  •  tkinter  •  pdfplumber  •  openpyxl"),
            ("Plataforma", "Windows"),
        ]

        for label, valor in campos:
            row = tk.Frame(info_frame, bg=CORES['bg_card'])
            row.pack(fill='x', padx=20, pady=4)
            tk.Label(row, text=f"{label}:", font=("Segoe UI", 10, "bold"),
                     fg=CORES['fg_dim'], bg=CORES['bg_card'], width=12,
                     anchor='w').pack(side='left')
            tk.Label(row, text=valor, font=("Segoe UI", 10),
                     fg=CORES['fg'], bg=CORES['bg_card'],
                     anchor='w').pack(side='left')

    def _criar_card(self, parent, titulo):
        card = tk.Frame(parent, bg=CORES['bg_card'], highlightbackground=CORES['border'],
                        highlightthickness=1)
        card.pack(fill='x', pady=(0, 10))

        header = tk.Frame(card, bg=CORES['bg_card'])
        header.pack(fill='x', padx=15, pady=(12, 8))

        tk.Label(header, text=titulo, font=("Segoe UI", 12, "bold"),
                 fg=CORES['fg'], bg=CORES['bg_card']).pack(side='left')

        content = tk.Frame(card, bg=CORES['bg_card'])
        content.pack(fill='x', padx=15, pady=(0, 12))
        return content

    def _criar_file_picker(self, parent, label, var, filetypes, btn_text):
        row = tk.Frame(parent, bg=CORES['bg_card'])
        row.pack(fill='x', pady=4)

        tk.Label(row, text=label, font=("Segoe UI", 10),
                 fg=CORES['fg_dim'], bg=CORES['bg_card'], width=15,
                 anchor='w').pack(side='left')

        entry = tk.Entry(row, textvariable=var, font=("Consolas", 10),
                         fg=CORES['fg'], bg=CORES['bg_input'],
                         insertbackground=CORES['fg'], relief='flat',
                         highlightbackground=CORES['border'], highlightthickness=1)
        entry.pack(side='left', fill='x', expand=True, padx=(0, 8), ipady=4)

        btn = tk.Button(row, text=btn_text, font=("Segoe UI", 9),
                        fg=CORES['accent'], bg=CORES['bg_input'],
                        activeforeground=CORES['accent_hover'],
                        activebackground=CORES['bg_input'],
                        relief='flat', cursor='hand2', padx=12,
                        command=lambda: self._escolher_arquivo(var, filetypes))
        btn.pack(side='right')

    def _escolher_arquivo(self, var, filetypes):
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            var.set(path)

    def _criar_mini_btn(self, parent, text, command):
        btn = tk.Button(parent, text=text, font=("Segoe UI", 9),
                        fg=CORES['fg_dim'], bg=CORES['bg_input'],
                        activeforeground=CORES['fg'],
                        activebackground=CORES['bg_input'],
                        relief='flat', cursor='hand2', padx=10, pady=2,
                        command=command)
        return btn

    def _criar_chip(self, parent, codigo, desc, tem_qtd, var, row, col):
        frame = tk.Frame(parent, bg=CORES['bg_card'])
        frame.grid(row=row, column=col, padx=4, pady=4, sticky='ew')

        def toggle():
            var.set(not var.get())
            atualizar_visual()

        def atualizar_visual():
            if var.get():
                chip.configure(bg=CORES['chip_on'],
                               highlightbackground=CORES['chip_border_on'])
                lbl_cod.configure(bg=CORES['chip_on'], fg=CORES['accent'])
                lbl_desc.configure(bg=CORES['chip_on'])
                if lbl_badge:
                    lbl_badge.configure(bg=CORES['chip_on'])
            else:
                chip.configure(bg=CORES['chip_off'],
                               highlightbackground=CORES['chip_border_off'])
                lbl_cod.configure(bg=CORES['chip_off'], fg=CORES['fg_dim'])
                lbl_desc.configure(bg=CORES['chip_off'])
                if lbl_badge:
                    lbl_badge.configure(bg=CORES['chip_off'])

        chip = tk.Frame(frame, bg=CORES['chip_on'], cursor='hand2',
                        highlightbackground=CORES['chip_border_on'],
                        highlightthickness=1)
        chip.pack(fill='x')

        inner = tk.Frame(chip, bg=CORES['chip_on'])
        inner.pack(fill='x', padx=10, pady=6)

        lbl_cod = tk.Label(inner, text=codigo, font=("Consolas", 12, "bold"),
                           fg=CORES['accent'], bg=CORES['chip_on'])
        lbl_cod.pack(side='left')

        lbl_desc = tk.Label(inner, text=desc, font=("Segoe UI", 9),
                            fg=CORES['fg_dim'], bg=CORES['chip_on'])
        lbl_desc.pack(side='left', padx=(6, 0))

        lbl_badge = None
        if not tem_qtd:
            lbl_badge = tk.Label(inner, text="sem qtd", font=("Segoe UI", 7),
                                 fg=CORES['warning'], bg=CORES['chip_on'])
            lbl_badge.pack(side='right')

        self.codigos_update_fns[codigo] = atualizar_visual

        for widget in [chip, inner, lbl_cod, lbl_desc]:
            widget.bind('<Button-1>', lambda e: toggle())
        if lbl_badge:
            lbl_badge.bind('<Button-1>', lambda e: toggle())

    def _selecionar_todos(self):
        for var in self.codigos_vars.values():
            var.set(True)
        # Refresh visual - rebuild
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

        # Perguntar onde salvar
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
        self.btn_processar.configure(text="⏳  Processando...", state='disabled',
                                     bg=CORES['fg_dim'])
        self.progress.pack(fill='x', pady=(5, 0))
        self.progress.start(15)

        # Limpar resultados anteriores
        for w in self.resultado_frame.winfo_children():
            w.destroy()

        # Processar em thread separada
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

    def _finalizar_processamento(self):
        self.processando = False
        self.btn_processar.configure(text="▶  PROCESSAR ARQUIVOS", state='normal',
                                     bg=CORES['btn_bg'])
        self.progress.stop()
        self.progress.pack_forget()

    def _mostrar_erro(self, msg):
        messagebox.showerror("Erro no Processamento", msg)

    def _mostrar_resultados(self, resultado, output_path):
        frame = self.resultado_frame

        # Stats
        stats_frame = tk.Frame(frame, bg=CORES['bg'])
        stats_frame.pack(fill='x', pady=(5, 8))

        stats = [
            ("No PDF", str(resultado['total_pdf']), CORES['accent']),
            ("Atualizados", str(resultado['matched']), CORES['success']),
            ("Sem match", str(len(resultado['nao_encontrados'])),
             CORES['error'] if resultado['nao_encontrados'] else CORES['success']),
        ]

        for i, (label, value, color) in enumerate(stats):
            stat = tk.Frame(stats_frame, bg=CORES['bg_card'],
                            highlightbackground=CORES['border'], highlightthickness=1)
            stat.pack(side='left', fill='x', expand=True, padx=(0 if i == 0 else 4, 0))

            tk.Label(stat, text=value, font=("Segoe UI", 24, "bold"),
                     fg=color, bg=CORES['bg_card']).pack(pady=(8, 0))
            tk.Label(stat, text=label, font=("Segoe UI", 9),
                     fg=CORES['fg_dim'], bg=CORES['bg_card']).pack(pady=(0, 8))

        # Botão abrir pasta
        btn_frame = tk.Frame(frame, bg=CORES['bg'])
        btn_frame.pack(fill='x', pady=(0, 8))

        tk.Button(btn_frame, text=f"📂  Abrir pasta do arquivo",
                  font=("Segoe UI", 10), fg=CORES['success'],
                  bg=CORES['bg_card'], activeforeground=CORES['success'],
                  activebackground=CORES['bg_input'],
                  relief='flat', cursor='hand2', pady=6,
                  command=lambda: os.startfile(os.path.dirname(output_path))
                  if os.name == 'nt' else None
                  ).pack(side='left', fill='x', expand=True)

        tk.Label(btn_frame, text=f"Salvo: {os.path.basename(output_path)}",
                 font=("Consolas", 9), fg=CORES['fg_dim'],
                 bg=CORES['bg']).pack(side='right')

        # Tabela de resultados
        if resultado['atualizados']:
            self._criar_tabela(frame, "✅  Registros Atualizados",
                               resultado['atualizados'], CORES['success'])

        if resultado['nao_encontrados']:
            self._criar_tabela(frame, "⚠  Sem Correspondência na Planilha",
                               resultado['nao_encontrados'], CORES['error'])

    def _criar_tabela(self, parent, titulo, dados, cor_titulo):
        card = tk.Frame(parent, bg=CORES['bg_card'],
                        highlightbackground=CORES['border'], highlightthickness=1)
        card.pack(fill='both', expand=True, pady=(0, 8))

        tk.Label(card, text=f"{titulo} ({len(dados)})",
                 font=("Segoe UI", 11, "bold"), fg=cor_titulo,
                 bg=CORES['bg_card'], anchor='w').pack(fill='x', padx=12, pady=(10, 4))

        # Treeview
        tree_frame = tk.Frame(card, bg=CORES['bg_card'])
        tree_frame.pack(fill='both', expand=True, padx=12, pady=(0, 10))

        style = ttk.Style()
        style.theme_use('default')
        style.configure("Custom.Treeview",
                        background=CORES['bg_card'],
                        foreground=CORES['fg'],
                        fieldbackground=CORES['bg_card'],
                        borderwidth=0,
                        font=("Consolas", 10),
                        rowheight=25)
        style.configure("Custom.Treeview.Heading",
                        background=CORES['table_header'],
                        foreground=CORES['fg'],
                        font=("Segoe UI", 10, "bold"),
                        borderwidth=0)
        style.map("Custom.Treeview",
                  background=[('selected', CORES['bg_input'])],
                  foreground=[('selected', CORES['accent'])])

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
