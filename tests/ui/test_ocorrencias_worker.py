import ui.tabs.ocorrencias as oco


class _FakeProc:
    def __init__(self):
        _FakeProc.last = self
        self.chamadas = []
    def extrair_ocorrencias(self, pdf, cods):
        self.chamadas.append("v1"); return {"1": {"nome": "A", "ocorrencias": {"FA": 1}}}
    def extrair_ocorrencias_texto(self, pdf, cods):
        self.chamadas.append("v2"); return {"1": {"nome": "A", "ocorrencias": {"FA": 1}}}
    def verificar_com_ia(self, pdf, cods, key, modelo):
        self.chamadas.append("ia"); return None
    def reconciliar(self, camadas, cods):
        self.chamadas.append(f"rec:{len(camadas)}")
        return {"concordantes": {"1": {"nome": "A", "ocorrencias": {"FA": 1}}}, "conflitos": []}
    def processar(self, pdf, xlsx, out, cods, progress_cb=None, dados_externos=None, **kw):
        self.chamadas.append(f"proc:ext={dados_externos is not None}")
        if progress_cb: progress_cb(100, "ok")
        return {"matched": 1, "total_pdf": 1}


def test_worker_modo_unica_nao_reconcilia(qtbot, monkeypatch):
    monkeypatch.setattr(oco, "ProcessadorOcorrencias", _FakeProc)
    w = oco.OcorrenciasWorker("a.pdf", "b.xlsx", "out.xlsx", ["FA"], "unica", "", "m")
    with qtbot.waitSignal(w.finished, timeout=3000) as bl:
        w.run()
    assert bl.args[0]["status"] == "ok"
    assert "proc:ext=False" in _FakeProc.last.chamadas
    assert not any(c.startswith("rec") for c in _FakeProc.last.chamadas)


def test_worker_modo_dupla_reconcilia_sem_conflitos(qtbot, monkeypatch):
    monkeypatch.setattr(oco, "ProcessadorOcorrencias", _FakeProc)
    w = oco.OcorrenciasWorker("a.pdf", "b.xlsx", "out.xlsx", ["FA"], "dupla", "", "m")
    with qtbot.waitSignal(w.finished, timeout=3000) as bl:
        w.run()
    assert bl.args[0]["status"] == "ok"
    c = _FakeProc.last.chamadas
    assert "v1" in c and "v2" in c and "rec:2" in c and "proc:ext=True" in c


def test_worker_modo_ia_fallback_quando_ia_none(qtbot, monkeypatch):
    monkeypatch.setattr(oco, "ProcessadorOcorrencias", _FakeProc)
    w = oco.OcorrenciasWorker("a.pdf", "b.xlsx", "out.xlsx", ["FA"], "ia", "k", "m")
    with qtbot.waitSignal(w.finished, timeout=3000) as bl:
        w.run()
    assert bl.args[0]["info_verif"]["ia_fallback"] is True
    assert "rec:2" in _FakeProc.last.chamadas
