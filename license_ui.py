import tkinter as tk
from tkinter import ttk
from typing import Optional


def show_activation_window(initial_message: str = "") -> Optional[str]:
    """Abre janela modal pedindo chave de licença. Retorna a chave ou None."""
    result: dict = {"key": None}

    root = tk.Tk()
    root.title("Ativação de licença")
    root.geometry("420x220")
    root.resizable(False, False)

    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    root.attributes("-topmost", True)
    root.after(200, lambda: root.attributes("-topmost", False))
    root.lift()
    root.focus_force()

    frm = ttk.Frame(root, padding=20)
    frm.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frm, text="Processador de Ocorrências", font=("Segoe UI", 12, "bold")).pack()

    if initial_message:
        ttk.Label(frm, text=initial_message, foreground="#a00", wraplength=380).pack(pady=(8, 0))

    ttk.Label(frm, text="Chave de licença:").pack(anchor=tk.W, pady=(12, 4))
    entry = ttk.Entry(frm, width=40)
    entry.pack(fill=tk.X)
    entry.focus_set()

    def on_activate():
        value = entry.get().strip().upper()
        if value:
            result["key"] = value
            root.destroy()

    def on_cancel():
        result["key"] = None
        root.destroy()

    btn_frame = ttk.Frame(frm)
    btn_frame.pack(fill=tk.X, pady=(16, 0))
    ttk.Button(btn_frame, text="Ativar", command=on_activate).pack(side=tk.LEFT)
    ttk.Button(btn_frame, text="Sair", command=on_cancel).pack(side=tk.RIGHT)

    root.bind("<Return>", lambda e: on_activate())
    root.bind("<Escape>", lambda e: on_cancel())
    root.protocol("WM_DELETE_WINDOW", on_cancel)

    root.mainloop()
    return result["key"]


def show_error_window(message: str) -> None:
    """Mostra diálogo de erro bloqueante."""
    root = tk.Tk()
    root.title("Erro de licença")
    root.geometry("420x180")
    root.resizable(False, False)

    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    root.attributes("-topmost", True)
    root.after(200, lambda: root.attributes("-topmost", False))
    root.lift()
    root.focus_force()

    frm = ttk.Frame(root, padding=20)
    frm.pack(fill=tk.BOTH, expand=True)
    ttk.Label(frm, text=message, wraplength=380).pack(expand=True)
    ttk.Button(frm, text="OK", command=root.destroy).pack(pady=(12, 0))

    root.bind("<Return>", lambda e: root.destroy())
    root.bind("<Escape>", lambda e: root.destroy())

    root.mainloop()
