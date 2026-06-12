"""O diálogo de atualização manual também não pode tocar widgets fora da GUI.

Mesma regressão do _run_auto_update: handlers soltos conectados a sinais de
worker em QThread executam na thread do worker (crash em Qt6Gui.dll).
"""
from types import SimpleNamespace

from PySide6.QtCore import QThread

from ui.update_dialog import run_update_dialog


def test_handlers_do_dialogo_rodam_na_thread_principal(qtbot, monkeypatch):
    main_thread = QThread.currentThread()
    chamadas = []  # (evento, thread em que rodou)

    class FakeDialog:
        canceled = SimpleNamespace(connect=lambda *a, **k: None)

        def __init__(self, *a, **k):
            pass

        def setValue(self, v):
            chamadas.append(("progress", QThread.currentThread()))

        def __getattr__(self, name):
            return lambda *a, **k: None  # demais métodos de UI são irrelevantes

    class FakeMessageBox:
        @staticmethod
        def information(*a, **k):
            chamadas.append(("fim", QThread.currentThread()))

        @staticmethod
        def warning(*a, **k):
            chamadas.append(("fim", QThread.currentThread()))

    def fake_check(on_progress=None, on_status=None):
        on_progress(50, 100)
        on_status("erro")

    monkeypatch.setattr("ui.update_dialog.QProgressDialog", FakeDialog)
    monkeypatch.setattr("ui.update_dialog.QMessageBox", FakeMessageBox)
    monkeypatch.setattr("ui.update_worker.check_and_update", fake_check)

    run_update_dialog(None)
    qtbot.waitUntil(lambda: ("fim", main_thread) in chamadas
                    or any(e == "fim" for e, _ in chamadas), timeout=3000)

    assert [e for e, _ in chamadas] == ["progress", "fim"]
    erradas = [e for e, t in chamadas if t is not main_thread]
    assert not erradas, f"handlers rodaram fora da thread da GUI: {erradas}"
