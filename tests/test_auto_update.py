# tests/test_auto_update.py
import auto_update


class FakeResponse:
    """Simula um requests.Response usado como context manager + stream."""
    def __init__(self, chunks, content_length=None):
        self._chunks = chunks
        self.headers = {}
        if content_length is not None:
            self.headers['Content-Length'] = str(content_length)

    def __enter__(self): return self
    def __exit__(self, *a): pass
    def raise_for_status(self): pass
    def iter_content(self, chunk_size=65536):
        for c in self._chunks:
            yield c


def _patch_download(monkeypatch, response, tmp_path):
    """Faz requests.get devolver `response` e isola exit/subprocess/tempdir."""
    monkeypatch.setattr(auto_update.requests, 'get', lambda *a, **k: response)
    monkeypatch.setattr(auto_update.tempfile, 'mkdtemp', lambda: str(tmp_path))
    monkeypatch.setattr(auto_update.subprocess, 'Popen', lambda *a, **k: None)
    # sys.exit som é chamado no modo legado; intercepta para nao matar o teste
    def _no_exit(code=0):
        raise SystemExit(code)
    monkeypatch.setattr(auto_update.sys, 'exit', _no_exit)
    # sys.executable aponta para um caminho dentro de tmp_path (current_exe)
    monkeypatch.setattr(auto_update.sys, 'executable',
                        str(tmp_path / 'ProcessadorOcorrencias-v1.00.exe'))


def test_download_chama_on_progress_com_baixado_e_total(monkeypatch, tmp_path):
    chunks = [b'x' * 100, b'y' * 50]  # total 150 bytes
    resp = FakeResponse(chunks, content_length=150)
    _patch_download(monkeypatch, resp, tmp_path)

    eventos = []
    try:
        auto_update._download_and_relaunch(
            'novo.exe',
            on_progress=lambda baixado, total: eventos.append((baixado, total)),
            on_status=lambda estado: None,
        )
    except SystemExit:
        pass

    assert eventos == [(100, 150), (150, 150)]
