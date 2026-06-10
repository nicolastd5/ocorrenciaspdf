# tests/test_historico_persistencia.py
"""Testes da persistência do histórico (ui.history) em disco."""
import json

from ui import history


def _usar_caminho(monkeypatch, tmp_path, nome="hist.json"):
    caminho = tmp_path / nome
    monkeypatch.setattr(history, "_HISTORY_PATH", caminho)
    return caminho


def test_carregar_historico_inexistente_retorna_lista_vazia(tmp_path, monkeypatch):
    _usar_caminho(monkeypatch, tmp_path, "nao_existe.json")
    assert history.load() == []


def test_salvar_e_carregar_historico_roundtrip(tmp_path, monkeypatch):
    _usar_caminho(monkeypatch, tmp_path)

    entrada = {"tipo": "ocorrencias", "arquivo": "saida.pdf",
               "data": "01/01/2026 10:00", "total_pdf": 5, "matched": 4,
               "nao_encontrados": 1, "info_verif": {"modo": "unica"}}
    assert history.append(entrada) is None

    assert history.load() == [entrada]


def test_carregar_historico_arquivo_corrompido_nao_quebra(tmp_path, monkeypatch):
    caminho = _usar_caminho(monkeypatch, tmp_path)
    caminho.write_text("{ isto não é json válido", encoding="utf-8")

    assert history.load() == []


def test_carregar_historico_json_nao_lista_retorna_lista_vazia(tmp_path, monkeypatch):
    caminho = _usar_caminho(monkeypatch, tmp_path)
    caminho.write_text('{"ocorrencias": []}', encoding="utf-8")

    assert history.load() == []


def test_salvar_historico_preserva_acentos(tmp_path, monkeypatch):
    caminho = _usar_caminho(monkeypatch, tmp_path)

    history.append({"arquivo": "ocorrência.pdf", "motivo": "não localizado"})

    bruto = json.loads(caminho.read_text(encoding="utf-8"))
    assert bruto[0]["arquivo"] == "ocorrência.pdf"
    assert "ocorrência" in caminho.read_text(encoding="utf-8")  # ensure_ascii=False


def test_remove_apaga_apenas_o_indice(tmp_path, monkeypatch):
    _usar_caminho(monkeypatch, tmp_path)
    history.append({"arquivo": "a.pdf"})
    history.append({"arquivo": "b.pdf"})

    assert history.remove(0) is None
    assert [e["arquivo"] for e in history.load()] == ["b.pdf"]

    # índice fora do intervalo não quebra nem altera nada
    assert history.remove(99) is None
    assert len(history.load()) == 1


def test_clear_esvazia_historico(tmp_path, monkeypatch):
    _usar_caminho(monkeypatch, tmp_path)
    history.append({"arquivo": "a.pdf"})

    assert history.clear() is None
    assert history.load() == []


def test_append_respeita_limite_de_entradas(tmp_path, monkeypatch):
    caminho = _usar_caminho(monkeypatch, tmp_path)
    caminho.write_text(
        json.dumps([{"n": i} for i in range(history.MAX_ENTRIES)]),
        encoding="utf-8",
    )

    history.append({"n": "nova"})

    data = history.load()
    assert len(data) == history.MAX_ENTRIES
    assert data[-1] == {"n": "nova"}
    assert data[0] == {"n": 1}  # a mais antiga saiu
