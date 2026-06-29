from ..agrupador import agrupar_documentos
from ..validador import validar_processo
from .processamento_service import processar_aprovado, processar_pendente


def agrupar_processos(documentos: list[dict]) -> list[dict]:
    return agrupar_documentos(documentos)


def validar_processos(processos: list[dict], tolerancia: float) -> list[dict]:
    return [validar_processo(processo, tolerancia) for processo in processos]


def gerar_saida_aprovada(processo: dict, pastas) -> None:
    processar_aprovado(processo, pastas)


def gerar_saida_pendente(processo: dict, pastas) -> None:
    processar_pendente(processo, pastas)
