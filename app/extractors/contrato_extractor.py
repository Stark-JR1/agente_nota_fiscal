from .base_extractor import extrair


def extrair_contrato(pagina: dict, confianca: float) -> dict:
    return extrair(pagina, "FATURA_CONTRATO", confianca)
