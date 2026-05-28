import ui.tabs.vt_caixa as vt


class _FakeProc:
    def __init__(self):
        _FakeProc.last = self
        self.kwargs = None
    def processar(self, fonte, xls, out, progress_cb=None, usar_ia=False, api_key='', model_id='gemini-2.5-flash'):
        self.kwargs = dict(usar_ia=usar_ia, api_key=api_key, model_id=model_id)
        if progress_cb: progress_cb(100, "ok")
        return {"total_ok": 5, "total_pdf": 7}


def test_worker_ok_reporta_totais(qtbot, monkeypatch):
    monkeypatch.setattr(vt, "ProcessadorVTCaixa", _FakeProc)
    w = vt.VTCaixaWorker("f.pdf", "c.xlsx", "out.csv", False, "", "m")
    with qtbot.waitSignal(w.finished, timeout=3000) as bl:
        w.run()
    info = bl.args[0]
    assert info["status"] == "ok"
    assert info["total_ok"] == 5 and info["total_pdf"] == 7
    assert _FakeProc.last.kwargs["usar_ia"] is False


def test_worker_repassa_flags_ia(qtbot, monkeypatch):
    monkeypatch.setattr(vt, "ProcessadorVTCaixa", _FakeProc)
    w = vt.VTCaixaWorker("f.pdf", "c.xlsx", "out.csv", True, "KEY", "gemini-2.5-pro")
    with qtbot.waitSignal(w.finished, timeout=3000):
        w.run()
    k = _FakeProc.last.kwargs
    assert k["usar_ia"] is True and k["api_key"] == "KEY" and k["model_id"] == "gemini-2.5-pro"
