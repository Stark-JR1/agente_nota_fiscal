from .base_extractor import extrair


def extrair_recibo(pagina: dict, confianca: float) -> dict:
    return extrair(pagina, "RECIBO_LOCACAO", confianca)
