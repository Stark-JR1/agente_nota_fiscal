from .base_extractor import extrair


def extrair_pedido(pagina: dict, confianca: float) -> dict:
    return extrair(pagina, "PEDIDO_COMPRA", confianca)
