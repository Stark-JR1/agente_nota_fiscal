from ..validador import TIPOS_NOTA, validar_processo as validar_processo_fiscal


def validar_processo(processo: dict, tolerancia: float = 0.05) -> dict:
    validado = validar_processo_fiscal(processo, tolerancia)
    aplicar_score_auditoria(validado)
    return validado


def aplicar_score_auditoria(processo: dict) -> dict:
    processo.update(calcular_score_auditoria(processo))
    return processo


def calcular_score_auditoria(processo: dict) -> dict:
    docs = processo.get("documentos", [])
    tipos = {doc.get("tipo_documento") for doc in docs}
    criterios: list[str] = []
    score = 0

    score += pontuar(bool(tipos & TIPOS_NOTA), 15, "NF encontrada", "NF nao encontrada", criterios)
    score += pontuar("PEDIDO_COMPRA" in tipos, 15, "Pedido encontrado", "Pedido nao encontrado", criterios)
    score += pontuar("BOLETO" in tipos, 15, "Boleto encontrado", "Boleto nao encontrado", criterios)

    score += pontuar(campo_presente(docs, "fornecedor_nome"), 10, "Fornecedor identificado", "Fornecedor nao identificado", criterios)
    score += pontuar(campo_presente(docs, "fornecedor_cnpj"), 10, "CNPJ fornecedor identificado", "CNPJ fornecedor nao identificado", criterios)
    score += pontuar(processo.get("valor_nf") is not None or valor_por_tipo(docs, TIPOS_NOTA), 10, "Valor NF identificado", "Valor NF nao identificado", criterios)
    score += pontuar(
        processo.get("valor_pedidos") is not None
        or processo.get("valor_boletos") is not None
        or valor_por_tipo(docs, {"PEDIDO_COMPRA", "BOLETO"}),
        10,
        "Valor Pedido ou Boleto identificado",
        "Valor Pedido ou Boleto nao identificado",
        criterios,
    )

    divergencia_cnpj = contem_problema(processo, "CNPJ")
    divergencia_valor = contem_problema(processo, "VALOR")
    baixa_confianca = ocr_baixa_confianca(docs) or contem_problema(processo, "OCR")
    erro_arquivo = processo.get("status") == "PENDENTE_ERRO_ARQUIVO" or contem_problema(processo, "ARQUIVO")

    score += pontuar(not divergencia_cnpj, 5, "Sem divergencia de CNPJ", "Divergencia de CNPJ detectada", criterios)
    score += pontuar(not divergencia_valor, 5, "Sem divergencia de valor", "Divergencia de valor detectada", criterios)
    score += pontuar(not baixa_confianca, 5, "OCR confiavel ou documento digital", "OCR baixa confianca", criterios)

    if divergencia_cnpj:
        score -= 20
    if divergencia_valor:
        score -= 20
    if baixa_confianca:
        score -= 10
    if "DESCONHECIDO" in tipos:
        score -= 5
        criterios.append("Documento desconhecido relevante")
    if erro_arquivo:
        score -= 30
        criterios.append("Erro de arquivo detectado")

    score = max(0, min(100, score))
    if erro_arquivo:
        score = min(score, 69)

    return {
        "score_auditoria": score,
        "risco_auditoria": classificar_risco_auditoria(score),
        "criterios_score": criterios,
    }


def classificar_risco_auditoria(score: int) -> str:
    if score >= 90:
        return "BAIXO_RISCO"
    if score >= 70:
        return "MEDIO_RISCO"
    return "ALTO_RISCO"


def pontuar(condicao: bool, pontos: int, sucesso: str, falha: str, criterios: list[str]) -> int:
    criterios.append(sucesso if condicao else falha)
    return pontos if condicao else 0


def campo_presente(docs: list[dict], campo: str) -> bool:
    return any(doc.get(campo) not in (None, "") for doc in docs)


def valor_por_tipo(docs: list[dict], tipos: set[str]) -> bool:
    return any(doc.get("tipo_documento") in tipos and doc.get("valor_total") is not None for doc in docs)


def contem_problema(processo: dict, palavra: str) -> bool:
    palavra = palavra.upper()
    textos = [str(processo.get("status") or "")]
    textos.extend(str(erro) for erro in processo.get("erros", []))
    return palavra in " ".join(textos).upper()


def ocr_baixa_confianca(docs: list[dict]) -> bool:
    for doc in docs:
        if doc.get("origem_texto") in {"vazio", "erro"}:
            return True
        for campo in ("confianca_extracao", "confianca_documento"):
            valor = doc.get(campo)
            if valor is None:
                continue
            try:
                if float(valor) < 0.5:
                    return True
            except (TypeError, ValueError):
                continue
    return False


__all__ = ["validar_processo", "calcular_score_auditoria", "aplicar_score_auditoria", "classificar_risco_auditoria"]
