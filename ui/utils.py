"""Utilitários pequenos compartilhados pela UI."""
import os
import subprocess
import sys


def open_path(p: str) -> None:
    """Abre arquivo ou pasta no aplicativo padrão do sistema."""
    if not p:
        return
    if sys.platform == "win32":
        os.startfile(p)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", p])
    else:
        subprocess.Popen(["xdg-open", p])
