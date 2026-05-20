import tkinter as tk
from typing import Optional


# Paleta compartilhada com app.py (subset do design system, accent blue)
_BG          = '#0a0b12'
_SURFACE     = '#14161f'
_INPUT       = '#0e1019'
_BORDER      = '#262a3a'
_BORDER_2    = '#353a52'
_ACCENT      = '#5b8def'
_ACCENT_HOVER = '#7aa3f5'
_FG          = '#b4b8cc'
_FG_BRIGHT   = '#e6e8f0'
_FG_DIM      = '#6e7591'
_ERROR       = '#f87171'


def _centralizar(root: tk.Tk) -> None:
    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")


def _criar_root(title: str, w: int, h: int) -> tk.Tk:
    root = tk.Tk()
    root.title(title)
    root.geometry(f"{w}x{h}")
    root.resizable(False, False)
    root.configure(bg=_BG)

    _centralizar(root)
    root.attributes("-topmost", True)
    root.after(200, lambda: root.attributes("-topmost", False))
    root.lift()
    root.focus_force()
    return root


def show_activation_window(initial_message: str = "") -> Optional[str]:
    """Abre janela modal pedindo chave de licença. Retorna a chave ou None."""
    result: dict = {"key": None}

    root = _criar_root("Ativação de licença", 460, 320)

    # Card central
    card = tk.Frame(root, bg=_SURFACE,
                    highlightbackground=_BORDER_2, highlightthickness=1)
    card.pack(fill='both', expand=True, padx=24, pady=24)

    # Top highlight
    tk.Frame(card, bg=_BORDER_2, height=1).pack(fill='x', side='top')

    inner = tk.Frame(card, bg=_SURFACE)
    inner.pack(fill='both', expand=True, padx=22, pady=20)

    tk.Label(inner, text="Processador de Ocorrências",
             font=("Inter", 14, "bold"),
             fg=_FG_BRIGHT, bg=_SURFACE).pack(anchor='w')

    tk.Label(inner, text="Insira sua chave para liberar o aplicativo.",
             font=("Inter", 9), fg=_FG_DIM, bg=_SURFACE).pack(anchor='w', pady=(2, 0))

    if initial_message:
        tk.Label(inner, text=initial_message,
                 font=("Inter", 9), fg=_ERROR, bg=_SURFACE,
                 wraplength=380, justify='left').pack(anchor='w', pady=(10, 0))

    tk.Label(inner, text="CHAVE DE LICENÇA",
             font=("Inter", 8, "bold"), fg=_FG_DIM, bg=_SURFACE).pack(
        anchor='w', pady=(14, 4))

    entry = tk.Entry(inner, font=("JetBrains Mono", 11),
                     fg=_FG_BRIGHT, bg=_INPUT,
                     insertbackground=_FG_BRIGHT, relief='flat',
                     highlightbackground=_BORDER, highlightthickness=1,
                     highlightcolor=_ACCENT)
    entry.pack(fill='x', ipady=7)
    entry.focus_set()

    def on_activate():
        value = entry.get().strip().upper()
        if value:
            result["key"] = value
            root.destroy()

    def on_cancel():
        result["key"] = None
        root.destroy()

    btn_row = tk.Frame(inner, bg=_SURFACE)
    btn_row.pack(fill='x', pady=(18, 0))

    btn_ativar = tk.Button(btn_row, text="Ativar",
                           font=("Inter", 10, "bold"),
                           fg='#ffffff', bg=_ACCENT,
                           activeforeground='#ffffff', activebackground=_ACCENT_HOVER,
                           relief='flat', cursor='hand2', padx=18, pady=8, borderwidth=0,
                           command=on_activate)
    btn_ativar.pack(side='left')

    btn_sair = tk.Button(btn_row, text="Sair",
                         font=("Inter", 10),
                         fg=_FG, bg=_INPUT,
                         activeforeground=_FG_BRIGHT, activebackground=_BORDER,
                         relief='flat', cursor='hand2', padx=14, pady=8, borderwidth=0,
                         highlightbackground=_BORDER, highlightthickness=1,
                         command=on_cancel)
    btn_sair.pack(side='right')

    root.bind("<Return>", lambda e: on_activate())
    root.bind("<Escape>", lambda e: on_cancel())
    root.protocol("WM_DELETE_WINDOW", on_cancel)

    root.mainloop()
    return result["key"]


def show_error_window(message: str) -> None:
    """Mostra diálogo de erro bloqueante."""
    root = _criar_root("Erro de licença", 460, 240)

    card = tk.Frame(root, bg=_SURFACE,
                    highlightbackground=_BORDER_2, highlightthickness=1)
    card.pack(fill='both', expand=True, padx=24, pady=24)
    tk.Frame(card, bg=_BORDER_2, height=1).pack(fill='x', side='top')

    inner = tk.Frame(card, bg=_SURFACE)
    inner.pack(fill='both', expand=True, padx=22, pady=20)

    tk.Label(inner, text="Erro de licença",
             font=("Inter", 13, "bold"),
             fg=_ERROR, bg=_SURFACE).pack(anchor='w')

    tk.Label(inner, text=message,
             font=("Inter", 10), fg=_FG, bg=_SURFACE,
             wraplength=380, justify='left').pack(anchor='w', pady=(10, 0))

    tk.Button(inner, text="OK",
              font=("Inter", 10, "bold"),
              fg='#ffffff', bg=_ACCENT,
              activeforeground='#ffffff', activebackground=_ACCENT_HOVER,
              relief='flat', cursor='hand2', padx=18, pady=8, borderwidth=0,
              command=root.destroy).pack(anchor='e', pady=(16, 0))

    root.bind("<Return>", lambda e: root.destroy())
    root.bind("<Escape>", lambda e: root.destroy())

    root.mainloop()
