from __future__ import annotations

from decimal import Decimal

from .utils import somente_digitos


SISTERMI_CNPJ = "27535996001249"
TIPOS_NOTA = {"NF_PRODUTO", "NF_SERVICO", "DACTE", "RECIBO_LOCACAO"}
CONTRATOS_SEM_NF = {"MARIA_INES_ALUGUEL", "MARIA_INES_ENERGIA"}


def validar_processo(processo: dict, tolerancia: float = 0.05) -> dict:
    docs = processo["documentos"]
    tipos = {doc.get("tipo_documento") for doc in docs}
    erros = []
    contrato = contrato_sem_pedido(processo)

    if contrato not in CONTRATOS_SEM_NF and any(tipo in tipos for tipo in TIPOS_NOTA) is False:
        erros.append(("PENDENTE_NF", "Nota fiscal nao identificada."))
    if not contrato and "DACTE" not in tipos and "PEDIDO_COMPRA" not in tipos:
        erros.append(("PENDENTE_PEDIDO", "Pedido de compra nao identificado."))
    if not contrato and "BOLETO" not in tipos:
        erros.append(("PENDENTE_BOLETO", "Boleto nao identificado."))
    if contrato == "INTERNET_SUPER":
        validar_contrato_internet_super(docs, tipos, erros)
    if contrato == "VIGILANCIA_SEGURANCA":
        validar_contrato_vigilancia(docs, tipos, erros)
    if contrato == "LIEBHERR_NF_PEDIDO":
        validar_liebherr_nf_pedido(docs, tipos, erros)
    if contrato == "NET_VALE_NF_BOLETO":
        validar_nf_boleto_sem_pedido("Net Vale", tipos, erros)
    if contrato == "SISTERMI_NF_PROPRIA":
        validar_nf_propria_sistermi(tipos, erros)
    if contrato in {"MARIA_INES_ALUGUEL", "MARIA_INES_ENERGIA"}:
        validar_maria_ines(contrato, tipos, erros)
    if "DESCONHECIDO" in tipos:
        erros.append(("PENDENTE_CLASSIFICACAO", "Ha documento sem classificacao confiavel."))
    if any(doc.get("origem_texto") == "vazio" and doc.get("tipo_documento") != "OUTRO_ANEXO" for doc in docs):
        erros.append(("PENDENTE_OCR", "Ha pagina sem texto digital e sem OCR aproveitavel."))
    validar_valores_obrigatorios(docs, tipos, contrato, erros)

    cnpjs_fornecedor = {
        somente_digitos(doc.get("fornecedor_cnpj"))
        for doc in docs
        if somente_digitos(doc.get("fornecedor_cnpj")) and somente_digitos(doc.get("fornecedor_cnpj")) != SISTERMI_CNPJ
    }
    if len({cnpj[:8] for cnpj in cnpjs_fornecedor if len(cnpj) == 14}) > 1:
        erros.append(("PENDENTE_CNPJ", "CNPJ do fornecedor diverge entre documentos."))

    validar_cnpjs_por_papel(docs, erros)
    validar_pedidos_referenciados(docs, erros)

    sistermi_ok = any(somente_digitos(doc.get("sistermi_cnpj")) == SISTERMI_CNPJ for doc in docs)
    if contrato in {"VIGILANCIA_SEGURANCA", "NET_VALE_NF_BOLETO", "SISTERMI_NF_PROPRIA"}:
        sistermi_ok = sistermi_ok or any("27.535.996/" in (doc.get("texto_extraido") or "") for doc in docs)
    if contrato in {"NET_VALE_NF_BOLETO", "SISTERMI_NF_PROPRIA"}:
        sistermi_ok = True
    if any(tipo in tipos for tipo in {"NF_PRODUTO", "NF_SERVICO", "DACTE", "PEDIDO_COMPRA"}) and not sistermi_ok:
        erros.append(("PENDENTE_CNPJ", "CNPJ da Sistermi nao localizado nos documentos principais."))

    pedidos_cnpj_incorreto = [
        doc.get("arquivo_nome") or doc.get("arquivo_origem")
        for doc in docs
        if doc.get("tipo_documento") == "PEDIDO_COMPRA"
        and somente_digitos(doc.get("sistermi_cnpj")) != SISTERMI_CNPJ
    ]
    if pedidos_cnpj_incorreto:
        erros.append(
            (
                "PENDENTE_CNPJ",
                "Pedido de compra nao pertence ao CNPJ da filial 27.535.996/0012-49: "
                + ", ".join(str(nome) for nome in pedidos_cnpj_incorreto),
            )
        )

    tipos_nf_valor = tipos_nota_para_soma(tipos)
    valor_nf = soma_valores(docs, tipos_nf_valor)
    valor_produtos_nf = soma_campo(docs, tipos_nf_valor, "valor_produtos")
    valor_servicos_nf = soma_campo(docs, {"NF_SERVICO"}, "valor_servico")
    valor_pedidos = soma_valores(docs, {"PEDIDO_COMPRA"})
    valor_produtos_pedidos = soma_campo(docs, {"PEDIDO_COMPRA"}, "valor_produtos_pedido")
    valor_servicos_pedidos = soma_campo(docs, {"PEDIDO_COMPRA"}, "valor_servicos_pedido")
    valor_boletos = soma_valores(docs, {"BOLETO"})

    if valor_nf is not None and not contrato:
        tol = Decimal(str(tolerancia))
        tem_nota_nao_produto = bool(tipos & (TIPOS_NOTA - {"NF_PRODUTO", "DACTE"}))
        referencia_pedido = valor_produtos_nf if valor_produtos_nf is not None and not tem_nota_nao_produto else valor_nf
        referencias_validas = {referencia_pedido, valor_nf}
        if (
            valor_pedidos is not None
            and all(abs(referencia - valor_pedidos) > tol for referencia in referencias_validas)
        ):
            rotulo_referencia = "Valor das NFs" if tem_nota_nao_produto and valor_produtos_nf is not None else "Valor dos produtos da NF"
            erros.append(("PENDENTE_VALOR", f"{rotulo_referencia} {referencia_pedido} diverge do pedido {valor_pedidos}."))
        if valor_boletos is not None and abs(valor_nf - valor_boletos) > tol:
            erros.append(("PENDENTE_VALOR", f"Valor NF {valor_nf} diverge da soma dos boletos {valor_boletos}."))
        if {"NF_PRODUTO", "NF_SERVICO"} <= tipos:
            validar_composicao_pedido_misto(
                valor_produtos_nf,
                valor_servicos_nf,
                valor_produtos_pedidos,
                valor_servicos_pedidos,
                tol,
                erros,
            )
    if valor_nf is not None and contrato == "VIGILANCIA_SEGURANCA":
        tol = Decimal(str(tolerancia))
        if valor_boletos is not None and abs(valor_nf - valor_boletos) > tol:
            erros.append(("PENDENTE_VALOR", f"Valor NF {valor_nf} diverge da soma dos boletos {valor_boletos}."))
    if valor_nf is not None and contrato == "LIEBHERR_NF_PEDIDO":
        tol = Decimal(str(tolerancia))
        if valor_pedidos is not None and abs(valor_nf - valor_pedidos) > tol:
            erros.append(("PENDENTE_VALOR", f"Valor NF {valor_nf} diverge do pedido {valor_pedidos}."))
    if valor_nf is not None and contrato == "NET_VALE_NF_BOLETO":
        tol = Decimal(str(tolerancia))
        if valor_boletos is not None and abs(valor_nf - valor_boletos) > tol:
            erros.append(("PENDENTE_VALOR", f"Valor NF {valor_nf} diverge da soma dos boletos {valor_boletos}."))

    status = "APROVADO" if not erros else erros[0][0]
    processo.update(
        {
            "status": status,
            "erros": [erro for _, erro in erros],
            "valor_nf": valor_nf,
            "valor_produtos_nf": valor_produtos_nf,
            "valor_servicos_nf": valor_servicos_nf,
            "valor_pedidos": valor_pedidos,
            "valor_produtos_pedidos": valor_produtos_pedidos,
            "valor_servicos_pedidos": valor_servicos_pedidos,
            "valor_boletos": valor_boletos,
            "contrato_sem_pedido": contrato,
        }
    )
    return processo


def contrato_sem_pedido(processo: dict) -> str | None:
    for doc in processo.get("documentos", []):
        if doc.get("contrato_sem_pedido"):
            return doc["contrato_sem_pedido"]
    return None


def tipos_nota_para_soma(tipos: set[str]) -> set[str]:
    notas_sem_cte = TIPOS_NOTA - {"DACTE"}
    return notas_sem_cte if tipos & notas_sem_cte else {"DACTE"}


def validar_valores_obrigatorios(docs: list[dict], tipos: set[str], contrato: str | None, erros: list[tuple[str, str]]) -> None:
    papeis = [
        ("da nota fiscal", tipos_nota_para_soma(tipos)),
        ("do boleto", {"BOLETO"}),
        ("do pedido de compra", {"PEDIDO_COMPRA"}),
    ]
    for complemento, tipos_papel in papeis:
        documentos = [doc for doc in docs if doc.get("tipo_documento") in tipos_papel]
        if not documentos:
            continue
        if contrato and complemento == "do pedido de compra":
            continue
        if not any(doc.get("valor_total") is not None and Decimal(doc["valor_total"]) > 0 for doc in documentos):
            erros.append(("PENDENTE_VALOR", f"Valor {complemento} nao identificado."))


def validar_cnpjs_por_papel(docs: list[dict], erros: list[tuple[str, str]]) -> None:
    cnpjs_nf = cnpjs_por_tipo(docs, TIPOS_NOTA)
    cnpjs_pedido = cnpjs_por_tipo(docs, {"PEDIDO_COMPRA"})
    cnpjs_boleto = cnpjs_por_tipo(docs, {"BOLETO"})
    cnpjs_sistermi = {
        somente_digitos(doc.get("sistermi_cnpj"))
        for doc in docs
        if somente_digitos(doc.get("sistermi_cnpj"))
    }

    if len(cnpjs_nf) > 1:
        erros.append(("PENDENTE_CNPJ", "CNPJ do fornecedor diverge entre documentos fiscais do processo."))
    if len(cnpjs_pedido) > 1:
        erros.append(("PENDENTE_CNPJ", "CNPJ do fornecedor diverge entre pedidos de compra do processo."))
    if len(cnpjs_boleto) > 1:
        erros.append(("PENDENTE_CNPJ", "CNPJ do beneficiario diverge entre boletos do processo."))

    comparar_cnpjs_papel("NF/recibo", cnpjs_nf, "pedido de compra", cnpjs_pedido, erros)
    comparar_cnpjs_papel("NF/recibo", cnpjs_nf, "boleto", cnpjs_boleto, erros)
    comparar_cnpjs_papel("pedido de compra", cnpjs_pedido, "boleto", cnpjs_boleto, erros)

    cnpjs_sistermi_invalidos = sorted(cnpj for cnpj in cnpjs_sistermi if cnpj != SISTERMI_CNPJ)
    if cnpjs_sistermi_invalidos:
        erros.append((
            "PENDENTE_CNPJ",
            "Documento principal possui CNPJ da Sistermi diferente da filial esperada 27.535.996/0012-49: "
            + ", ".join(formatar_cnpj(cnpj) for cnpj in cnpjs_sistermi_invalidos),
        ))


def validar_pedidos_referenciados(docs: list[dict], erros: list[tuple[str, str]]) -> None:
    pedidos_anexados = numeros_pedidos_anexados(docs)
    pedidos_referenciados = {
        str(numero)
        for doc in docs
        if doc.get("tipo_documento") in TIPOS_NOTA
        for numero in doc.get("pedidos_referenciados", [])
        if numero
    }
    pedidos_ausentes = pedidos_referenciados - pedidos_anexados
    pedidos_nao_referenciados = pedidos_anexados - pedidos_referenciados if pedidos_referenciados else set()
    if pedidos_anexados and pedidos_ausentes:
        erros.append((
            "PENDENTE_PEDIDO",
            "Pedido(s) referenciado(s) na NF sem anexo correspondente: "
            + ", ".join(sorted(pedidos_ausentes))
            + ". Pedido(s) anexado(s): "
            + ", ".join(sorted(pedidos_anexados))
            + ".",
        ))
    if pedidos_nao_referenciados:
        erros.append((
            "PENDENTE_PEDIDO",
            "Pedido(s) anexado(s) nao referenciado(s) na NF: "
            + ", ".join(sorted(pedidos_nao_referenciados))
            + ". Pedido(s) referenciado(s): "
            + ", ".join(sorted(pedidos_referenciados))
            + ".",
        ))


def numeros_pedidos_anexados(docs: list[dict]) -> set[str]:
    return {
        str(doc.get("numero_pedido"))
        for doc in docs
        if doc.get("tipo_documento") == "PEDIDO_COMPRA" and doc.get("numero_pedido")
    }


def validar_composicao_pedido_misto(
    valor_produtos_nf: Decimal | None,
    valor_servicos_nf: Decimal | None,
    valor_produtos_pedidos: Decimal | None,
    valor_servicos_pedidos: Decimal | None,
    tolerancia: Decimal,
    erros: list[tuple[str, str]],
) -> None:
    if valor_servicos_nf is not None and valor_servicos_pedidos is None:
        erros.append(("PENDENTE_VALOR", "NF de servico localizada, mas nenhum item de servico foi identificado no pedido de compra."))
    elif (
        valor_servicos_nf is not None
        and valor_servicos_pedidos is not None
        and abs(valor_servicos_nf - valor_servicos_pedidos) > tolerancia
    ):
        erros.append(("PENDENTE_VALOR", f"Valor dos servicos da NF {valor_servicos_nf} diverge dos servicos do pedido {valor_servicos_pedidos}."))
    if (
        valor_produtos_nf is not None
        and valor_produtos_pedidos is not None
        and abs(valor_produtos_nf - valor_produtos_pedidos) > tolerancia
    ):
        erros.append(("PENDENTE_VALOR", f"Valor dos produtos da NF {valor_produtos_nf} diverge dos produtos do pedido {valor_produtos_pedidos}."))


def cnpjs_por_tipo(docs: list[dict], tipos: set[str]) -> set[str]:
    return {
        somente_digitos(doc.get("fornecedor_cnpj"))
        for doc in docs
        if doc.get("tipo_documento") in tipos
        and somente_digitos(doc.get("fornecedor_cnpj"))
        and somente_digitos(doc.get("fornecedor_cnpj")) != SISTERMI_CNPJ
    }


def comparar_cnpjs_papel(rotulo_a: str, cnpjs_a: set[str], rotulo_b: str, cnpjs_b: set[str], erros: list[tuple[str, str]]) -> None:
    if not cnpjs_a or not cnpjs_b:
        return
    if cnpjs_a == cnpjs_b or {cnpj[:8] for cnpj in cnpjs_a} & {cnpj[:8] for cnpj in cnpjs_b}:
        return
    erros.append((
        "PENDENTE_CNPJ",
        f"CNPJ do fornecedor no {rotulo_a} ({formatar_lista_cnpjs(cnpjs_a)}) diverge do {rotulo_b} ({formatar_lista_cnpjs(cnpjs_b)}).",
    ))


def formatar_lista_cnpjs(cnpjs: set[str]) -> str:
    return ", ".join(formatar_cnpj(cnpj) for cnpj in sorted(cnpjs))


def formatar_cnpj(cnpj: str) -> str:
    digitos = somente_digitos(cnpj)
    if len(digitos) != 14:
        return cnpj
    return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"


def validar_contrato_internet_super(docs: list[dict], tipos: set[str], erros: list[tuple[str, str]]) -> None:
    arquivos = {doc.get("arquivo_origem") for doc in docs if doc.get("arquivo_origem")}
    tem_fatura = "FATURA_CONTRATO" in tipos or "BOLETO" in tipos
    if len(arquivos) < 7:
        erros.append(("PENDENTE_MANUAL", f"Contrato Internet Super incompleto: encontrados {len(arquivos)} de 7 documentos esperados."))
    if not tem_fatura:
        erros.append(("PENDENTE_BOLETO", "Contrato Internet Super sem fatura/resumo de cobranca."))


def validar_contrato_vigilancia(docs: list[dict], tipos: set[str], erros: list[tuple[str, str]]) -> None:
    if not ({"NF_PRODUTO", "NF_SERVICO", "RECIBO_LOCACAO"} & tipos):
        erros.append(("PENDENTE_NF", "Contrato Vigilancia sem nota fiscal."))
    if "BOLETO" not in tipos:
        erros.append(("PENDENTE_BOLETO", "Contrato Vigilancia sem boleto."))


def validar_liebherr_nf_pedido(docs: list[dict], tipos: set[str], erros: list[tuple[str, str]]) -> None:
    if not ({"NF_PRODUTO", "NF_SERVICO", "RECIBO_LOCACAO"} & tipos):
        erros.append(("PENDENTE_NF", "Liebherr sem nota fiscal."))
    if "PEDIDO_COMPRA" not in tipos:
        erros.append(("PENDENTE_PEDIDO", "Liebherr sem pedido de compra."))


def validar_nf_boleto_sem_pedido(nome: str, tipos: set[str], erros: list[tuple[str, str]]) -> None:
    if not (TIPOS_NOTA & tipos):
        erros.append(("PENDENTE_NF", f"{nome} sem nota fiscal."))
    if "BOLETO" not in tipos:
        erros.append(("PENDENTE_BOLETO", f"{nome} sem boleto."))


def validar_nf_propria_sistermi(tipos: set[str], erros: list[tuple[str, str]]) -> None:
    if not ({"NF_PRODUTO", "NF_SERVICO", "RECIBO_LOCACAO"} & tipos):
        erros.append(("PENDENTE_NF", "NF propria da Sistermi nao identificada."))


def validar_maria_ines(contrato: str, tipos: set[str], erros: list[tuple[str, str]]) -> None:
    if "BOLETO" not in tipos:
        erros.append(("PENDENTE_BOLETO", "Maria Ines sem boleto."))
    if "RECIBO_CONTRATO" not in tipos:
        descricao = "aluguel" if contrato == "MARIA_INES_ALUGUEL" else "energia"
        erros.append(("PENDENTE_RECIBO", f"Maria Ines sem recibo de {descricao}."))


def soma_valores(docs: list[dict], tipos: set[str]) -> Decimal | None:
    valores_por_documento: dict[tuple, Decimal] = {}
    for doc in docs:
        if doc.get("tipo_documento") not in tipos or doc.get("valor_total") is None:
            continue
        valor = Decimal(doc["valor_total"]).quantize(Decimal("0.01"))
        chave = chave_documento_valor(doc, valor)
        valores_por_documento[chave] = max(valor, valores_por_documento.get(chave, valor))
    if not valores_por_documento:
        return None
    return sum(valores_por_documento.values())


def chave_documento_valor(doc: dict, valor: Decimal) -> tuple:
    tipo = doc.get("tipo_documento")
    arquivo = doc.get("caminho_original") or doc.get("arquivo_origem") or doc.get("arquivo_nome")
    if not arquivo:
        return (tipo, doc.get("numero_pedido"), doc.get("numero_nf"), doc.get("vencimento"), valor)
    if tipo == "PEDIDO_COMPRA":
        referencia = doc.get("numero_pedido") or "SEM_PEDIDO"
    elif tipo in {"NF_PRODUTO", "NF_SERVICO", "RECIBO_LOCACAO", "DACTE"}:
        referencia = doc.get("numero_nf") or "SEM_NF"
    elif tipo == "BOLETO":
        referencia = doc.get("vencimento") or "SEM_VENCIMENTO"
    else:
        referencia = doc.get("numero_pedido") or doc.get("numero_nf") or "SEM_REFERENCIA"
    return (str(arquivo), tipo, referencia)


def soma_campo(docs: list[dict], tipos: set[str], campo: str) -> Decimal | None:
    valores = []
    vistos = set()
    for doc in docs:
        if doc.get("tipo_documento") not in tipos or doc.get(campo) is None:
            continue
        valor = Decimal(doc[campo]).quantize(Decimal("0.01"))
        chave = (doc.get("tipo_documento"), doc.get("numero_nf"), doc.get("numero_pedido"), valor)
        if chave in vistos:
            continue
        vistos.add(chave)
        valores.append(valor)
    return sum(valores) if valores else None
