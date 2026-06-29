from decimal import Decimal

from app.validador import validar_processo


def doc(tipo, valor="100.00", cnpj="12.345.678/0001-95", **extras):
    return {
        "tipo_documento": tipo,
        "arquivo_origem": f"{tipo}.pdf",
        "arquivo_nome": f"{tipo}.pdf",
        "fornecedor_nome": "FORNECEDOR",
        "fornecedor_cnpj": cnpj,
        "sistermi_cnpj": "27.535.996/0012-49",
        "valor_total": Decimal(valor),
        "pedidos_referenciados": [],
        **extras,
    }


def test_nf_pedido_boleto_aprova():
    processo = {"documentos": [
        doc("NF_PRODUTO", numero_nf="1"),
        doc("PEDIDO_COMPRA", numero_pedido="10"),
        doc("BOLETO"),
    ]}
    assert validar_processo(processo, 0.10)["status"] == "APROVADO"


def test_falta_boleto_fica_pendente():
    processo = {"documentos": [doc("NF_PRODUTO", numero_nf="1"), doc("PEDIDO_COMPRA", numero_pedido="10")]}
    validado = validar_processo(processo, 0.10)
    assert validado["status"] != "APROVADO"
    assert any("boleto" in erro.lower() for erro in validado["erros"])


def test_falta_pedido_fica_pendente():
    processo = {"documentos": [doc("NF_PRODUTO", numero_nf="1"), doc("BOLETO")]}
    validado = validar_processo(processo, 0.10)
    assert validado["status"] != "APROVADO"
    assert any("pedido" in erro.lower() for erro in validado["erros"])


def test_falta_nf_fica_pendente():
    processo = {"documentos": [doc("PEDIDO_COMPRA", numero_pedido="10"), doc("BOLETO")]}
    validado = validar_processo(processo, 0.10)
    assert validado["status"] != "APROVADO"
    assert any("fiscal" in erro.lower() or "nf" in erro.lower() for erro in validado["erros"])


def test_nf_com_varios_pedidos_aprova_quando_todos_estao_anexados():
    nf = doc("NF_PRODUTO", "200.00", numero_nf="1", pedidos_referenciados=["10", "20"])
    processo = {"documentos": [
        nf,
        doc("PEDIDO_COMPRA", "100.00", numero_pedido="10"),
        doc("PEDIDO_COMPRA", "100.00", numero_pedido="20"),
        doc("BOLETO", "200.00"),
    ]}
    assert validar_processo(processo, 0.10)["status"] == "APROVADO"


def test_nf_com_varios_pedidos_nao_aprova_apenas_por_ser_faturamento_parcial():
    processo = {"documentos": [
        doc("NF_PRODUTO", "1052.00", numero_nf="91583"),
        doc("PEDIDO_COMPRA", "1226.00", numero_pedido="16515", arquivo_origem="PC_16515.pdf"),
        doc("PEDIDO_COMPRA", "66.00", numero_pedido="16651", arquivo_origem="PC_16651.pdf"),
        doc("BOLETO", "1052.00"),
    ]}
    assert validar_processo(processo, 0.10)["status"] == "PENDENTE_VALOR"


def test_nf_com_varios_pedidos_nao_aprova_quando_nf_supera_soma():
    processo = {"documentos": [
        doc("NF_PRODUTO", "300.00", numero_nf="1"),
        doc("PEDIDO_COMPRA", "100.00", numero_pedido="10", arquivo_origem="PC_10.pdf"),
        doc("PEDIDO_COMPRA", "100.00", numero_pedido="20", arquivo_origem="PC_20.pdf"),
        doc("BOLETO", "300.00"),
    ]}
    assert validar_processo(processo, 0.10)["status"] == "PENDENTE_VALOR"


def test_nf_com_boleto_parcelado_aprova_pela_soma():
    processo = {"documentos": [
        doc("NF_PRODUTO", "200.00", numero_nf="1"),
        doc("PEDIDO_COMPRA", "200.00", numero_pedido="10"),
        doc("BOLETO", "100.00", vencimento="10/07/2026", arquivo_origem="BOLETO_PARCELA_1.pdf", arquivo_nome="BOLETO_PARCELA_1.pdf"),
        doc("BOLETO", "100.00", vencimento="10/08/2026", arquivo_origem="BOLETO_PARCELA_2.pdf", arquivo_nome="BOLETO_PARCELA_2.pdf"),
    ]}
    assert validar_processo(processo, 0.10)["status"] == "APROVADO"


def test_pedido_com_varias_nfs_aprova_pela_soma():
    processo = {"documentos": [
        doc("NF_PRODUTO", "100.00", numero_nf="1"),
        doc("NF_PRODUTO", "100.00", numero_nf="2"),
        doc("PEDIDO_COMPRA", "200.00", numero_pedido="10"),
        doc("BOLETO", "200.00"),
    ]}
    assert validar_processo(processo, 0.10)["status"] == "APROVADO"


def test_pedido_misto_confere_nf_produto_e_nf_servico():
    processo = {"documentos": [
        doc("NF_PRODUTO", "572.00", numero_nf="1", valor_produtos=Decimal("572.00")),
        doc("NF_SERVICO", "160.00", numero_nf="2", valor_servico=Decimal("160.00")),
        doc(
            "PEDIDO_COMPRA",
            "732.00",
            numero_pedido="10",
            valor_produtos_pedido=Decimal("572.00"),
            valor_servicos_pedido=Decimal("160.00"),
        ),
        doc("BOLETO", "732.00"),
    ]}
    assert validar_processo(processo, 0.10)["status"] == "APROVADO"


def test_paginas_do_mesmo_pedido_usam_o_total_mais_completo():
    processo = {"documentos": [
        doc("NF_PRODUTO", "967.69", numero_nf="1"),
        doc("PEDIDO_COMPRA", "345.00", numero_pedido="10", arquivo_origem="PEDIDO_10.pdf"),
        doc("PEDIDO_COMPRA", "967.69", numero_pedido="10", arquivo_origem="PEDIDO_10.pdf"),
        doc("BOLETO", "967.69"),
    ]}
    assert validar_processo(processo, 0.10)["status"] == "APROVADO"


def test_nf_aprova_quando_total_geral_bate_e_valor_produtos_ocr_esta_incorreto():
    processo = {"documentos": [
        doc("NF_PRODUTO", "967.69", numero_nf="1", valor_produtos=Decimal("1075.21")),
        doc("PEDIDO_COMPRA", "967.69", numero_pedido="10"),
        doc("BOLETO", "967.69"),
    ]}
    assert validar_processo(processo, 0.10)["status"] == "APROVADO"


def test_divergencia_de_valor_fica_pendente():
    processo = {"documentos": [
        doc("NF_PRODUTO", "100.00", numero_nf="1"),
        doc("PEDIDO_COMPRA", "110.00", numero_pedido="10"),
        doc("BOLETO", "100.00"),
    ]}
    validado = validar_processo(processo, 0.10)
    assert validado["status"] != "APROVADO"
    assert any("diverge" in erro.lower() for erro in validado["erros"])


def test_divergencia_de_cnpj_fica_pendente():
    processo = {"documentos": [
        doc("NF_PRODUTO", cnpj="12.345.678/0001-95", numero_nf="1"),
        doc("PEDIDO_COMPRA", cnpj="98.765.432/0001-10", numero_pedido="10"),
        doc("BOLETO", cnpj="12.345.678/0001-95"),
    ]}
    validado = validar_processo(processo, 0.10)
    assert validado["status"] != "APROVADO"
    assert any("cnpj" in erro.lower() for erro in validado["erros"])
