from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from .utils import normalizar_texto, somente_digitos


def chave_documento(doc: dict) -> str:
    if doc.get("grupo_arquivo"):
        return f"ARQUIVO:{doc['grupo_arquivo']}"
    cnpj = somente_digitos(doc.get("fornecedor_cnpj"))
    if doc.get("contrato_sem_pedido"):
        if doc.get("contrato_sem_pedido") in {"NET_VALE_NF_BOLETO", "SISTERMI_NF_PROPRIA", "MARIA_INES_ALUGUEL", "MARIA_INES_ENERGIA"}:
            if doc.get("numero_nf"):
                return f"{doc.get('contrato_sem_pedido')}:NF:{doc['numero_nf']}"
            if doc.get("valor_total"):
                return f"{doc.get('contrato_sem_pedido')}:VALOR:{Decimal(doc['valor_total']).quantize(Decimal('0.01'))}"
        return f"CONTRATO:{doc.get('contrato_sem_pedido')}"
    if doc.get("tipo_documento") in {"NF_PRODUTO", "NF_SERVICO", "RECIBO_LOCACAO", "BOLETO", "PEDIDO_COMPRA", "DACTE", "OUTRO_ANEXO"} and doc.get("arquivo_origem") and doc.get("origem_texto") in {"ocr", "vazio"}:
        return f"ARQUIVO_OCR:{doc.get('arquivo_origem')}"
    if doc.get("tipo_documento") == "DESCONHECIDO" and not cnpj and not doc.get("valor_total"):
        return f"DESCONHECIDO:{doc.get('arquivo_origem')}"
    if doc.get("numero_nf"):
        return f"NF:{doc['numero_nf']}"
    if doc.get("numero_pedido") and cnpj:
        return f"PEDIDO:{doc['numero_pedido']}:{cnpj}"
    if doc.get("valor_total") and cnpj:
        return f"VALOR:{Decimal(doc['valor_total']).quantize(Decimal('0.01'))}:{cnpj}"
    nome = normalizar_texto(doc.get("fornecedor_nome") or "SEM_FORNECEDOR")
    return f"NOME:{nome[:40]}"


def agrupar_documentos(documentos: list[dict]) -> list[dict]:
    grupos: dict[str, list[dict]] = defaultdict(list)
    for doc in documentos:
        grupos[chave_documento(doc)].append(doc)

    processos = []
    for index, (chave, docs) in enumerate(grupos.items(), start=1):
        processos.append(
            {
                "id": f"PROCESSO_{index:03d}",
                "chave": chave,
                "documentos": docs,
            }
        )

    return consolidar_por_similaridade(processos)


def consolidar_por_similaridade(processos: list[dict]) -> list[dict]:
    try:
        from rapidfuzz import fuzz
    except ImportError:
        return processos

    consolidados: list[dict] = []
    for processo in processos:
        nome = nome_principal(processo)
        valor = valor_principal(processo)
        soma = soma_valores_processo(processo)
        unido = False
        for existente in consolidados:
            if contratos_incompativeis(processo, existente):
                continue
            nome_existente = nome_principal(existente)
            valor_existente = valor_principal(existente)
            soma_existente = soma_valores_processo(existente)
            score_nome = fuzz.token_set_ratio(nome or "", nome_existente or "")
            mesmo_valor = valor is not None and valor_existente is not None and valor == valor_existente
            mesmo_numero_nf = bool(numeros_nf(processo) & numeros_nf(existente))
            mesmo_cnpj = bool(cnpjs_fornecedor(processo) & cnpjs_fornecedor(existente))
            mesma_raiz_cnpj = bool(raizes_cnpj(processo) & raizes_cnpj(existente))
            mesma_nf_no_nome = bool(numeros_nf_arquivo(processo) & numeros_nf_arquivo(existente))
            mesmo_prefixo_arquivo = bool(prefixos_arquivo(processo) & prefixos_arquivo(existente))
            referencia_arquivo_exata = mesma_nf_no_nome and mesmo_prefixo_arquivo and mesmo_valor
            if cnpjs_conflitantes(processo, existente) and not referencia_arquivo_exata:
                continue
            itens_compativeis = len(itens_chave(processo) & itens_chave(existente)) >= 2 and valores_itens_proximos(processo, existente)
            mesmo_contrato_compativel = contratos_compativeis(processo, existente)
            mesmo_cnpj_valor = mesmo_cnpj and mesmo_valor
            mesmo_cnpj_prefixo_sem_nf_arquivo = (
                mesmo_cnpj
                and prefixos_arquivo(processo) & prefixos_arquivo(existente)
                and not numeros_nf_arquivo(processo)
                and not numeros_nf_arquivo(existente)
            )
            cnpj_com_soma_compativel = mesmo_cnpj and valores_compativeis({valor, soma}, {valor_existente, soma_existente})
            nome_com_soma_compativel = score_nome >= 75 and valores_compativeis({valor, soma}, {valor_existente, soma_existente})
            boleto_sem_cnpj_compativel = boleto_sem_cnpj_completa_processo(processo, existente) or boleto_sem_cnpj_completa_processo(existente, processo)
            fechamento_por_soma = fechamento_mesmo_fornecedor_por_soma(processo, existente)
            if (
                mesmo_numero_nf
                or referencia_arquivo_exata
                or (mesma_nf_no_nome and mesma_raiz_cnpj)
                or (itens_compativeis and mesma_raiz_cnpj)
                or mesmo_contrato_compativel
                or mesmo_cnpj_valor
                or mesmo_cnpj_prefixo_sem_nf_arquivo
                or cnpj_com_soma_compativel
                or nome_com_soma_compativel
                or boleto_sem_cnpj_compativel
                or fechamento_por_soma
            ):
                existente["documentos"].extend(processo["documentos"])
                existente["chave"] += f"|{processo['chave']}"
                unido = True
                break
        if not unido:
            consolidados.append(processo)

    consolidados_por_pedido = consolidar_pedidos_por_soma(consolidados)
    if len(consolidados_por_pedido) != len(processos):
        return consolidar_por_similaridade(reindexar(consolidados_por_pedido))

    for index, processo in enumerate(consolidados_por_pedido, start=1):
        processo["id"] = f"PROCESSO_{index:03d}"
    return consolidados_por_pedido


def reindexar(processos: list[dict]) -> list[dict]:
    for index, processo in enumerate(processos, start=1):
        processo["id"] = f"PROCESSO_{index:03d}"
    return processos


def nome_principal(processo: dict) -> str | None:
    for doc in processo.get("documentos", []):
        if doc.get("fornecedor_nome"):
            return normalizar_texto(doc["fornecedor_nome"])
    return None


def valor_principal(processo: dict) -> Decimal | None:
    for doc in processo.get("documentos", []):
        if doc.get("valor_total") is not None:
            return Decimal(doc["valor_total"]).quantize(Decimal("0.01"))
    return None


def soma_valores_processo(processo: dict) -> Decimal | None:
    valores = []
    vistos = set()
    for doc in processo.get("documentos", []):
        if doc.get("valor_total") is None:
            continue
        chave = (
            doc.get("tipo_documento"),
            doc.get("numero_pedido"),
            doc.get("numero_nf"),
            Decimal(doc["valor_total"]).quantize(Decimal("0.01")),
        )
        if chave in vistos:
            continue
        vistos.add(chave)
        valores.append(Decimal(doc["valor_total"]).quantize(Decimal("0.01")))
    return sum(valores) if valores else None


def valores_compativeis(esquerda: set[Decimal | None], direita: set[Decimal | None]) -> bool:
    valores_esquerda = {v for v in esquerda if v is not None}
    valores_direita = {v for v in direita if v is not None}
    return bool(valores_esquerda & valores_direita)


def fechamento_mesmo_fornecedor_por_soma(processo: dict, existente: dict) -> bool:
    if not (cnpjs_fornecedor(processo) & cnpjs_fornecedor(existente)):
        return False
    if not (prefixos_arquivo(processo) & prefixos_arquivo(existente)):
        return False
    documentos = processo.get("documentos", []) + existente.get("documentos", [])
    total_fiscal = soma_documentos_por_tipo(documentos, {"NF_PRODUTO", "NF_SERVICO", "RECIBO_LOCACAO"})
    total_boletos = soma_documentos_por_tipo(documentos, {"BOLETO"})
    return total_fiscal is not None and total_boletos is not None and total_fiscal == total_boletos


def soma_documentos_por_tipo(documentos: list[dict], tipos: set[str]) -> Decimal | None:
    valores = [
        Decimal(doc["valor_total"]).quantize(Decimal("0.01"))
        for doc in documentos
        if doc.get("tipo_documento") in tipos and doc.get("valor_total") is not None
    ]
    return sum(valores) if valores else None


def numeros_nf(processo: dict) -> set[str]:
    return {str(doc.get("numero_nf")) for doc in processo.get("documentos", []) if doc.get("numero_nf")}


def cnpjs_fornecedor(processo: dict) -> set[str]:
    return {somente_digitos(doc.get("fornecedor_cnpj")) for doc in processo.get("documentos", []) if somente_digitos(doc.get("fornecedor_cnpj"))}


def raizes_cnpj(processo: dict) -> set[str]:
    return {cnpj[:8] for cnpj in cnpjs_fornecedor(processo) if len(cnpj) == 14}


def cnpjs_conflitantes(processo: dict, existente: dict) -> bool:
    raizes_a = raizes_cnpj(processo)
    raizes_b = raizes_cnpj(existente)
    return bool(raizes_a and raizes_b and raizes_a.isdisjoint(raizes_b))


def itens_chave(processo: dict) -> set[str]:
    return {
        str(item)
        for doc in processo.get("documentos", [])
        for item in doc.get("itens_chave", [])
        if item
    }


def valores_itens_proximos(processo: dict, existente: dict) -> bool:
    valores_a = valores_referencia_itens(processo)
    valores_b = valores_referencia_itens(existente)
    return any(abs(a - b) <= Decimal("1.00") for a in valores_a for b in valores_b)


def valores_referencia_itens(processo: dict) -> set[Decimal]:
    valores = set()
    for doc in processo.get("documentos", []):
        valor = doc.get("valor_produtos")
        if valor is None and doc.get("tipo_documento") == "PEDIDO_COMPRA":
            valor = doc.get("valor_total")
        if valor is not None:
            valores.add(Decimal(valor).quantize(Decimal("0.01")))
    return valores


def prefixos_arquivo(processo: dict) -> set[str]:
    prefixos = set()
    for doc in processo.get("documentos", []):
        nome = nome_arquivo_doc(doc)
        if not nome:
            continue
        prefixo = nome.split(" - ", 1)[0]
        prefixo_norm = normalizar_texto(prefixo)
        if len(prefixo_norm) >= 4:
            prefixos.add(prefixo_norm)
    return prefixos


def numeros_nf_arquivo(processo: dict) -> set[str]:
    import re
    numeros = set()
    for doc in processo.get("documentos", []):
        nome = normalizar_texto(nome_arquivo_doc(doc))
        for match in re.finditer(r"\bNF\s*[-_ ]?(\d{2,12})\b", nome):
            numeros.add(match.group(1).lstrip("0") or "0")
    return numeros


def nome_arquivo_doc(doc: dict) -> str:
    nome = str(doc.get("arquivo_nome") or doc.get("arquivo_origem") or "")
    return nome.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]


def consolidar_pedidos_por_soma(processos: list[dict]) -> list[dict]:
    alterou = False
    usados: set[int] = set()
    resultado: list[dict] = []

    pedidos_por_cnpj: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    for idx, processo in enumerate(processos):
        if tipos_processo(processo) == {"PEDIDO_COMPRA"}:
            for cnpj in cnpjs_fornecedor(processo):
                pedidos_por_cnpj[cnpj].append((idx, processo))

    for idx, processo in enumerate(processos):
        if idx in usados:
            continue
        tipos = tipos_processo(processo)
        if not (tipos & {"NF_PRODUTO", "NF_SERVICO", "RECIBO_LOCACAO", "DACTE", "BOLETO"}):
            resultado.append(processo)
            continue
        if "PEDIDO_COMPRA" in tipos:
            resultado.append(processo)
            continue

        alvo = valor_principal(processo) or soma_valores_processo(processo)
        cnpjs = cnpjs_fornecedor(processo)
        candidatos = [
            (pedido_idx, pedido)
            for cnpj in cnpjs
            for pedido_idx, pedido in pedidos_por_cnpj.get(cnpj, [])
            if pedido_idx not in usados and pedido_idx != idx
        ]
        encontrados = escolher_pedidos_por_soma(candidatos, alvo)
        if encontrados:
            for pedido_idx, pedido in encontrados:
                processo["documentos"].extend(pedido["documentos"])
                processo["chave"] += f"|{pedido['chave']}"
                usados.add(pedido_idx)
            alterou = True
        resultado.append(processo)

    if not alterou:
        return processos
    return resultado


def escolher_pedidos_por_soma(candidatos: list[tuple[int, dict]], alvo: Decimal | None) -> list[tuple[int, dict]]:
    if alvo is None:
        return []
    alvo = Decimal(alvo).quantize(Decimal("0.01"))
    itens = [
        (idx, processo, soma_valores_processo(processo))
        for idx, processo in candidatos
        if soma_valores_processo(processo) is not None
    ]
    itens = [(idx, processo, valor.quantize(Decimal("0.01"))) for idx, processo, valor in itens]

    def backtrack(pos: int, soma: Decimal, escolhidos: list[tuple[int, dict]]) -> list[tuple[int, dict]]:
        if soma == alvo:
            return escolhidos
        if soma > alvo or pos >= len(itens):
            return []
        idx, processo, valor = itens[pos]
        com_atual = backtrack(pos + 1, soma + valor, escolhidos + [(idx, processo)])
        if com_atual:
            return com_atual
        return backtrack(pos + 1, soma, escolhidos)

    return backtrack(0, Decimal("0.00"), [])


def tipos_processo(processo: dict) -> set[str]:
    return {doc.get("tipo_documento") for doc in processo.get("documentos", []) if doc.get("tipo_documento")}


def contrato_processo(processo: dict) -> str | None:
    contratos = {doc.get("contrato_sem_pedido") for doc in processo.get("documentos", []) if doc.get("contrato_sem_pedido")}
    return next(iter(contratos)) if contratos else None


def contratos_incompativeis(processo: dict, existente: dict) -> bool:
    contrato_a = contrato_processo(processo)
    contrato_b = contrato_processo(existente)
    if contrato_a and contrato_b:
        if contrato_a == contrato_b and contrato_a in {"NET_VALE_NF_BOLETO", "SISTERMI_NF_PROPRIA"}:
            return not (
                bool(numeros_nf(processo) & numeros_nf(existente))
                or valores_compativeis(
                    {valor_principal(processo), soma_valores_processo(processo)},
                    {valor_principal(existente), soma_valores_processo(existente)},
                )
            )
        return contrato_a != contrato_b
    if contrato_a or contrato_b:
        return True
    return False


def contratos_compativeis(processo: dict, existente: dict) -> bool:
    contrato_a = contrato_processo(processo)
    contrato_b = contrato_processo(existente)
    if not contrato_a or contrato_a != contrato_b:
        return False
    return bool(numeros_nf(processo) & numeros_nf(existente)) or valores_compativeis(
        {valor_principal(processo), soma_valores_processo(processo)},
        {valor_principal(existente), soma_valores_processo(existente)},
    )


def boleto_sem_cnpj_completa_processo(boleto: dict, processo: dict) -> bool:
    docs_boleto = boleto.get("documentos", [])
    if not docs_boleto or any(doc.get("tipo_documento") != "BOLETO" for doc in docs_boleto):
        return False
    if cnpjs_fornecedor(boleto):
        return False
    tipos_processo = {doc.get("tipo_documento") for doc in processo.get("documentos", [])}
    if not ({"NF_PRODUTO", "NF_SERVICO", "RECIBO_LOCACAO", "DACTE"} & tipos_processo or "PEDIDO_COMPRA" in tipos_processo):
        return False
    return valores_compativeis({valor_principal(boleto), soma_valores_processo(boleto)}, {valor_principal(processo), soma_valores_processo(processo)})
