from decimal import Decimal

from app.grouping.grouping_service import agrupar_processos


def test_agrupa_nf_boleto_e_pedido_por_cnpj_e_valor():
    base = {"fornecedor_cnpj": "12.345.678/0001-95", "fornecedor_nome": "FORNECEDOR", "origem_texto": "digital"}
    docs = [
        {**base, "tipo_documento": "NF_PRODUTO", "numero_nf": "123", "valor_total": Decimal("100.00"), "arquivo_origem": "F - NF 123.pdf"},
        {**base, "tipo_documento": "BOLETO", "valor_total": Decimal("100.00"), "arquivo_origem": "F - BOLETO.pdf"},
        {**base, "tipo_documento": "PEDIDO_COMPRA", "numero_pedido": "456", "valor_total": Decimal("100.00"), "arquivo_origem": "F - PC.pdf"},
    ]
    assert len(agrupar_processos(docs)) == 1


def test_nao_agrupa_fornecedores_com_cnpjs_conflitantes_por_nome_e_valor():
    docs = [
        {
            "tipo_documento": "NF_PRODUTO",
            "fornecedor_nome": "MAC FREIOS",
            "fornecedor_cnpj": "12.345.678/0001-95",
            "valor_total": Decimal("100.00"),
            "arquivo_origem": "MAC FREIOS - NF 10.pdf",
            "origem_texto": "digital",
        },
        {
            "tipo_documento": "BOLETO",
            "fornecedor_nome": "MAC SERVICOS",
            "fornecedor_cnpj": "98.765.432/0001-10",
            "valor_total": Decimal("100.00"),
            "arquivo_origem": "MAC SERVICOS - NF 20.pdf",
            "origem_texto": "digital",
        },
    ]
    assert len(agrupar_processos(docs)) == 2


def test_agrupa_referencia_exata_do_nome_mesmo_com_cnpj_extraido_divergente():
    docs = [
        {
            "tipo_documento": "NF_PRODUTO",
            "fornecedor_nome": "GAMA CENTER",
            "fornecedor_cnpj": "12.345.678/0001-95",
            "valor_total": Decimal("100.00"),
            "arquivo_origem": "GAMA CENTER - NF 100 - NF.pdf",
            "origem_texto": "digital",
        },
        {
            "tipo_documento": "PEDIDO_COMPRA",
            "fornecedor_nome": "GAMA CENTER MEDICINA OCUPACIONAL",
            "fornecedor_cnpj": "98.765.432/0001-10",
            "valor_total": Decimal("100.00"),
            "arquivo_origem": "GAMA CENTER - NF 100 - PC 10.pdf",
            "origem_texto": "digital",
        },
    ]
    assert len(agrupar_processos(docs)) == 1


def test_paginas_do_mesmo_pdf_formam_um_grupo_sem_unir_outro_fornecedor():
    docs = [
        {
            "tipo_documento": "NF_PRODUTO",
            "fornecedor_nome": "RITA",
            "fornecedor_cnpj": "38.625.208/0001-79",
            "valor_total": Decimal("572.00"),
            "arquivo_origem": "RITA - NF 8205.pdf",
            "grupo_arquivo": "RITA - NF 8205.pdf",
            "origem_texto": "ocr",
        },
        {
            "tipo_documento": "OUTRO_ANEXO",
            "fornecedor_nome": "RITA",
            "fornecedor_cnpj": "38.625.208/0001-79",
            "arquivo_origem": "RITA - NF 8205.pdf",
            "grupo_arquivo": "RITA - NF 8205.pdf",
            "origem_texto": "ocr",
        },
        {
            "tipo_documento": "NF_PRODUTO",
            "fornecedor_nome": "MAC FREIOS",
            "fornecedor_cnpj": "66.204.074/0001-58",
            "valor_total": Decimal("572.00"),
            "arquivo_origem": "MAC FREIOS - NF 84400.pdf",
            "origem_texto": "digital",
        },
    ]
    assert len(agrupar_processos(docs)) == 2
