# tests/test_historico_persistencia.py
"""Testes da persistência do histórico de Ocorrências e VT Caixa em disco."""
import json
import app


def test_carregar_historico_inexistente_retorna_listas_vazias(tmp_path, monkeypatch):
    monkeypatch.setattr(app, '_HISTORICO_PATH', str(tmp_path / 'nao_existe.json'))
    dados = app._carregar_historico()
    assert dados == {'ocorrencias': [], 'vtcaixa': []}


def test_salvar_e_carregar_historico_roundtrip(tmp_path, monkeypatch):
    caminho = str(tmp_path / 'hist.json')
    monkeypatch.setattr(app, '_HISTORICO_PATH', caminho)

    ocorrencias = [{'arquivo': 'saida.pdf', 'data': '01/01/2026 10:00',
                    'total_pdf': 5, 'matched': 4, 'nao_encontrados': 1,
                    'lista_nao_encontrados': [], 'info_verif': {'modo': 'unica'}}]
    vtcaixa = [{'arquivo': 'vt.csv', 'data': '01/01/2026 11:00', 'total_ok': 3}]

    erro = app._salvar_historico(ocorrencias, vtcaixa)
    assert erro is None

    dados = app._carregar_historico()
    assert dados['ocorrencias'] == ocorrencias
    assert dados['vtcaixa'] == vtcaixa


def test_carregar_historico_arquivo_corrompido_nao_quebra(tmp_path, monkeypatch):
    caminho = tmp_path / 'hist.json'
    caminho.write_text('{ isto não é json válido', encoding='utf-8')
    monkeypatch.setattr(app, '_HISTORICO_PATH', str(caminho))

    dados = app._carregar_historico()
    assert dados == {'ocorrencias': [], 'vtcaixa': []}


def test_salvar_historico_preserva_acentos(tmp_path, monkeypatch):
    caminho = str(tmp_path / 'hist.json')
    monkeypatch.setattr(app, '_HISTORICO_PATH', caminho)

    ocorrencias = [{'arquivo': 'ocorrência.pdf', 'motivo': 'não localizado'}]
    app._salvar_historico(ocorrencias, [])

    bruto = json.loads(open(caminho, encoding='utf-8').read())
    assert bruto['ocorrencias'][0]['arquivo'] == 'ocorrência.pdf'
