# tests/test_processador_verificacao.py
import pytest
from processador import ProcessadorOcorrencias

proc = ProcessadorOcorrencias()

class FakePage:
    """Simula uma página do pdfplumber com extract_text()."""
    def __init__(self, text):
        self._text = text
    def extract_text(self):
        return self._text

class FakePDF:
    def __init__(self, pages):
        self.pages = pages
    def __enter__(self): return self
    def __exit__(self, *a): pass


def test_extrair_ocorrencias_texto_basico(monkeypatch):
    texto = (
        "SILVA JOAO          12345  ... AT AT FA\n"
        "SOUZA MARIA         67890  ... AT AT AT\n"
    )
    import pdfplumber

    class FakePDF2:
        pages = [FakePage(texto)]
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr(pdfplumber, 'open', lambda path: FakePDF2())
    resultado = proc.extrair_ocorrencias_texto('fake.pdf', ['AT', 'FA'])

    assert '12345' in resultado
    assert resultado['12345']['ocorrencias']['AT'] == 2
    assert resultado['12345']['ocorrencias']['FA'] == 1
    assert '67890' in resultado
    assert resultado['67890']['ocorrencias']['AT'] == 3


def test_extrair_ocorrencias_texto_sem_ocorrencias(monkeypatch):
    import pdfplumber

    class FakePDF2:
        pages = [FakePage("SILVA JOAO  12345  SD SD\n")]
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr(pdfplumber, 'open', lambda path: FakePDF2())
    resultado = proc.extrair_ocorrencias_texto('fake.pdf', ['AT'])
    assert resultado == {}
