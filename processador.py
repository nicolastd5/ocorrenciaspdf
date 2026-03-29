"""
Módulo de processamento de ocorrências.
Extrai dados do PDF e atualiza a planilha Excel.
"""

import pdfplumber
from openpyxl import load_workbook
import shutil
import os


class ProcessadorOcorrencias:
    """Processador principal de ocorrências PDF → Excel."""

    TODOS_CODIGOS = ['FA', 'AT', 'SD', 'LC', 'AA', 'AP', 'LM', 'FE']
    SEM_QUANTIDADE = ['AP', 'LM', 'FE']
    ORDEM = ['FA', 'AT', 'SD', 'LC', 'AA', 'AP', 'LM', 'FE']
    CODIGOS_DEDUZIR = ['FA', 'AT', 'SD', 'LC']
    COLUNAS_QT = ['qt va', 'qt vr', 'qt vt']
    DESCRICOES = {
        'FA': 'Faltas',
        'AT': 'Atestado',
        'SD': 'Suspensão Disciplinar',
        'LC': 'Licença Casamento',
        'AA': 'Ausência Autorizada',
        'AP': 'Afastamento Previdenciário',
        'LM': 'Afastamento Maternidade',
        'FE': 'Férias',
    }

    def extrair_ocorrencias(self, pdf_path, codigos_alvo):
        """
        Extrai ocorrências do PDF de jornada de trabalho.

        Args:
            pdf_path: Caminho do arquivo PDF.
            codigos_alvo: Set de códigos a procurar.

        Returns:
            dict: {codigo_re: {'nome': str, 'ocorrencias': {codigo: contagem}}}
        """
        resultados = {}
        codigos_set = set(codigos_alvo)

        with pdfplumber.open(pdf_path) as pdf:
            for pagina in pdf.pages:
                tabelas = pagina.extract_tables()
                if not tabelas:
                    continue

                for tabela in tabelas:
                    for linha in tabela:
                        if not linha or not linha[0] or not linha[1]:
                            continue

                        nome = linha[0].strip() if linha[0] else ''
                        codigo = linha[1].strip() if linha[1] else ''

                        if codigo == 'Código' or not codigo.isdigit():
                            continue

                        ocorrencias = {}
                        for celula in linha[6:34]:
                            if celula and celula.strip() in codigos_set:
                                cod = celula.strip()
                                ocorrencias[cod] = ocorrencias.get(cod, 0) + 1

                        if ocorrencias:
                            if codigo not in resultados:
                                resultados[codigo] = {'nome': nome, 'ocorrencias': {}}
                            for k, v in ocorrencias.items():
                                resultados[codigo]['ocorrencias'][k] = \
                                    resultados[codigo]['ocorrencias'].get(k, 0) + v

        return resultados

    def montar_motivo(self, ocorrencias, codigos_selecionados):
        """
        Monta a string de motivo a partir das ocorrências.

        Regras:
        - Ordem: FA, AT, SD, LC, AA, AP, LM
        - Quantidade na frente quando > 1 (ex: 2 AT, 3 FA)
        - AP e LM nunca recebem quantidade
        - Múltiplos códigos separados por vírgula
        """
        partes = []
        codigos_set = set(codigos_selecionados)

        for codigo in self.ORDEM:
            if codigo in ocorrencias and codigo in codigos_set:
                contagem = ocorrencias[codigo]
                if codigo in self.SEM_QUANTIDADE:
                    partes.append(codigo)
                else:
                    if contagem > 1:
                        partes.append(f"{contagem} {codigo}")
                    else:
                        partes.append(codigo)

        return ', '.join(partes)

    def processar(self, pdf_path, xlsx_path, output_path, codigos, progress_cb=None, dias_mes=None):
        """
        Processa os arquivos e retorna um dicionário com os resultados.

        Args:
            pdf_path: Caminho do PDF de faltas.
            xlsx_path: Caminho da planilha Excel de pedido.
            output_path: Caminho para salvar a planilha atualizada.
            codigos: Lista de códigos a incluir.
            progress_cb: Callable(pct: int, msg: str) para atualizar progresso.

        Returns:
            dict: {
                'total_pdf': int,
                'matched': int,
                'atualizados': [{'re': str, 'nome': str, 'motivo': str}],
                'nao_encontrados': [{'re': str, 'nome': str, 'motivo': str}]
            }
        """
        def _prog(pct, msg):
            if progress_cb:
                progress_cb(pct, msg)

        # 1. Extrair ocorrências do PDF
        _prog(5, "Lendo PDF...")
        resultados_pdf = self.extrair_ocorrencias(pdf_path, codigos)
        _prog(50, "PDF lido. Abrindo planilha...")

        # 2. Copiar e abrir planilha
        shutil.copy(xlsx_path, output_path)
        wb = load_workbook(output_path)
        ws = wb.active
        _prog(60, "Planilha aberta. Cruzando dados...")

        # 3. Encontrar colunas RE, MOTIVO e Qt VA/VR/VT
        re_col = None
        motivo_col = None
        qt_cols = {}  # {'qt va': col_num, ...}
        for col in range(1, ws.max_column + 1):
            val = ws.cell(row=1, column=col).value
            if val:
                val_lower = str(val).lower().strip()
                if motivo_col is None and val_lower == 'motivo':
                    motivo_col = col
                if re_col is None and val_lower == 'folha re':
                    re_col = col
                if val_lower in self.COLUNAS_QT:
                    qt_cols[val_lower] = col

        if not re_col or not motivo_col:
            raise ValueError(
                f"Colunas não encontradas na planilha. "
                f"RE col: {re_col}, MOTIVO col: {motivo_col}. "
                f"Verifique se a planilha tem colunas de matrícula/RE e MOTIVO."
            )

        # 4. Cruzar dados
        excel_res = set()
        matched = 0
        atualizados = []

        total_rows = ws.max_row - 1
        for i, row in enumerate(range(2, ws.max_row + 1)):
            re_val = ws.cell(row=row, column=re_col).value
            if re_val is not None:
                re_str = str(int(re_val)) if isinstance(re_val, (float, int)) else str(re_val).strip()
                excel_res.add(re_str)

                if dias_mes is not None and qt_cols:
                    for qt_col in qt_cols.values():
                        ws.cell(row=row, column=qt_col).value = dias_mes

                if re_str in resultados_pdf:
                    ocorr = resultados_pdf[re_str]['ocorrencias']
                    motivo = self.montar_motivo(ocorr, codigos)
                    if motivo:
                        ws.cell(row=row, column=motivo_col).value = motivo
                        matched += 1
                        atualizados.append({
                            're': re_str,
                            'nome': resultados_pdf[re_str]['nome'],
                            'motivo': motivo
                        })

                    if dias_mes is not None and qt_cols:
                        dias_ded = sum(ocorr.get(c, 0) for c in self.CODIGOS_DEDUZIR)
                        if dias_ded > 0:
                            for qt_col in qt_cols.values():
                                ws.cell(row=row, column=qt_col).value = max(0, dias_mes - dias_ded)
            if total_rows > 0:
                pct = 60 + int((i / total_rows) * 30)
                _prog(pct, f"Cruzando dados... ({i}/{total_rows})")

        # 5. Encontrar não correspondidos
        _prog(90, "Finalizando...")
        nao_encontrados = []
        for codigo, dados in resultados_pdf.items():
            motivo = self.montar_motivo(dados['ocorrencias'], codigos)
            if motivo and codigo not in excel_res:
                nao_encontrados.append({
                    're': codigo,
                    'nome': dados['nome'],
                    'motivo': motivo
                })

        nao_encontrados.sort(key=lambda x: x['nome'])

        # 6. Salvar
        _prog(97, "Salvando planilha...")
        wb.save(output_path)
        _prog(100, "Concluído!")

        return {
            'total_pdf': len(resultados_pdf),
            'matched': matched,
            'atualizados': atualizados,
            'nao_encontrados': nao_encontrados,
        }
