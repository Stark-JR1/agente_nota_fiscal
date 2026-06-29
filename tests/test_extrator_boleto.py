from decimal import Decimal

from app.extractors.boleto_extractor import extrair_boleto


def test_extrator_boleto_le_valor_documento():
    pagina = {
        "texto": "FICHA DE COMPENSACAO BENEFICIARIO TESTE VALOR DO DOCUMENTO 123,45",
        "arquivo_origem": "FORNECEDOR - BOLETO.pdf",
        "pagina": 1,
        "origem_texto": "digital",
        "confianca_ocr": 1.0,
    }
    assert extrair_boleto(pagina, 1.0)["valor_total"] == Decimal("123.45")
