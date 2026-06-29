from app.classificador import classificar_texto


def test_classifica_pedido_detalhado():
    tipo, _ = classificar_texto("PEDIDO DE COMPRA DETALHADO PEDIDO / FILIAL FORNECEDOR CNPJ/CPF TOTAL PRD")
    assert tipo == "PEDIDO_COMPRA"


def test_classifica_danfe_confiavel():
    tipo, confianca = classificar_texto("DANFE CHAVE DE ACESSO NATUREZA DA OPERACAO NOTA FISCAL")
    assert tipo == "NF_PRODUTO"
    assert confianca == 1.0
