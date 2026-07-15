from core.processador import ProcessadorOcorrencias


def test_montar_motivo_ordena_e_quantifica():
    p = ProcessadorOcorrencias()
    ocorr = {'AT': 2, 'FA': 1, 'AP': 3}
    assert p.montar_motivo(ocorr, ['FA', 'AT', 'AP']) == 'FA, 2 AT, AP'


def test_reconciliar_concordantes_e_conflitos():
    p = ProcessadorOcorrencias()
    v1 = {'12345': {'nome': 'ANA', 'ocorrencias': {'FA': 1, 'AT': 2}}}
    v2 = {'12345': {'nome': 'ANA', 'ocorrencias': {'FA': 1, 'AT': 3}}}
    r = p.reconciliar([v1, v2], ['FA', 'AT'])
    assert r['concordantes']['12345']['ocorrencias'] == {'FA': 1}
    assert len(r['conflitos']) == 1
    assert r['conflitos'][0]['codigo'] == 'AT'
    assert r['conflitos'][0]['sugestao'] == 3


def test_ia_removida():
    assert not hasattr(ProcessadorOcorrencias, 'verificar_com_ia')


def test_montar_motivo_config_extras_ordem_e_quantidade():
    p = ProcessadorOcorrencias()
    extras = [{"codigo": "BB", "com_quantidade": False},
              {"codigo": "FR", "com_quantidade": True}]
    ocorr = {"FR": 2, "FA": 1, "BB": 3}
    # embutido (FA) vem primeiro; extras depois na ordem recebida;
    # BB sem quantidade mesmo com contagem 3; FR com quantidade.
    assert p.montar_motivo(ocorr, ["FA", "FR", "BB"], extras) == "FA, BB, 2 FR"


def test_montar_motivo_sem_extras_inalterado():
    p = ProcessadorOcorrencias()
    ocorr = {"AT": 2, "FA": 1, "AP": 3}
    assert p.montar_motivo(ocorr, ["FA", "AT", "AP"]) == "FA, 2 AT, AP"


def test_processar_aceita_config_extras():
    import inspect
    sig = inspect.signature(ProcessadorOcorrencias.processar)
    assert "config_extras" in sig.parameters
