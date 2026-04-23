import os
import tempfile
import unittest

from openpyxl import Workbook

from vt_caixa_processador import ProcessadorVTCaixa, _extrair_codigo


class TestFonteSemQuantidade(unittest.TestCase):
    def test_extrair_codigo_normaliza_separador_milhar(self):
        self.assertEqual(_extrair_codigo("11.108"), "11108")
        self.assertEqual(_extrair_codigo("11,108"), "11108")
        self.assertEqual(_extrair_codigo("11108.0"), "11108")

    def test_extracao_fonte_nao_expoe_quantidade(self):
        wb = Workbook()
        ws = wb.active
        ws.title = "Fonte"
        ws.append(
            [
                "Setor",
                "Re",
                "Nome",
                "Matricula VT",
                "Cargo",
                "Tipo Beneficio",
                "Administradora(Fornecedor)",
                "Quantidade",
                "Valor Unitário",
            ]
        )
        ws.append(
            [
                "CAIXA ECONOMICA 10 - 84",
                "11.108",
                "ELIZANGELA IAROSSI DO NASCIMENTO",
                "11.108",
                "TELEFONISTA",
                "VALE TRANSPORTE - VT",
                "GUARUPASS",
                20,
                "12,40",
            ]
        )

        fd, path = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        try:
            wb.save(path)

            proc = ProcessadorVTCaixa()
            rows, avisos = proc._extrair_fonte_planilha(path)

            self.assertEqual(len(rows), 1)
            self.assertTrue(any("Aba selecionada para extracao" in a for a in avisos))
            self.assertEqual(rows[0]["codigo"], "11108")
            self.assertEqual(rows[0]["colaborador"], "ELIZANGELA IAROSSI DO NASCIMENTO")
            self.assertEqual(rows[0]["valor_unitario"], "12,40")
            self.assertEqual(rows[0]["administradora"], "GUARUPASS")
            self.assertNotIn("quantidade", rows[0])
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
