from ..extrator_campos import extrair_campos


def extrair(pagina: dict, tipo: str, confianca: float) -> dict:
    return extrair_campos(pagina, tipo, confianca)
