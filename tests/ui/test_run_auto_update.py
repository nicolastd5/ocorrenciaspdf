"""O download roda numa QThread; o splash só pode ser tocado na thread da GUI.

Regressão do crash 0xc0000005 em Qt6Gui.dll: os handlers de progress/status
eram funções soltas, executadas na thread do worker, e pintavam o splash de lá.
"""
import importlib.util
from pathlib import Path

from PySide6.QtCore import QThread

# Importa o app.py da raiz por caminho: na suíte completa o pacote
# license-server/app/ ocupa o nome "app" em sys.modules.
_spec = importlib.util.spec_from_file_location(
    "_app_entrypoint", Path(__file__).parents[2] / "app.py")
app_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(app_module)


def test_handlers_de_update_rodam_na_thread_principal(qtbot, monkeypatch):
    main_thread = QThread.currentThread()
    chamadas = []  # (metodo, thread em que rodou)

    class FakeSplash:
        def set_status(self, texto):
            chamadas.append(("set_status", QThread.currentThread()))

        def set_progress(self, frac, texto):
            chamadas.append(("set_progress", QThread.currentThread()))

    def fake_check(on_progress=None, on_status=None):
        on_progress(50, 100)
        on_progress(100, 100)
        on_status("reiniciando")

    monkeypatch.setattr("ui.update_worker.check_and_update", fake_check)

    estado = app_module._run_auto_update(FakeSplash())

    assert estado == "reiniciando"
    assert [m for m, _ in chamadas] == ["set_status", "set_progress", "set_progress"]
    threads_erradas = [m for m, t in chamadas if t is not main_thread]
    assert not threads_erradas, f"handlers rodaram fora da thread da GUI: {threads_erradas}"
