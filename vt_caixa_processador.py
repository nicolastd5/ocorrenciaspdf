import csv
import re
import unicodedata
from datetime import date, datetime

import pdfplumber
import xlrd

COLUNAS_CSV = [
    'CNPJ', 'CEP', 'LOGRADOURO', 'NÚMERO', 'COMPLEMENTO', 'PONTO REFERENCIA',
    'UF', 'ESTADO', 'MATRÍCULA', 'NOME DO FUNCIONÁRIO', 'CPF', 'RG',
    'DATA DE NASCIMENTO', 'CARGO', 'DEPARTAMENTO', 'NOME DA MÃE',
    'BENEFÍCIO DO FUNCIONÁRIO', 'VALOR UNITÁRIO', 'QUANTIDADE DIÁRIA',
    'PERÍODO DE DIAS TRABALHADOS', 'TIPO VALOR', 'REDE RECARGA',
    'CEP RESIDENCIAL', 'LOGRADOURO RESIDENCIAL', 'NÚMERO RESIDENCIAL',
    'COMPLEMENTO RESIDENCIAL', 'ESTADO CIVIL', 'DATA DE EMISSÃO DO RG',
    'ÓRGÃO EXPEDIDOR', 'ESTADO EMISSÃO RG',
]

_COL_ALIASES = {
    'cod epr':            'Cód Epr',
    'cpf':                'CPF',
    'rg':                 'RG',
    'uf rg':              'UF RG',
    'orgao rg':           'Orgão RG',
    'data nascimento':    'Data nascimento',
    'data de nascimento': 'Data nascimento',
    'descricao cargo':    'Descrição cargo',
    'cod ccusto':         'Descrição Ccusto',
    'descricao ccusto':   'Descrição Ccusto',
    'endereco':           'Endereço',
    'numero':             'Numero',
    'complemento':        'Complemento',
    'cep':                'Cep',
    'cidade':             'Cidade',
    'uf end':             'UF End',
    'estado civil':       'Estado Civil',
}


# ──────────────────────────────────────────────────────────────────────────────
# Funções auxiliares de módulo
# ──────────────────────────────────────────────────────────────────────────────

def _norm(texto):
    """Remove acentos e converte para minúsculas para comparação robusta."""
    return unicodedata.normalize('NFKD', str(texto)).encode('ascii', 'ignore').decode().lower().strip()


def _extrair_codigo(valor):
    """Extrai código numérico de célula, lidando com '123.0', '  123 ', etc."""
    if valor is None:
        return ''
    s = str(valor).strip().replace('\n', '').replace('\r', '')
    s = re.sub(r'\.0+$', '', s)
    m = re.match(r'^(\d+)', s)
    return m.group(1) if m else ''


def _pode_latin1(c):
    """Verifica se o caractere pode ser codificado em latin-1."""
    try:
        c.encode('latin-1')
        return True
    except UnicodeEncodeError:
        return False


def _mascarar_pii(registros):
    """Substitui dados pessoais por indicadores de presença para envio à IA."""
    mascarados = []
    for r in registros:
        def _pres(v):
            return 'preenchido' if str(v).strip() else 'vazio'

        def _ano_nasc(v):
            m = re.search(r'\d{4}', str(v))
            return m.group(0) if m else ('preenchido' if v else 'vazio')

        mascarados.append({
            'MATRÍCULA':                   r['MATRÍCULA'],
            'NOME DO FUNCIONÁRIO':         r['NOME DO FUNCIONÁRIO'],
            'CPF':                         _pres(r['CPF']),
            'RG':                          _pres(r['RG']),
            'DATA DE NASCIMENTO':          _ano_nasc(r['DATA DE NASCIMENTO']),
            'CEP':                         _pres(r['CEP']),
            'VALOR UNITÁRIO':              r['VALOR UNITÁRIO'],
            'QUANTIDADE DIÁRIA':           r['QUANTIDADE DIÁRIA'],
            'PERÍODO DE DIAS TRABALHADOS': r['PERÍODO DE DIAS TRABALHADOS'],
            'BENEFÍCIO DO FUNCIONÁRIO':    r['BENEFÍCIO DO FUNCIONÁRIO'],
            'CARGO':                       r['CARGO'],
        })
    return mascarados


# ──────────────────────────────────────────────────────────────────────────────
# Classe principal
# ──────────────────────────────────────────────────────────────────────────────

class ProcessadorVTCaixa:

    # ── Extração PDF ───────────────────────────────────────────────────

    def _extrair_pdf(self, pdf_path):
        rows = []
        avisos = []

        with pdfplumber.open(pdf_path) as pdf:
            for pagina in pdf.pages:
                tabela = pagina.extract_table()
                if not tabela:
                    tabelas = pagina.extract_tables()
                    tabela = tabelas[0] if tabelas else None
                if not tabela:
                    continue

                for linha in tabela:
                    if not linha or all(c is None for c in linha):
                        continue

                    codigo = _extrair_codigo(linha[0])
                    if not codigo:
                        continue

                    while len(linha) < 9:
                        linha.append(None)

                    def _cel(idx, ln=linha):
                        v = ln[idx]
                        return str(v).strip().replace('\n', ' ').replace('\r', '') if v is not None else ''

                    rows.append({
                        'codigo':         codigo,
                        'colaborador':    _cel(1),
                        'periodo':        _cel(3),
                        'quantidade':     _cel(5),
                        'valor_unitario': _cel(6),
                        'administradora': _cel(8),
                    })

        if not rows:
            avisos.append('AVISO: Nenhuma linha de dados extraída do PDF.')

        return rows, avisos

    # ── Dias úteis ─────────────────────────────────────────────────────

    def _calcular_dias_uteis(self, periodo_str):
        if not periodo_str:
            return 0

        partes = None

        # Padrão 1: 'dd/mm/yyyy a dd/mm/yyyy'  ou  'dd/mm/yyyy - dd/mm/yyyy'
        m = re.match(
            r'(\d{2}/\d{2}/\d{4})\s+(?:[aA]|-)\s+(\d{2}/\d{2}/\d{4})',
            periodo_str.strip()
        )
        if m:
            partes = [m.group(1), m.group(2)]

        # Padrão 2: 'dd/mm/yyyy-dd/mm/yyyy'  (sem espaços ao redor do hífen)
        if not partes:
            m = re.match(
                r'(\d{2}/\d{2}/\d{4})-(\d{2}/\d{2}/\d{4})',
                periodo_str.strip()
            )
            if m:
                partes = [m.group(1), m.group(2)]

        if not partes:
            return 0

        try:
            inicio = datetime.strptime(partes[0], '%d/%m/%Y').date()
            fim    = datetime.strptime(partes[1], '%d/%m/%Y').date()
        except ValueError:
            return 0

        dias = 0
        atual = inicio
        while atual <= fim:
            if atual.weekday() < 5:
                dias += 1
            atual = date.fromordinal(atual.toordinal() + 1)
        return dias

    # ── Formatadores ───────────────────────────────────────────────────

    def _formatar_cpf(self, valor):
        if valor is None:
            return ''
        if isinstance(valor, float):
            valor = int(valor)
        digits = re.sub(r'\D', '', str(valor).split('.')[0])
        return digits.zfill(11) if digits else ''

    def _formatar_rg(self, valor):
        if valor is None:
            return ''
        if isinstance(valor, float):
            valor = int(valor)
        return str(valor).strip().split('.')[0]

    def _formatar_data(self, valor, wb):
        if valor is None or valor == '':
            return ''
        if isinstance(valor, float):
            try:
                dt = xlrd.xldate_as_datetime(valor, wb.datemode)
                return dt.strftime('%d/%m/%Y')
            except Exception:
                return str(valor)
        return str(valor).strip()

    def _formatar_cep(self, valor):
        if valor is None:
            return ''
        if isinstance(valor, float):
            valor = int(valor)
        digits = re.sub(r'\D', '', str(valor).split('.')[0])
        return digits.zfill(8) if digits else ''

    def _formatar_numero(self, valor):
        if valor is None:
            return ''
        if isinstance(valor, float):
            valor = int(valor)
        return str(valor).strip().split('.')[0]

    # ── Carregar Excel ─────────────────────────────────────────────────

    def _carregar_excel(self, xls_path):
        wb = xlrd.open_workbook(xls_path)
        ws = wb.sheet_by_index(0)
        avisos = []

        cabecalhos_norm = {}
        cabecalhos_orig = {}
        for col in range(ws.ncols):
            val = ws.cell_value(0, col)
            if val:
                n = _norm(val)
                cabecalhos_norm[n] = col
                cabecalhos_orig[n] = str(val).strip()

        avisos.append(f'Colunas no Excel: {list(cabecalhos_orig.values())}')

        def _idx(nome_interno):
            alvo = _norm(nome_interno)
            if alvo in cabecalhos_norm:
                return cabecalhos_norm[alvo]
            for alias, chave in _COL_ALIASES.items():
                if _norm(chave) == alvo and _norm(alias) in cabecalhos_norm:
                    return cabecalhos_norm[_norm(alias)]
            for n, idx in cabecalhos_norm.items():
                if alvo in n or n in alvo:
                    return idx
            return None

        idx_cod     = _idx('Cód Epr')
        idx_cpf     = _idx('CPF')
        idx_rg      = _idx('RG')
        idx_uf_rg   = _idx('UF RG')
        idx_org_rg  = _idx('Orgão RG')
        idx_dt_nasc = _idx('Data nascimento')
        idx_cargo   = _idx('Descrição cargo')
        idx_ccusto  = _idx('Descrição Ccusto')
        idx_end     = _idx('Endereço')
        idx_num     = _idx('Numero')
        idx_comp    = _idx('Complemento')
        idx_cep     = _idx('Cep')
        idx_cidade  = _idx('Cidade')
        idx_uf_end  = _idx('UF End')
        idx_est_civ = _idx('Estado Civil')

        if idx_cod is None:
            raise ValueError(
                f"Coluna 'Cód Epr' não encontrada.\n"
                f"Disponíveis: {list(cabecalhos_orig.values())}"
            )

        avisos.append(
            f'Mapeamento: cod={idx_cod}, cpf={idx_cpf}, rg={idx_rg}, '
            f'nascimento={idx_dt_nasc}, cargo={idx_cargo}, ccusto={idx_ccusto}'
        )

        dados = {}
        for row in range(1, ws.nrows):
            cod_raw = ws.cell_value(row, idx_cod)
            if cod_raw is None or cod_raw == '':
                continue
            chave = _extrair_codigo(cod_raw) or str(cod_raw).strip()
            if not chave:
                continue

            def _val(idx, r=row):
                if idx is None:
                    return ''
                v = ws.cell_value(r, idx)
                if v is None or v == '':
                    return ''
                if isinstance(v, float):
                    return str(int(v))
                return str(v).strip()

            dados[chave] = {
                'CPF':              self._formatar_cpf(ws.cell_value(row, idx_cpf) if idx_cpf is not None else None),
                'RG':               self._formatar_rg(ws.cell_value(row, idx_rg) if idx_rg is not None else None),
                'UF RG':            _val(idx_uf_rg),
                'Orgão RG':         _val(idx_org_rg),
                'Data nascimento':  self._formatar_data(ws.cell_value(row, idx_dt_nasc) if idx_dt_nasc is not None else None, wb),
                'Descrição cargo':  _val(idx_cargo),
                'Descrição Ccusto': _val(idx_ccusto),
                'Endereço':         _val(idx_end),
                'Numero':           self._formatar_numero(ws.cell_value(row, idx_num) if idx_num is not None else None),
                'Complemento':      _val(idx_comp),
                'Cep':              self._formatar_cep(ws.cell_value(row, idx_cep) if idx_cep is not None else None),
                'Cidade':           _val(idx_cidade),
                'UF End':           _val(idx_uf_end),
                'Estado Civil':     _val(idx_est_civ),
            }

        return dados, avisos

    # ── Cruzamento ─────────────────────────────────────────────────────

    def _limpar_valor_unitario(self, valor_str):
        v = valor_str.replace('R$', '').strip()
        return v.replace('.', '').replace(',', '.')

    def _cruzar_dados(self, pdf_rows, excel_data):
        registros = []
        nao_encontrados = []

        for linha in pdf_rows:
            codigo = linha['codigo']
            ex = excel_data.get(codigo)

            if ex is None:
                nao_encontrados.append(f"{codigo} - {linha['colaborador']}")
                continue

            registros.append({
                'CNPJ':                        '',
                'CEP':                         ex['Cep'],
                'LOGRADOURO':                  ex['Endereço'],
                'NÚMERO':                      ex['Numero'],
                'COMPLEMENTO':                 ex['Complemento'],
                'PONTO REFERENCIA':            '',
                'UF':                          ex['UF End'],
                'ESTADO':                      ex['Cidade'],
                'MATRÍCULA':                   codigo,
                'NOME DO FUNCIONÁRIO':         linha['colaborador'],
                'CPF':                         ex['CPF'],
                'RG':                          ex['RG'],
                'DATA DE NASCIMENTO':          ex['Data nascimento'],
                'CARGO':                       ex['Descrição cargo'],
                'DEPARTAMENTO':                ex['Descrição Ccusto'],
                'NOME DA MÃE':                 '',
                'BENEFÍCIO DO FUNCIONÁRIO':    linha['administradora'],
                'VALOR UNITÁRIO':              self._limpar_valor_unitario(linha['valor_unitario']),
                'QUANTIDADE DIÁRIA':           linha['quantidade'],
                'PERÍODO DE DIAS TRABALHADOS': str(self._calcular_dias_uteis(linha['periodo'])),
                'TIPO VALOR':                  '',
                'REDE RECARGA':                linha['administradora'],
                'CEP RESIDENCIAL':             ex['Cep'],
                'LOGRADOURO RESIDENCIAL':      ex['Endereço'],
                'NÚMERO RESIDENCIAL':          ex['Numero'],
                'COMPLEMENTO RESIDENCIAL':     ex['Complemento'],
                'ESTADO CIVIL':                ex['Estado Civil'],
                'DATA DE EMISSÃO DO RG':       '',
                'ÓRGÃO EXPEDIDOR':             ex['Orgão RG'],
                'ESTADO EMISSÃO RG':           ex['UF RG'],
            })

        return registros, nao_encontrados

    # ── Geração CSV ────────────────────────────────────────────────────

    def _gerar_csv(self, registros, output_path):
        """Grava CSV em latin-1. Retorna lista de avisos sobre caracteres substituídos."""
        avisos = []
        codec = 'latin-1'

        for reg in registros:
            mat = reg.get('MATRÍCULA', '?')
            for col, val in reg.items():
                if not isinstance(val, str):
                    continue
                problemas = [c for c in val if not _pode_latin1(c)]
                if problemas:
                    avisos.append(
                        f"Matrícula {mat} / {col}: "
                        f"char(s) fora do latin-1 substituído(s): {list(set(problemas))}"
                    )

        with open(output_path, 'w', newline='', encoding=codec, errors='replace') as f:
            writer = csv.DictWriter(f, fieldnames=COLUNAS_CSV, delimiter=';',
                                    extrasaction='ignore')
            writer.writeheader()
            writer.writerows(registros)

        return avisos

    # ── Modelos disponíveis ────────────────────────────────────────────

    @staticmethod
    def listar_modelos(api_key):
        from google import genai
        _EXCLUIR = ('tts', 'embedding', 'imagen', 'veo', 'audio', 'lyria',
                    'robotics', 'computer-use', 'deep-research', 'aqa',
                    'clip', 'image', 'live')
        client = genai.Client(api_key=api_key.strip())
        resultado = []
        for m in client.models.list():
            nome = m.name.lower()
            if any(ex in nome for ex in _EXCLUIR):
                continue
            model_id = m.name.split('/')[-1]
            display  = m.display_name or model_id
            resultado.append((display, model_id))
        return resultado

    # ── Verificação IA ─────────────────────────────────────────────────

    def verificar_com_ia(self, registros, nao_encontrados, api_key, model_id='gemini-2.5-flash'):
        try:
            from google import genai
        except ImportError:
            return ['Erro: biblioteca google-genai não instalada. Execute: pip install google-genai']

        if not api_key.strip():
            return ['Erro: API Key não informada.']

        amostra = _mascarar_pii(registros[:50])
        linhas_texto = [
            f"Matrícula={r['MATRÍCULA']} | Nome={r['NOME DO FUNCIONÁRIO']} | "
            f"CPF={r['CPF']} | RG={r['RG']} | AnoNasc={r['DATA DE NASCIMENTO']} | "
            f"CEP={r['CEP']} | ValorUnit={r['VALOR UNITÁRIO']} | "
            f"QtdDiaria={r['QUANTIDADE DIÁRIA']} | PeriodoDias={r['PERÍODO DE DIAS TRABALHADOS']} | "
            f"Beneficio={r['BENEFÍCIO DO FUNCIONÁRIO']} | Cargo={r['CARGO']}"
            for r in amostra
        ]
        sem_corresp = '\n'.join(nao_encontrados) if nao_encontrados else 'Nenhuma'

        prompt = f"""Você é um assistente de RH verificando dados de Vale-Transporte para importação.
CPF e RG foram substituídos por "preenchido"/"vazio" por privacidade.
Analise os registros e reporte APENAS inconsistências reais. Seja objetivo e conciso.

Verifique:
1. Valor Unitário zerado ou vazio
2. Quantidade Diária zerada ou vazia
3. Período de Dias Trabalhados zerado (possível erro no período)
4. CPF, RG ou CEP indicados como "vazio" (campos obrigatórios)
5. Nome com caracteres estranhos ou aparentemente truncado
6. Quantidade Diária numericamente maior que Período de Dias Trabalhados

Registros ({len(amostra)} de {len(registros)} total):
{chr(10).join(linhas_texto)}

Matrículas sem correspondência no cadastro:
{sem_corresp}

Responda em português com lista numerada. Se tudo OK: "Nenhuma inconsistência encontrada."
"""
        try:
            client = genai.Client(api_key=api_key.strip())
            response = client.models.generate_content(model=model_id, contents=prompt)
            return response.text.strip().splitlines()
        except Exception as e:
            return [f'Erro ao chamar IA: {e}']

    # ── Orquestrador ───────────────────────────────────────────────────

    def processar(self, pdf_path, xls_path, output_path,
                  progress_cb=None, usar_ia=False, api_key='', model_id='gemini-2.5-flash'):
        def _prog(pct, msg):
            if progress_cb:
                progress_cb(pct, msg)

        _prog(5, 'Lendo PDF...')
        pdf_rows, avisos_pdf = self._extrair_pdf(pdf_path)
        _prog(35, f'PDF: {len(pdf_rows)} linha(s) encontrada(s).')
        for av in avisos_pdf:
            _prog(35, av)
        if pdf_rows:
            _prog(35, f'1º código PDF: {pdf_rows[0]["codigo"]}  |  último: {pdf_rows[-1]["codigo"]}')

        _prog(40, 'Carregando Excel cadastral...')
        excel_data, avisos_xls = self._carregar_excel(xls_path)
        _prog(60, f'Excel: {len(excel_data)} funcionário(s).')
        for av in avisos_xls:
            _prog(60, av)
        if excel_data:
            _prog(60, f'Primeiros códigos Excel: {list(excel_data.keys())[:3]}')

        _prog(65, 'Cruzando dados...')
        registros, nao_encontrados = self._cruzar_dados(pdf_rows, excel_data)
        _prog(80, f'{len(registros)} correspondência(s) | {len(nao_encontrados)} sem correspondência.')

        _prog(85, 'Gerando CSV...')
        avisos_csv = self._gerar_csv(registros, output_path)
        for av in avisos_csv:
            _prog(87, f'AVISO encoding: {av}')
        _prog(90, f'CSV salvo em {output_path}')

        alertas_ia = []
        if usar_ia and registros:
            _prog(92, f'Verificando com IA ({model_id})...')
            alertas_ia = self.verificar_com_ia(registros, nao_encontrados, api_key, model_id)

        _prog(100, 'Concluído!')

        return {
            'total_pdf':       len(pdf_rows),
            'total_ok':        len(registros),
            'nao_encontrados': nao_encontrados,
            'alertas_ia':      alertas_ia,
            'avisos_csv':      avisos_csv,
        }
