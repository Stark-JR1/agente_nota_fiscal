from .base_extractor import extrair


def extrair_nf_servico(pagina: dict, confianca: float) -> dict:
    return extrair(pagina, "NF_SERVICO", confianca)
