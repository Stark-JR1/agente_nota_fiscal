from __future__ import annotations


def calcular_confianca_documento(documento: dict) -> int:
    criterios = [
        _normalizar(documento.get("confianca_ocr")),
        _normalizar(documento.get("confianca_extracao")),
        1.0 if documento.get("fornecedor_nome") else 0.0,
        1.0 if documento.get("fornecedor_cnpj") else 0.0,
        1.0 if documento.get("valor_total") is not None else 0.0,
        1.0 if documento.get("numero_pedido") or documento.get("numero_nf") else 0.0,
    ]
    score = round(sum(criterios) / len(criterios) * 100)
    documento["confianca_documento"] = score
    return score


def calcular_confianca_processo(processo: dict) -> int:
    documentos = processo.get("documentos", [])
    scores = [calcular_confianca_documento(documento) for documento in documentos]
    base = round(sum(scores) / len(scores)) if scores else 0
    penalidade = min(35, len(processo.get("erros", [])) * 7)
    score = max(0, base - penalidade)
    processo["confianca_processo"] = score
    return score


def aplicar_scores(processos: list[dict]) -> list[dict]:
    for processo in processos:
        calcular_confianca_processo(processo)
    return processos


def _normalizar(valor) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, numero / 100 if numero > 1 else numero))
