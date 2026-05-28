import auto_update
from ui.update_worker import UpdateWorker


def test_worker_repassa_callbacks_e_emite_sinais(qtbot, monkeypatch):
    chamadas = {"progress": [], "status": []}

    def fake_check(on_progress=None, on_status=None):
        on_status("baixando")
        on_progress(50, 100)
        on_progress(100, 100)
        on_status("reiniciando")

    monkeypatch.setattr(auto_update, "check_and_update", fake_check)
    monkeypatch.setattr("ui.update_worker.check_and_update", fake_check)

    w = UpdateWorker()
    w.progress.connect(lambda b, t: chamadas["progress"].append((b, t)))
    w.status.connect(lambda e: chamadas["status"].append(e))

    with qtbot.waitSignal(w.finished, timeout=2000):
        w.run()

    assert chamadas["progress"] == [(50, 100), (100, 100)]
    assert chamadas["status"] == ["verificando", "baixando", "reiniciando"]
