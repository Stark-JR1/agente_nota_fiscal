from .base_extractor import extrair


def extrair_nf_produto(pagina: dict, confianca: float) -> dict:
    return extrair(pagina, "NF_PRODUTO", confianca)
