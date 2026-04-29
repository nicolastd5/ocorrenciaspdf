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


def test_reconciliar_sem_conflito():
    v1 = {'12345': {'nome': 'SILVA', 'ocorrencias': {'AT': 2, 'FA': 1}}}
    v2 = {'12345': {'nome': 'SILVA', 'ocorrencias': {'AT': 2, 'FA': 1}}}
    resultado = proc.reconciliar([v1, v2], ['AT', 'FA'])
    assert '12345' in resultado['concordantes']
    assert resultado['conflitos'] == []


def test_reconciliar_com_conflito():
    v1 = {'12345': {'nome': 'SILVA', 'ocorrencias': {'AT': 2}}}
    v2 = {'12345': {'nome': 'SILVA', 'ocorrencias': {'AT': 1}}}
    resultado = proc.reconciliar([v1, v2], ['AT'])
    assert resultado['concordantes'] == {}
    assert len(resultado['conflitos']) == 1
    c = resultado['conflitos'][0]
    assert c['re'] == '12345'
    assert c['codigo'] == 'AT'
    assert c['valores']['v1'] == 2
    assert c['valores']['v2'] == 1
    assert c['sugestao'] == 2  # v1 e v2 empatam → usa o maior


def test_reconciliar_maioria_vence():
    v1 = {'12345': {'nome': 'SILVA', 'ocorrencias': {'AT': 2}}}
    v2 = {'12345': {'nome': 'SILVA', 'ocorrencias': {'AT': 1}}}
    ia = {'12345': {'nome': 'SILVA', 'ocorrencias': {'AT': 2}}}
    resultado = proc.reconciliar([v1, v2, ia], ['AT'])
    # 2 votos em AT=2, 1 voto em AT=1 → sem conflito (maioria clara)
    assert '12345' in resultado['concordantes']
    assert resultado['concordantes']['12345']['ocorrencias']['AT'] == 2
    assert resultado['conflitos'] == []


def test_reconciliar_re_ausente_em_uma_camada():
    # RE presente na V1 mas não na V2 → conflito com v2=0
    v1 = {'12345': {'nome': 'SILVA', 'ocorrencias': {'AT': 1}}}
    v2 = {}
    resultado = proc.reconciliar([v1, v2], ['AT'])
    assert len(resultado['conflitos']) == 1
    c = resultado['conflitos'][0]
    assert c['valores']['v1'] == 1
    assert c['valores']['v2'] == 0
