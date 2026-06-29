import unittest
from decimal import Decimal

from app.agrupador import agrupar_documentos
from app.extrator_campos import extrair_campos
from app.validador import soma_campo, validar_processo


class RegrasFiscaisTest(unittest.TestCase):
    def test_paginas_ocr_do_mesmo_pdf_incluem_pedido_no_mesmo_processo(self):
        documentos = [
            self.doc("NF_PRODUTO", Decimal("2970.00")),
            self.doc("BOLETO", Decimal("2970.00")),
            self.doc("PEDIDO_COMPRA", Decimal("2970.00"), numero_pedido="16334"),
            self.doc("DACTE", Decimal("12.26")),
        ]

        processos = agrupar_documentos(documentos)

        self.assertEqual(len(processos), 1)
        self.assertEqual({doc["tipo_documento"] for doc in processos[0]["documentos"]}, {
            "NF_PRODUTO", "BOLETO", "PEDIDO_COMPRA", "DACTE",
        })

    def test_cte_nao_e_somado_ao_valor_da_nf_quando_ha_nota(self):
        processo = {
            "documentos": [
                self.doc("NF_PRODUTO", Decimal("2970.00")),
                self.doc("BOLETO", Decimal("2970.00")),
                self.doc("PEDIDO_COMPRA", Decimal("2970.00"), numero_pedido="16334"),
                self.doc("DACTE", Decimal("12.26")),
            ]
        }

        validado = validar_processo(processo, 0.10)

        self.assertEqual(validado["valor_nf"], Decimal("2970.00"))
        self.assertEqual(validado["status"], "APROVADO")

    def test_fecha_varias_notas_do_mesmo_fornecedor_quando_somam_o_boleto(self):
        documentos = [
            self.doc_nomeado("NF_PRODUTO", "HOTEL VERDES MARES - DANFE 5450.pdf", "7.00", numero_nf="5450"),
            self.doc_nomeado("NF_PRODUTO", "HOTEL VERDES MARES - DANFE 5451.pdf", "15.50", numero_nf="5451"),
            self.doc_nomeado("NF_SERVICO", "HOTEL VERDES MARES - NF 22833.pdf", "870.00", numero_nf="22833"),
            self.doc_nomeado("BOLETO", "HOTEL VERDES MARES - FATURA 22833.pdf", "892.50"),
        ]

        processos = agrupar_documentos(documentos)

        self.assertEqual(len(processos), 1)

    def test_processo_misto_compara_total_das_notas_com_pedidos(self):
        processo = {
            "documentos": [
                {**self.doc_nomeado("NF_PRODUTO", "HOTEL VERDES MARES - DANFE 5450.pdf", "22.50", numero_nf="5450"), "valor_produtos": Decimal("22.50")},
                self.doc_nomeado("NF_SERVICO", "HOTEL VERDES MARES - NF 22833.pdf", "870.00", numero_nf="22833"),
                self.doc_nomeado("BOLETO", "HOTEL VERDES MARES - FATURA 22833.pdf", "892.50"),
                {**self.doc_nomeado("PEDIDO_COMPRA", "HOTEL VERDES MARES - PC 16177.pdf", "915.00"), "numero_pedido": "16177"},
            ]
        }

        validado = validar_processo(processo, 0.10)

        self.assertIn("Valor das NFs 892.50 diverge do pedido 915.00.", validado["erros"])

    def test_fornecedor_invalido_e_substituido_pelo_nome_do_arquivo(self):
        pagina = {
            "texto": "NOTA FISCAL DE SERVICO\nNome/Razao Social\nCNPJ 12.345.678/0001-95\nVALOR TOTAL DOS SERVICOS 100,00",
            "arquivo_origem": "TRANSPORTE RIBEIRO - NF 123.pdf",
            "pagina": 1,
            "origem_texto": "digital",
            "confianca_ocr": 1.0,
        }

        campos = extrair_campos(pagina, "NF_SERVICO", 1.0)

        self.assertEqual(campos["fornecedor_nome"], "TRANSPORTE RIBEIRO")

    def test_fornecedor_corrompido_por_ocr_e_substituido_pelo_nome_do_arquivo(self):
        pagina = {
            "texto": "DANFE CHAVE DE ACESSO NATUREZA DA OPERACAO NOTA FISCAL\n"
                     "o or . o : CNP [E ADA EMISSAO\nVALOR TOTAL DA NOTA 100,00",
            "arquivo_origem": "MAKS PECAS - NF + BOLETO + PC.pdf",
            "pagina": 1,
            "origem_texto": "ocr",
            "confianca_ocr": 0.70,
        }

        campos = extrair_campos(pagina, "NF_PRODUTO", 1.0)

        self.assertEqual(campos["fornecedor_nome"], "MAKS PECAS")

    def test_documento_existente_sem_valor_fica_pendente(self):
        processo = {
            "documentos": [
                {**self.doc_nomeado("NF_SERVICO", "FORNECEDOR - NF 123.pdf", "0.00", numero_nf="123"), "valor_total": None},
                self.doc_nomeado("PEDIDO_COMPRA", "FORNECEDOR - PC 456.pdf", "100.00"),
            ]
        }

        validado = validar_processo(processo, 0.10)

        self.assertIn("Valor da nota fiscal nao identificado.", validado["erros"])

    def test_todos_pedidos_referenciados_precisam_estar_anexados(self):
        nf = self.doc_nomeado("NF_PRODUTO", "FORNECEDOR - NF 123.pdf", "100.00", numero_nf="123")
        nf["pedidos_referenciados"] = ["111", "222"]
        pedido = {**self.doc_nomeado("PEDIDO_COMPRA", "FORNECEDOR - PC 111.pdf", "100.00"), "numero_pedido": "111"}

        validado = validar_processo({"documentos": [nf, pedido]}, 0.10)

        self.assertTrue(any("222" in erro and "sem anexo correspondente" in erro for erro in validado["erros"]))

    def test_extrai_todos_pedidos_referenciados_na_nf(self):
        pagina = {
            "texto": (
                "DANFE NOTA FISCAL\nVALOR TOTAL DA NOTA 1.052,00\n"
                "PEDIDO DO CLIENTE 16575\nORDEM DE COMPRA 16515"
            ),
            "arquivo_origem": "POLIFILTRO - NF 91583 - R$ 1052,00 - NF.pdf",
            "pagina": 1,
            "origem_texto": "digital",
            "confianca_ocr": 1.0,
        }

        campos = extrair_campos(pagina, "NF_PRODUTO", 1.0)

        self.assertEqual(campos["pedidos_referenciados"], ["16515", "16575"])

    def test_extrai_valor_de_servico_lancado_no_pedido(self):
        pagina = {
            "texto": (
                "PEDIDO DE COMPRA DETALHADO\nPEDIDO / FILIAL : 16487 / 4\n"
                "398,00\n398,00\n0,00\nREGULADOR VOLTAGEM\n1050\nUN\n1\n"
                "160,00\n160,00\n0,00\nSERVICO DE MANUTENCAO ALTERNADOR\n10567\nSER\n1\n"
                "TOTAL PRD\nR$ 732,00"
            ),
            "arquivo_origem": "RITA - PC 16487.pdf",
            "pagina": 1,
            "origem_texto": "digital",
            "confianca_ocr": 1.0,
        }

        campos = extrair_campos(pagina, "PEDIDO_COMPRA", 1.0)

        self.assertEqual(campos["valor_servicos_pedido"], Decimal("160.00"))
        self.assertEqual(campos["valor_produtos_pedido"], Decimal("572.00"))

    def test_pedido_anexado_diferente_do_referenciado_fica_pendente(self):
        nf = self.doc_nomeado("NF_PRODUTO", "POLIFILTRO - NF 91583.pdf", "1052.00", numero_nf="91583")
        nf["pedidos_referenciados"] = ["16515", "16575"]
        pedidos = [
            {**self.doc_nomeado("PEDIDO_COMPRA", "POLIFILTRO - PC 16515.pdf", "986.00"), "numero_pedido": "16515"},
            {**self.doc_nomeado("PEDIDO_COMPRA", "POLIFILTRO - PC 16651.pdf", "66.00"), "numero_pedido": "16651"},
        ]

        validado = validar_processo({"documentos": [nf, *pedidos]}, 0.10)

        self.assertTrue(any("16575" in erro and "sem anexo correspondente" in erro for erro in validado["erros"]))
        self.assertTrue(any("16651" in erro and "nao referenciado" in erro for erro in validado["erros"]))

    def test_soma_produtos_de_nfs_distintas_com_mesmo_valor(self):
        docs = [
            {**self.doc_nomeado("NF_PRODUTO", "FORNECEDOR - NF 101.pdf", "50.00", numero_nf="101"), "valor_produtos": Decimal("50.00")},
            {**self.doc_nomeado("NF_PRODUTO", "FORNECEDOR - NF 102.pdf", "50.00", numero_nf="102"), "valor_produtos": Decimal("50.00")},
        ]

        self.assertEqual(soma_campo(docs, {"NF_PRODUTO"}, "valor_produtos"), Decimal("100.00"))

    @staticmethod
    def doc(tipo, valor, numero_pedido=None):
        return {
            "tipo_documento": tipo,
            "arquivo_origem": "MAKS PEÇAS - NF + BOLETO + PC + CTE.pdf",
            "arquivo_nome": "MAKS PEÇAS - NF + BOLETO + PC + CTE.pdf",
            "origem_texto": "ocr",
            "fornecedor_cnpj": "79.162.673/0001-06",
            "sistermi_cnpj": "27.535.996/0012-49",
            "fornecedor_nome": "MAKS PECAS",
            "numero_pedido": numero_pedido,
            "valor_total": valor,
            "pedidos_referenciados": [],
        }

    @staticmethod
    def doc_nomeado(tipo, arquivo, valor, numero_nf=None):
        return {
            "tipo_documento": tipo,
            "arquivo_origem": arquivo,
            "arquivo_nome": arquivo,
            "origem_texto": "digital",
            "fornecedor_cnpj": "03.000.972/0001-74",
            "sistermi_cnpj": "27.535.996/0012-49",
            "fornecedor_nome": "OUROTUR ORGANIZACAO LTDA",
            "numero_nf": numero_nf,
            "valor_total": Decimal(valor),
            "pedidos_referenciados": [],
        }


if __name__ == "__main__":
    unittest.main()
