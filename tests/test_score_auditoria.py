from decimal import Decimal

from app.validators.processo_validator import calcular_score_auditoria, validar_processo


SISTERMI_CNPJ = "27.535.996/0012-49"
FORNECEDOR_CNPJ = "12.345.678/0001-95"


def documentos_completos():
    return [
        {
            "tipo_documento": "NF_PRODUTO",
            "fornecedor_nome": "FORNECEDOR TESTE",
            "fornecedor_cnpj": FORNECEDOR_CNPJ,
            "sistermi_cnpj": SISTERMI_CNPJ,
            "numero_nf": "123",
            "valor_total": Decimal("100.00"),
            "origem_texto": "digital",
            "confianca_extracao": 1.0,
        },
        {
            "tipo_documento": "PEDIDO_COMPRA",
            "fornecedor_nome": "FORNECEDOR TESTE",
            "fornecedor_cnpj": FORNECEDOR_CNPJ,
            "sistermi_cnpj": SISTERMI_CNPJ,
            "numero_pedido": "456",
            "valor_total": Decimal("100.00"),
            "origem_texto": "digital",
            "confianca_extracao": 1.0,
        },
        {
            "tipo_documento": "BOLETO",
            "fornecedor_nome": "FORNECEDOR TESTE",
            "fornecedor_cnpj": FORNECEDOR_CNPJ,
            "valor_total": Decimal("100.00"),
            "origem_texto": "digital",
            "confianca_extracao": 1.0,
        },
    ]


def processo_base(**campos):
    processo = {
        "id": "PROCESSO_TESTE",
        "status": "APROVADO",
        "erros": [],
        "valor_nf": Decimal("100.00"),
        "valor_pedidos": Decimal("100.00"),
        "valor_boletos": Decimal("100.00"),
        "documentos": documentos_completos(),
    }
    processo.update(campos)
    return processo


def test_processo_completo_aprovado_gera_score_alto_e_preserva_status():
    processo = validar_processo({"id": "PROCESSO_TESTE", "documentos": documentos_completos()})

    assert processo["status"] == "APROVADO"
    assert processo["score_auditoria"] == 100
    assert processo["risco_auditoria"] == "BAIXO_RISCO"
    assert "NF encontrada" in processo["criterios_score"]


def test_processo_sem_pedido_reduz_score():
    processo = processo_base(
        status="PENDENTE_PEDIDO",
        valor_pedidos=None,
        documentos=[doc for doc in documentos_completos() if doc["tipo_documento"] != "PEDIDO_COMPRA"],
    )

    resultado = calcular_score_auditoria(processo)

    assert resultado["score_auditoria"] < 100
    assert resultado["risco_auditoria"] == "MEDIO_RISCO"
    assert "Pedido nao encontrado" in resultado["criterios_score"]


def test_processo_com_divergencia_de_valor_reduz_score():
    resultado = calcular_score_auditoria(
        processo_base(
            status="PENDENTE_VALOR",
            erros=["Valor NF 100.00 diverge da soma dos boletos 80.00."],
            valor_boletos=Decimal("80.00"),
        )
    )

    assert resultado["score_auditoria"] == 75
    assert resultado["risco_auditoria"] == "MEDIO_RISCO"
    assert "Divergencia de valor detectada" in resultado["criterios_score"]


def test_processo_com_erro_de_arquivo_gera_alto_risco():
    resultado = calcular_score_auditoria(
        processo_base(status="PENDENTE_ERRO_ARQUIVO", erros=["Arquivo nao encontrado: NF.pdf"])
    )

    assert resultado["score_auditoria"] == 69
    assert resultado["risco_auditoria"] == "ALTO_RISCO"
    assert "Erro de arquivo detectado" in resultado["criterios_score"]


def test_score_nunca_passa_de_100():
    resultado = calcular_score_auditoria(processo_base())

    assert resultado["score_auditoria"] <= 100


def test_score_nunca_fica_abaixo_de_0():
    resultado = calcular_score_auditoria(
        {
            "status": "PENDENTE_ERRO_ARQUIVO",
            "erros": [
                "Divergencia de CNPJ.",
                "Divergencia de valor.",
                "OCR com baixa confianca.",
                "Arquivo nao encontrado.",
            ],
            "documentos": [
                {
                    "tipo_documento": "DESCONHECIDO",
                    "origem_texto": "erro",
                    "confianca_extracao": 0.0,
                }
            ],
        }
    )

    assert resultado["score_auditoria"] >= 0
