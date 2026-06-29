from decimal import Decimal

from app.validators.processo_validator import validar_processo


def test_falta_boleto_e_detectada():
    processo = {"documentos": [
        {"tipo_documento": "NF_SERVICO", "valor_total": Decimal("100"), "sistermi_cnpj": "27.535.996/0012-49"},
        {"tipo_documento": "PEDIDO_COMPRA", "valor_total": Decimal("100"), "sistermi_cnpj": "27.535.996/0012-49"},
    ]}
    assert "Boleto nao identificado." in validar_processo(processo)["erros"]
