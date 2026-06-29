from .base_extractor import extrair


def extrair_dacte(pagina: dict, confianca: float) -> dict:
    return extrair(pagina, "DACTE", confianca)
