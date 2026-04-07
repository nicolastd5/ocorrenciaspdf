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

# Mapeamento de nomes de coluna do Excel (normalizado sem acento) → chave interna
_COL_ALIASES = {
    'cod epr':            'cod_epr',
    'cpf':                'CPF',
    'rg':                 'RG',
    'uf rg':              'UF RG',
    'orgao rg':           'Orgão RG',
    'orgão rg':           'Orgão RG',
    'data nascimento':    'Data nascimento',
    'data de nascimento': 'Data nascimento',
    'descricao cargo':    'Descrição cargo',
    'descrição cargo':    'Descrição cargo',
    'cod ccusto':         'Descrição Ccusto',
    'descricao ccusto':   'Descrição Ccusto',
    'descrição ccusto':   'Descrição Ccusto',
    'endereco':           'Endereço',
    'endereço':           'Endereço',
    'numero':             'Numero',
    'número':             'Numero',
    'complemento':        'Complemento',
    'cep':                'Cep',
    'cidade':             'Cidade',
    'uf end':             'UF End',
    'estado civil':       'Estado Civil',
}


def _normalizar(texto):
    """Remove acentos e converte para minúsculas para comparação robusta."""
    return unicodedata.normalize('NFKD', str(texto)).encode('ascii', 'ignore').decode().lower().strip()


def _extrair_codigo(valor):
    """Extrai o código numérico de uma célula, lidando com '123.0', '  123  ', etc.
    Retorna string de dígitos ou '' se não for um código válido.
    """
    if valor is None:
        return ''
    s = str(valor).strip().replace('\n', '').replace('\r', '')
    # Remove sufixo decimal (ex: '123.0' → '123')
    s = re.sub(r'\.0+$', '', s)
    # Extrai apenas dígitos iniciais
    m = re.match(r'^(\d+)', s)
    if m:
        return m.group(1)
    return ''


class ProcessadorVTCaixa:

    def _extrair_pdf(self, pdf_path):
        """Extrai linhas de dados do PDF Nautilus.
        Retorna lista de dicts com: codigo, colaborador, periodo,
        quantidade, valor_unitario, administradora.
        Também retorna lista de avisos de diagnóstico.
        """
        rows = []
        avisos = []

        with pdfplumber.open(pdf_path) as pdf:
            for num_pag, pagina in enumerate(pdf.pages, 1):
                tabela = pagina.extract_table()
                if not tabela:
                    # Tenta extract_tables como fallback
                    tabelas = pagina.extract_tables()
                    if tabelas:
                        tabela = tabelas[0]
                    else:
                        continue

                for idx_linha, linha in enumerate(tabela):
                    if not linha or all(c is None for c in linha):
                        continue

                    codigo = _extrair_codigo(linha[0])
                    if not codigo:
                        continue

                    # Garante que há colunas suficientes
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
            avisos.append('AVISO: Nenhuma linha de dados extraída do PDF. '
                          'Verifique se o PDF é o Relatório Compra Benefícios correto.')

        return rows, avisos

    def _calcular_dias_uteis(self, periodo_str):
        """Conta dias úteis (seg–sex) no período 'dd/mm/yyyy a dd/mm/yyyy'."""
        if not periodo_str:
            return 0
        partes = re.split(r'\s+[aA\-/]\s+', periodo_str.strip())
        if len(partes) != 2:
            # Tenta formato com hífen sem espaço
            partes = re.split(r'[-/]', periodo_str.strip())
            if len(partes) != 2:
                return 0
        try:
            inicio = datetime.strptime(partes[0].strip(), '%d/%m/%Y').date()
            fim    = datetime.strptime(partes[1].strip(), '%d/%m/%Y').date()
        except ValueError:
            return 0
        dias = 0
        atual = inicio
        while atual <= fim:
            if atual.weekday() < 5:
                dias += 1
            atual = date.fromordinal(atual.toordinal() + 1)
        return dias

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

    def _carregar_excel(self, xls_path):
        """Carrega o Excel cadastral .xls.
        Retorna (dict {str(Cód Epr): {...}}, lista de avisos de diagnóstico).
        """
        wb = xlrd.open_workbook(xls_path)
        ws = wb.sheet_by_index(0)
        avisos = []

        # Mapeia nome normalizado → índice de coluna
        cabecalhos_norm = {}   # normalizado → índice
        cabecalhos_orig = {}   # normalizado → nome original
        for col in range(ws.ncols):
            val = ws.cell_value(0, col)
            if val:
                norm = _normalizar(val)
                cabecalhos_norm[norm] = col
                cabecalhos_orig[norm] = str(val).strip()

        avisos.append(f'Colunas encontradas no Excel: {list(cabecalhos_orig.values())}')

        def _idx(nome_interno):
            """Busca índice da coluna pelo alias normalizado."""
            norm_alvo = _normalizar(nome_interno)
            # Busca direta
            if norm_alvo in cabecalhos_norm:
                return cabecalhos_norm[norm_alvo]
            # Busca via aliases
            for alias, chave in _COL_ALIASES.items():
                if chave == nome_interno or _normalizar(chave) == norm_alvo:
                    if _normalizar(alias) in cabecalhos_norm:
                        return cabecalhos_norm[_normalizar(alias)]
            # Busca parcial (substring)
            for norm_col, idx in cabecalhos_norm.items():
                if norm_alvo in norm_col or norm_col in norm_alvo:
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
            cols_disp = list(cabecalhos_orig.values())
            raise ValueError(
                f"Coluna 'Cód Epr' não encontrada no Excel.\n"
                f"Colunas disponíveis: {cols_disp}"
            )

        avisos.append(
            f'Mapeamento de colunas: cod_epr={idx_cod}, cpf={idx_cpf}, '
            f'rg={idx_rg}, nascimento={idx_dt_nasc}, cargo={idx_cargo}'
        )

        dados = {}
        for row in range(1, ws.nrows):
            cod_raw = ws.cell_value(row, idx_cod)
            if cod_raw is None or cod_raw == '':
                continue

            # Normaliza chave: remove decimal, strip
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

    def _limpar_valor_unitario(self, valor_str):
        v = valor_str.replace('R$', '').strip()
        v = v.replace('.', '').replace(',', '.')
        return v

    def _cruzar_dados(self, pdf_rows, excel_data):
        registros = []
        nao_encontrados = []

        for linha in pdf_rows:
            codigo = linha['codigo']
            ex = excel_data.get(codigo)

            if ex is None:
                nao_encontrados.append(f"{codigo} - {linha['colaborador']}")
                continue

            dias_uteis = self._calcular_dias_uteis(linha['periodo'])

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
                'PERÍODO DE DIAS TRABALHADOS': str(dias_uteis),
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

    def _gerar_csv(self, registros, output_path):
        with open(output_path, 'w', newline='', encoding='latin-1', errors='replace') as f:
            writer = csv.DictWriter(f, fieldnames=COLUNAS_CSV, delimiter=';',
                                    extrasaction='ignore')
            writer.writeheader()
            writer.writerows(registros)

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

    def verificar_com_ia(self, registros, nao_encontrados, api_key, model_id='gemini-2.5-flash'):
        try:
            from google import genai
        except ImportError:
            return ['Erro: biblioteca google-genai não instalada. Execute: pip install google-genai']

        if not api_key.strip():
            return ['Erro: API Key não informada.']

        amostra = registros[:50]
        linhas_texto = []
        for r in amostra:
            linhas_texto.append(
                f"Matrícula={r['MATRÍCULA']} | Nome={r['NOME DO FUNCIONÁRIO']} | "
                f"CPF={r['CPF']} | RG={r['RG']} | Nascimento={r['DATA DE NASCIMENTO']} | "
                f"CEP={r['CEP']} | ValorUnit={r['VALOR UNITÁRIO']} | "
                f"QtdDiaria={r['QUANTIDADE DIÁRIA']} | PeriodoDias={r['PERÍODO DE DIAS TRABALHADOS']} | "
                f"Beneficio={r['BENEFÍCIO DO FUNCIONÁRIO']}"
            )
        sem_corresp = '\n'.join(nao_encontrados) if nao_encontrados else 'Nenhuma'

        prompt = f"""Você é um assistente de RH verificando dados de Vale-Transporte para importação.
Analise os registros abaixo e reporte APENAS inconsistências reais. Seja objetivo e conciso.

Verifique:
1. Valor Unitário zerado ou vazio
2. Quantidade Diária zerada ou vazia
3. Período de Dias Trabalhados zerado (possível erro no período)
4. CPF, RG ou CEP vazios (campos obrigatórios)
5. Nome com caracteres estranhos ou truncado
6. Quantidade Diária maior que Período de Dias Trabalhados

Registros ({len(amostra)} de {len(registros)} total):
{chr(10).join(linhas_texto)}

Matrículas sem correspondência no cadastro:
{sem_corresp}

Responda em português com lista numerada de problemas encontrados. Se tudo estiver OK, diga apenas "Nenhuma inconsistência encontrada."
"""
        try:
            client = genai.Client(api_key=api_key.strip())
            response = client.models.generate_content(model=model_id, contents=prompt)
            return response.text.strip().splitlines()
        except Exception as e:
            return [f'Erro ao chamar IA: {e}']

    def processar(self, pdf_path, xls_path, output_path,
                  progress_cb=None, usar_ia=False, api_key='', model_id='gemini-2.5-flash'):
        def _prog(pct, msg):
            if progress_cb:
                progress_cb(pct, msg)

        _prog(5, 'Lendo PDF...')
        pdf_rows, avisos_pdf = self._extrair_pdf(pdf_path)
        _prog(35, f'PDF lido: {len(pdf_rows)} linha(s) de dados encontrada(s).')

        for av in avisos_pdf:
            _prog(35, av)

        if pdf_rows:
            # Diagnóstico: mostra primeiro e último código extraído
            _prog(35, f'Primeiro código PDF: {pdf_rows[0]["codigo"]} '
                      f'— Último: {pdf_rows[-1]["codigo"]}')

        _prog(40, 'Carregando Excel cadastral...')
        excel_data, avisos_xls = self._carregar_excel(xls_path)
        _prog(60, f'Excel carregado: {len(excel_data)} funcionário(s).')

        for av in avisos_xls:
            _prog(60, av)

        if excel_data:
            primeiros = list(excel_data.keys())[:3]
            _prog(60, f'Primeiros códigos Excel: {primeiros}')

        _prog(65, 'Cruzando dados...')
        registros, nao_encontrados = self._cruzar_dados(pdf_rows, excel_data)
        _prog(80, f'Cruzamento concluído: {len(registros)} correspondência(s), '
                  f'{len(nao_encontrados)} sem correspondência.')

        _prog(85, 'Gerando CSV...')
        self._gerar_csv(registros, output_path)
        _prog(90, 'CSV salvo.')

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
        }
