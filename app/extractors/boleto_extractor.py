from .base_extractor import extrair


def extrair_boleto(pagina: dict, confianca: float) -> dict:
    return extrair(pagina, "BOLETO", confianca)
