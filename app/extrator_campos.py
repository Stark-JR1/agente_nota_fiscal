from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from .utils import limpar_espacos, normalizar_texto, parse_valor_brl, primeiro, somente_digitos


REGEX_CNPJ = re.compile(r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?!\d)")
REGEX_VALOR = re.compile(r"(?:R\$)?\s*\d{1,3}(?:\.\d{3})*(?:,|\.)\d{2}")
REGEX_DATA = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
REGEX_PEDIDO_FILIAL = re.compile(
    r"(?:PEDIDO\s*(?:/|DO CLIENTE)?\s*FILIAL|PEDIDO/FILIAL|PEDIDO\s*/\s*FILIAL)\s*:?\s*(\d+)\s*/\s*(\d+)",
    re.IGNORECASE,
)
REGEX_LINHA_DIGITAVEL = re.compile(r"\b(?:\d{5}\.?\d{5}\s+\d{5}\.?\d{6}\s+\d{5}\.?\d{6}\s+\d\s+\d{14}|\d{47,48})\b")
REGEX_CHAVE_ACESSO = re.compile(r"\b\d{44}\b")
REGEX_NF = [
    re.compile(r"N[UÚ]MERO\s+(?:DA\s+)?(?:NF[S]?-?E|NOTA)?\s*:?\s*(\d{1,12})", re.IGNORECASE),
    re.compile(r"N[ºO]\s*\.?\s*(\d{1,3}(?:\.\d{3})+|\d{2,12})", re.IGNORECASE),
    re.compile(r"\bNF(?:-?E)?\s*N?[ºO]?\s*:?\s*(\d{1,12})", re.IGNORECASE),
    re.compile(r"\bNFS-?E\s*:?\s*(\d{1,12})", re.IGNORECASE),
]


def _extrair_numero_nf(texto: str) -> str | None:
    especificos = [
        r"N[úu]mero\s+da\s+Nota\s+Fiscal\s*:?\s*(?:\n|\s)+(\d{1,12})",
        r"Referente\s+as\s+NF-e/NFS-e\s+ou\s+RPS\s*:?\s*(\d{1,12})",
        r"\bN\.\s*(\d{1,3}(?:\.\d{3})+|\d{2,12})",
        r"\bN[º°]\s*:?\s*(\d{1,12})",
    ]
    for padrao in especificos:
        match = re.search(padrao, texto, re.IGNORECASE)
        if match:
            return _normalizar_numero(re.sub(r"\D", "", match.group(1)))
    for regex in REGEX_NF:
        match = regex.search(texto)
        if match:
            return _normalizar_numero(re.sub(r"\D", "", match.group(1)))
    return None


def _extrair_numero_nf_nome_arquivo(nome: str | None) -> str | None:
    if not nome:
        return None
    match = re.search(r"\b(?:NF|CTE|CT-E|DACTE)\s*[-_ ]?\s*(\d{2,12})\b", nome, re.IGNORECASE)
    return _normalizar_numero(match.group(1)) if match else None


def _normalizar_numero(numero: str) -> str:
    return numero.lstrip("0") or "0"


def _numero_nf_confiavel(numero: str | None) -> str | None:
    if not numero:
        return None
    numero = _normalizar_numero(re.sub(r"\D", "", str(numero)))
    return None if numero in {"0", "1", "2"} else numero


def _extrair_fornecedor(texto: str, tipo: str) -> str | None:
    linhas = [limpar_espacos(l) for l in texto.splitlines() if limpar_espacos(l)]
    texto_norm = normalizar_texto(texto)

    if tipo == "RECIBO_LOCACAO":
        match = re.search(r"Raz[ãa]o\s+Social\s*:?\s*(.+?)(?:\n|CNPJ|Logradouro|$)", texto, re.IGNORECASE | re.DOTALL)
        if match:
            return limpar_espacos(match.group(1))[:90]
        for i, linha in enumerate(linhas):
            if normalizar_texto(linha) == "DADOS DO LOCADOR":
                for candidato in linhas[i + 1:i + 8]:
                    if _linha_fornecedor_valida(candidato) and "LTDA" in normalizar_texto(candidato):
                        return candidato[:90]

    if tipo == "NF_SERVICO" and linhas:
        for linha in linhas[:5]:
            if _linha_fornecedor_valida(linha) and ("LTDA" in normalizar_texto(linha) or "ME" in normalizar_texto(linha)):
                return linha[:90]

    if tipo == "NF_PRODUTO":
        recebemos = re.search(r"RECEBEMOS\s+DE\s+(.+?)\s+OS\s+PROD[UO]TOS", texto, re.IGNORECASE)
        if recebemos:
            return limpar_espacos(recebemos.group(1))[:90]
        for i, linha in enumerate(linhas):
            if "IDENTIFICACAO DO EMITENTE" in normalizar_texto(linha) and i + 1 < len(linhas) and _linha_fornecedor_valida(linhas[i + 1]):
                return linhas[i + 1][:90]
        for linha in linhas[:35]:
            linha_norm = normalizar_texto(linha)
            if _linha_fornecedor_valida(linha) and "LTDA" in linha_norm and "SISTERMI" not in linha_norm:
                return linha[:90]

    if tipo == "BOLETO":
        for linha in linhas:
            linha_norm = normalizar_texto(linha)
            if _linha_fornecedor_valida(linha) and "LTDA" in linha_norm and "SISTERMI" not in linha_norm and "BANCO" not in linha_norm:
                return re.sub(r"\s+CNPJ:.*", "", linha, flags=re.IGNORECASE)[:90]
        for i, linha in enumerate(linhas):
            if normalizar_texto(linha) == "BENEFICIARIO" and i + 1 < len(linhas):
                prox = linhas[i + 1]
                if "VENCIMENTO" not in normalizar_texto(prox):
                    return re.sub(r"\s+CNPJ:.*", "", prox, flags=re.IGNORECASE)[:90]

    if tipo == "DACTE":
        for linha in linhas[:12]:
            linha_norm = normalizar_texto(linha)
            if _linha_fornecedor_valida(linha) and "LTDA" in linha_norm and "SISTERMI" not in linha_norm:
                return re.sub(r"\s+CNPJ\s*:.*", "", linha, flags=re.IGNORECASE)[:90]

    padroes = [
        r"RAZ[ÃA]O\s+SOCIAL\s*:?\s*(.+)",
        r"FORNECEDOR\s*:?\s*(.+)",
        r"BENEFICIARIO\s*:?\s*(.+)",
        r"PRESTADOR DO SERVICO\s*:?\s*(.+)",
        r"EMITENTE\s*:?\s*(.+)",
    ]
    for padrao in padroes:
        match = re.search(padrao, texto, re.IGNORECASE)
        if match:
            return limpar_espacos(match.group(1))[:90]

    if tipo in {"NF_PRODUTO", "NF_SERVICO"}:
        for i, linha in enumerate(linhas):
            if "CNPJ" in normalizar_texto(linha) and i > 0:
                candidato = linhas[i - 1]
                if len(candidato) > 4 and not REGEX_CNPJ.search(candidato) and _linha_fornecedor_valida(candidato):
                    return candidato[:90]

    if "VISUAL RODOPAR" in texto_norm:
        for linha in linhas:
            if len(linha) > 6 and not REGEX_CNPJ.search(linha) and "PEDIDO" not in normalizar_texto(linha):
                return linha[:90]
    return None


def _linha_fornecedor_valida(linha: str) -> bool:
    linha_norm = normalizar_texto(linha)
    bloqueados = [
        "DOCUMENTO AUXILIAR",
        "DATA DO DOCUMENTO",
        "SEFAZ AUTORIZADORA",
        "CHAVE DE ACESSO",
        "E-MAIL",
        "FONE",
        "SITE:",
        "CNPJ 27.535.996",
    ]
    return bool(linha.strip()) and not any(bloqueado in linha_norm for bloqueado in bloqueados)


def _valor_por_rotulo(texto: str, rotulos: list[str]) -> Decimal | None:
    for rotulo in rotulos:
        regex = re.compile(rotulo + r".{0,60}?(" + REGEX_VALOR.pattern + r")", re.IGNORECASE | re.DOTALL)
        match = regex.search(texto)
        if match:
            return parse_valor_brl(match.group(1))
    return None


def _extrair_cnpj_fornecedor(texto: str, tipo: str, cnpjs: list[str]) -> str | None:
    if tipo == "PEDIDO_COMPRA":
        match = re.search(r"CNPJ/CPF\s*:?\s*(" + REGEX_CNPJ.pattern + r")", texto, re.IGNORECASE)
        if match:
            return match.group(1)

    if tipo == "BOLETO":
        beneficiario = re.search(r"Benefici[áa]rio.{0,120}?CNPJ\s*:?\s*(" + REGEX_CNPJ.pattern + r")", texto, re.IGNORECASE | re.DOTALL)
        if beneficiario:
            return beneficiario.group(1)
        return next((c for c in cnpjs if re.sub(r"\D", "", c) != "27535996001249"), None)

    if tipo in {"NF_PRODUTO", "NF_SERVICO", "DACTE", "RECIBO_LOCACAO"}:
        return next((c for c in cnpjs if re.sub(r"\D", "", c) != "27535996001249"), None)

    return cnpjs[0] if cnpjs else None


def _maior_valor(texto: str) -> Decimal | None:
    valores = [v for v in (parse_valor_brl(m.group(0)) for m in REGEX_VALOR.finditer(texto)) if v is not None]
    return max(valores) if valores else None


def _valor_nf_produto_por_linha(texto: str) -> Decimal | None:
    texto_norm = normalizar_texto(texto)
    linhas = [limpar_espacos(linha) for linha in texto.splitlines() if limpar_espacos(linha)]
    for indice, linha in enumerate(linhas):
        if "VALOR TOTAL DA NOTA" not in normalizar_texto(linha):
            continue
        janela = " ".join(linhas[indice : indice + 16])
        valores = [parse_valor_brl(m.group(0)) for m in REGEX_VALOR.finditer(janela)]
        valores = [valor for valor in valores if valor is not None]
        if valores:
            positivos = [valor for valor in valores if valor > 0]
            return max(positivos) if positivos else valores[-1]

    if "VALOR TOTAL DA NOTA" in texto_norm:
        valores = [v for v in (parse_valor_brl(m.group(0)) for m in REGEX_VALOR.finditer(texto)) if v is not None]
        positivos = [valor for valor in valores if valor > 0]
        return max(positivos) if positivos else None
    return None


def _ultimo_valor_apos_rotulo(texto: str, rotulo: str, janela: int = 3) -> Decimal | None:
    linhas = [limpar_espacos(linha) for linha in texto.splitlines() if limpar_espacos(linha)]
    rotulo_norm = normalizar_texto(rotulo)
    for indice, linha in enumerate(linhas):
        if rotulo_norm not in normalizar_texto(linha):
            continue
        trecho = " ".join(linhas[indice : indice + janela])
        valores = [parse_valor_brl(match.group(0)) for match in REGEX_VALOR.finditer(trecho)]
        valores = [valor for valor in valores if valor is not None]
        if valores:
            return valores[-1]
    return None


def _valores_calculo_nf(texto: str) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    linhas = [limpar_espacos(linha) for linha in texto.splitlines() if limpar_espacos(linha)]
    for indice, linha in enumerate(linhas):
        linha_norm = normalizar_texto(linha)
        if "VALOR DO FRETE" not in linha_norm or "TOTAL" not in linha_norm or "NOTA" not in linha_norm:
            continue
        trecho = " ".join(linhas[indice + 1 : indice + 3])
        valores = [parse_valor_brl(match.group(0)) for match in REGEX_VALOR.finditer(trecho)]
        valores = [valor for valor in valores if valor is not None]
        if len(valores) >= 6:
            return valores[0], valores[3], valores[-1]
    return None, None, None


def _extrair_itens_chave(texto: str) -> list[str]:
    texto_norm = normalizar_texto(texto)
    termos = []
    for termo in ("PALHETA", "LAMPADA", "PNEU", "FILTRO", "OLEO", "CORREIA", "BATERIA", "PARAFUSO"):
        if termo in texto_norm:
            termos.append(termo)
    return termos


def _valor_servicos_pedido(texto: str) -> Decimal | None:
    linhas = [limpar_espacos(linha) for linha in texto.splitlines() if limpar_espacos(linha)]
    valores = []
    for indice, linha in enumerate(linhas):
        if normalizar_texto(linha) not in {"SER", "SERV"}:
            continue
        for anterior in reversed(linhas[max(0, indice - 8):indice]):
            candidatos = [parse_valor_brl(match.group(0)) for match in REGEX_VALOR.finditer(anterior)]
            positivos = [valor for valor in candidatos if valor is not None and valor > 0]
            if positivos:
                valores.append(positivos[-1])
                break
    return sum(set(valores)) if valores else None


def _valor_nf_servico(texto: str) -> Decimal | None:
    linhas = [limpar_espacos(linha) for linha in texto.splitlines() if limpar_espacos(linha)]
    for indice, linha in enumerate(linhas):
        linha_norm = normalizar_texto(linha)
        if "VALOR SERVICO" not in linha_norm and "VALOR DO SERVICO" not in linha_norm:
            continue
        trecho = " ".join(linhas[indice:indice + 3])
        valores = [parse_valor_brl(match.group(0)) for match in REGEX_VALOR.finditer(trecho)]
        positivos = [valor for valor in valores if valor is not None and valor > 0]
        if positivos:
            return positivos[0]
    return None


def _extrair_pedidos_referenciados(texto: str) -> list[str]:
    padroes = [
        r"PEDIDO\(S\)\s+DE\s+COMPRA\s*:?\s*(?:OC\s*)?(\d{3,12})",
        r"PEDIDO\s+DE\s+COMPRA\s*:?\s*(?:OC\s*)?(\d{3,12})",
        r"PEDIDO\s+DO\s+CLIENTE\s*:?\s*(\d{3,12})",
        r"ORDEM\s+DE\s+COMPRA\s*:?\s*(?:OC\s*)?(\d{3,12})",
        r"\bXPED\s*:?\s*(\d{3,12})",
    ]
    encontrados = []
    for padrao in padroes:
        encontrados.extend(re.findall(padrao, texto, re.IGNORECASE))
    return sorted(set(encontrados))


def _fornecedor_nome_arquivo(nome: str) -> str | None:
    prefixo = re.split(r"\s+-\s+(?:NF|NFS|CTE|CT-E|DACTE|BOLETO|PC)\b", nome, maxsplit=1, flags=re.IGNORECASE)[0]
    prefixo = limpar_espacos(prefixo)
    return prefixo if len(prefixo) >= 4 else None


def _fornecedor_nome_confiavel(nome: str | None) -> bool:
    if not nome:
        return False
    nome_norm = limpar_espacos(normalizar_texto(nome))
    bloqueados = [
        "CPF/CNPJ",
        "CNPJ/CPF",
        "NOME/RAZAO SOCIAL",
        "DA NFS-E",
        "DADOS DA NFS-E",
        "CONFORME",
        "DATA EMISSAO",
        "DATA DE EMISSAO",
        "EMISSAO",
        "IDENTIFICACAO DO EMITENTE",
        "INSCRICAO MUNICIPAL",
        "TELEFONE",
    ]
    if any(bloqueado in nome_norm for bloqueado in bloqueados):
        return False
    if nome_norm.startswith("CNPJ ") or re.search(r"\bCNP\b", nome_norm) or REGEX_CNPJ.fullmatch(nome.strip()):
        return False
    letras = sum(ch.isalpha() for ch in nome_norm)
    return letras >= 4


def _valor_linha_digitavel(linha_digitavel: str | None) -> Decimal | None:
    digitos = somente_digitos(linha_digitavel)
    if len(digitos) < 10:
        return None
    valor = Decimal(digitos[-10:]) / Decimal("100")
    return valor if valor > 0 else None


def _valor_nome_arquivo(nome: str | None) -> Decimal | None:
    if not nome:
        return None
    match = re.search(r"R\$\s*(\d+(?:\.\d{3})*(?:,|\.)\d{2})", nome, re.IGNORECASE)
    return parse_valor_brl(match.group(1)) if match else None


def _valor_dacte(texto: str) -> Decimal | None:
    linhas = [limpar_espacos(linha) for linha in texto.splitlines() if limpar_espacos(linha)]
    for indice, linha in enumerate(linhas):
        linha_norm = normalizar_texto(linha)
        if "VALOR TOTAL DO SERVICO" not in linha_norm and "VALOR TOTAL DA PRESTACAO" not in linha_norm:
            continue
        janela = " ".join(linhas[indice : indice + 8])
        valores = [parse_valor_brl(m.group(0)) for m in REGEX_VALOR.finditer(janela)]
        valores = [valor for valor in valores if valor is not None and valor > 0]
        if valores:
            return valores[0]
    return None


def _documento_ocr_confiavel(texto: str, tipo: str) -> bool:
    texto_norm = limpar_espacos(normalizar_texto(texto))
    if tipo == "NF_PRODUTO":
        return "DANFE" in texto_norm and "CHAVE DE ACESSO" in texto_norm and "NATUREZA DA OPERACAO" in texto_norm
    if tipo == "DACTE":
        return "DACTE" in texto_norm and "CHAVE DE ACESSO" in texto_norm and "CONHECIMENTO DE TRANSPORTE" in texto_norm
    if tipo == "BOLETO":
        return "FICHA DE COMPENSACAO" in texto_norm and ("LINHA DIGITAVEL" in texto_norm or bool(REGEX_LINHA_DIGITAVEL.search(texto)))
    return False


def _cnpj_valido(cnpj: str) -> bool:
    digitos = somente_digitos(cnpj)
    if len(digitos) != 14 or len(set(digitos)) == 1:
        return False

    def calc(pos: int) -> str:
        pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] if pos == 13 else [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        base = digitos[:pos]
        soma = sum(int(num) * peso for num, peso in zip(base, pesos[-len(base):]))
        resto = soma % 11
        return "0" if resto < 2 else str(11 - resto)

    return digitos[12] == calc(12) and digitos[13] == calc(13)


def extrair_campos(pagina: dict, tipo_documento: str, confianca_classificacao: float) -> dict:
    texto = pagina.get("texto", "")
    arquivo_nome = Path(str(pagina.get("arquivo_origem"))).name
    contrato_sem_pedido = _contrato_sem_pedido(texto)
    cnpjs = [cnpj for cnpj in REGEX_CNPJ.findall(texto) if _cnpj_valido(cnpj)]
    datas = REGEX_DATA.findall(texto)
    pedido = REGEX_PEDIDO_FILIAL.search(texto)
    linha_digitavel = REGEX_LINHA_DIGITAVEL.search(texto)
    chave = REGEX_CHAVE_ACESSO.search(re.sub(r"\D", "", texto))
    valor_frete_nf, outras_despesas_nf, valor_total_nf = _valores_calculo_nf(texto)

    valor_total = _valor_por_rotulo(
        texto,
        [
            r"VALOR\s+L[ÍI]QUIDO\s+DA\s+NOTA\s+FISCAL",
            r"VALOR\s+T\s*OTAL\s+DOS\s+SERVI[ÇC]OS",
            r"VALOR\s+TOTAL\s+DOS\s+SERVI[ÇC]OS",
            r"VALOR\s+TOTAL(?:\s+DA\s+NOTA)?",
            r"TOTAL\s+DA\s+NOTA",
            r"V\.\s*TOTAL\s+DA\s+NOTA",
            r"V\.\s*TOTAL\s+PRODUTOS",
            r"TOTAL\s+PRD",
            r"VALOR\s+DO\s+DOCUMENTO",
            r"VALOR\s+COBRADO",
        ],
    )
    if tipo_documento == "BOLETO":
        valor_total = primeiro(_valor_linha_digitavel(linha_digitavel.group(0) if linha_digitavel else None), valor_total)
    if tipo_documento == "DACTE":
        valor_total = primeiro(_valor_dacte(texto), valor_total)
    if tipo_documento == "RECIBO_CONTRATO":
        valor_total = primeiro(_valor_recibo_maria_ines(texto), _valor_nome_arquivo(arquivo_nome), valor_total)
    if tipo_documento == "RECIBO_LOCACAO":
        valor_total = primeiro(
            _valor_por_rotulo(texto, [r"VALOR\s+TOTAL", r"VALOR\s+DO\s+RECIBO", r"VALOR\s+DA\s+LOCACAO"]),
            valor_total,
        )
    if tipo_documento == "NF_SERVICO":
        valor_total = primeiro(_valor_nf_servico(texto), valor_total)
    if tipo_documento == "NF_PRODUTO" and (valor_total is None or valor_total == 0):
        valor_total = primeiro(_valor_nf_produto_por_linha(texto), valor_total)
    valor_produtos = (
        _ultimo_valor_apos_rotulo(texto, "VALOR TOTAL DOS PRODUTOS")
        if tipo_documento == "NF_PRODUTO"
        else None
    )
    if tipo_documento == "NF_PRODUTO":
        valor_total = primeiro(
            valor_total_nf,
            _ultimo_valor_apos_rotulo(texto, "VALOR TOTAL DA NOTA"),
            _ultimo_valor_apos_rotulo(texto, "VALOR TOTAL. DA NOTA"),
            valor_total,
        )
    if pagina.get("origem_texto") == "ocr" and tipo_documento in {"NF_PRODUTO", "DACTE"}:
        valor_total = primeiro(_valor_nome_arquivo(arquivo_nome), valor_total)
    if pagina.get("origem_texto") == "ocr" and tipo_documento == "BOLETO":
        valor_total = primeiro(valor_total, _valor_nome_arquivo(arquivo_nome))
    if pagina.get("origem_texto") == "ocr" and tipo_documento == "NF_SERVICO":
        valor_total = primeiro(valor_total, _valor_nome_arquivo(arquivo_nome))
    valor_total = primeiro(valor_total, _maior_valor(texto))
    valor_servicos_pedido = _valor_servicos_pedido(texto) if tipo_documento == "PEDIDO_COMPRA" else None
    valor_produtos_pedido = (
        valor_total - valor_servicos_pedido
        if tipo_documento == "PEDIDO_COMPRA"
        and valor_total is not None
        and valor_servicos_pedido is not None
        and valor_total >= valor_servicos_pedido
        else None
    )
    confianca_extracao = round((pagina.get("confianca_ocr", 0.0) + confianca_classificacao) / 2, 2)
    if pagina.get("origem_texto") == "ocr" and _documento_ocr_confiavel(texto, tipo_documento):
        confianca_extracao = 1.0

    campos = {
        "tipo_documento": tipo_documento,
        "arquivo_origem": pagina.get("arquivo_origem"),
        "caminho_original": pagina.get("caminho_original") or pagina.get("arquivo_origem"),
        "pagina": pagina.get("pagina"),
        "fornecedor_nome": _extrair_fornecedor(texto, tipo_documento),
        "fornecedor_cnpj": _extrair_cnpj_fornecedor(texto, tipo_documento, cnpjs),
        "sistermi_cnpj": next((c for c in cnpjs if re.sub(r"\D", "", c) == "27535996001249"), None),
        "numero_nf": primeiro(
            _numero_nf_confiavel(_extrair_numero_nf_nome_arquivo(arquivo_nome))
            if tipo_documento in {"NF_PRODUTO", "NF_SERVICO", "DACTE"}
            else None,
            _numero_nf_confiavel(_extrair_numero_nf(texto)),
        ),
        "serie_nf": primeiro(_buscar(texto, r"S[ÉE]RIE\s*:?\s*(\d+)"), _buscar(texto, r"SERIE\s*:?\s*(\d+)")),
        "numero_pedido": pedido.group(1) if pedido else _buscar(texto, r"PEDIDO(?:\s+DO\s+CLIENTE)?\s*:?\s*(\d+)"),
        "filial_pedido": pedido.group(2) if pedido else None,
        "valor_total": valor_total,
        "valor_boleto": valor_total if tipo_documento == "BOLETO" else None,
        "valor_produtos": valor_produtos if tipo_documento == "NF_PRODUTO" else None,
        "valor_produtos_pedido": valor_produtos_pedido,
        "valor_servicos_pedido": valor_servicos_pedido,
        "valor_frete": valor_frete_nf if tipo_documento == "NF_PRODUTO" else None,
        "outras_despesas": outras_despesas_nf if tipo_documento == "NF_PRODUTO" else None,
        "itens_chave": _extrair_itens_chave(texto),
        "pedidos_referenciados": _extrair_pedidos_referenciados(texto),
        "valor_servico": valor_total if tipo_documento in {"NF_SERVICO", "DACTE", "RECIBO_LOCACAO"} else None,
        "vencimento": datas[0] if tipo_documento == "BOLETO" and datas else None,
        "data_emissao": datas[0] if tipo_documento != "BOLETO" and datas else None,
        "linha_digitavel": linha_digitavel.group(0) if linha_digitavel else None,
        "chave_acesso": chave.group(0) if chave else None,
        "centro_custo": _buscar(texto, r"CENTRO\s+DE\s+CUSTO\s*:?\s*([A-Z0-9 ._-]+)"),
        "frota": _buscar(texto, r"FROTA\s*:?\s*([A-Z0-9 ._-]+)"),
        "placa": _buscar(texto, r"\bPLACA\s*:?\s*([A-Z]{3}\s*-?\s*\d[A-Z0-9]\d{2})"),
        "observacoes": None,
        "contrato_sem_pedido": contrato_sem_pedido,
        "confianca_extracao": confianca_extracao,
        "origem_texto": pagina.get("origem_texto"),
        "texto_extraido": texto,
    }

    if contrato_sem_pedido == "INTERNET_SUPER":
        campos["fornecedor_nome"] = "INTERNET SUPER LTDA - ME"
        campos["fornecedor_cnpj"] = "24.774.313/0001-65"

    if tipo_documento in {"NF_PRODUTO", "NF_SERVICO"} and _nf_emitida_pela_sistermi(texto):
        campos["fornecedor_nome"] = "SISTERMI LOCACAO DE MAQUINAS E EQUIPAMENTOS LTDA"
        campos["fornecedor_cnpj"] = "27.535.996/0012-49"
        campos["sistermi_cnpj"] = "27.535.996/0012-49"
        campos["contrato_sem_pedido"] = "SISTERMI_NF_PROPRIA"

    if (
        tipo_documento in {"NF_PRODUTO", "NF_SERVICO"}
        and "SISTERMI" in normalizar_texto(campos.get("fornecedor_nome") or "")
        and somente_digitos(campos.get("fornecedor_cnpj")) != "27535996001249"
    ):
        campos["fornecedor_nome"] = primeiro(_fornecedor_nome_arquivo(arquivo_nome), campos["fornecedor_nome"])

    if tipo_documento in {"NF_PRODUTO", "NF_SERVICO"} and "LIEBHERR" in normalizar_texto(texto + " " + arquivo_nome):
        campos["fornecedor_nome"] = "LIEBHERR BRASIL LTDA"
        campos["fornecedor_cnpj"] = "44.021.095/0001-03"
        campos["contrato_sem_pedido"] = "LIEBHERR_NF_PEDIDO"

    if "NET VALE" in normalizar_texto(texto + " " + arquivo_nome):
        campos["contrato_sem_pedido"] = "NET_VALE_NF_BOLETO"

    contrato_maria = _contrato_maria_ines(texto, arquivo_nome)
    if contrato_maria:
        campos["fornecedor_nome"] = "MARIA INES COTA PINHEIRO"
        campos["fornecedor_cnpj"] = "679.253.916-34"
        campos["contrato_sem_pedido"] = contrato_maria

    if not campos["fornecedor_nome"] and campos["fornecedor_cnpj"]:
        campos["fornecedor_nome"] = f"CNPJ {campos['fornecedor_cnpj']}"
    if not _fornecedor_nome_confiavel(campos["fornecedor_nome"]):
        campos["fornecedor_nome"] = primeiro(_fornecedor_nome_arquivo(arquivo_nome), campos["fornecedor_nome"])
    campos["arquivo_nome"] = Path(str(campos["arquivo_origem"])).name
    return campos


def _buscar(texto: str, padrao: str) -> str | None:
    match = re.search(padrao, texto, re.IGNORECASE)
    return limpar_espacos(match.group(1)) if match else None


def _contrato_sem_pedido(texto: str) -> str | None:
    texto_norm = normalizar_texto(texto)
    if "INTERNET SUPER" in texto_norm or "24.774.313/0001-65" in texto or "24774313000165" in somente_digitos(texto):
        return "INTERNET_SUPER"
    if "VIGILANCIA SEGURANCA ELETRONICA" in texto_norm:
        return "VIGILANCIA_SEGURANCA"
    if "NET VALE" in texto_norm:
        return "NET_VALE_NF_BOLETO"
    contrato_maria = _contrato_maria_ines(texto, "")
    if contrato_maria:
        return contrato_maria
    return None


def _contrato_maria_ines(texto: str, arquivo_nome: str) -> str | None:
    texto_norm = normalizar_texto(texto + " " + arquivo_nome)
    if "MARIA INES" not in texto_norm and "679.253.916" not in texto and "679253916" not in somente_digitos(texto):
        return None
    if "ALUGUEL" in texto_norm:
        return "MARIA_INES_ALUGUEL"
    if "ENERGIA" in texto_norm or "FOTOVOLTAICA" in texto_norm:
        return "MARIA_INES_ENERGIA"
    return None


def _valor_recibo_maria_ines(texto: str) -> Decimal | None:
    valor_liquido = _valor_por_rotulo(texto, [r"VALOR\s+LIQUIDO\s+RECEBIDO", r"VALOR\s+DO\s+REEMBOLSO"])
    return valor_liquido


def _nf_emitida_pela_sistermi(texto: str) -> bool:
    linhas = [limpar_espacos(linha) for linha in texto.splitlines() if limpar_espacos(linha)]
    primeira_linha = normalizar_texto(linhas[0] if linhas else "")
    if "RECEBEMOS DE" in primeira_linha:
        return "RECEBEMOS DE SISTERMI" in primeira_linha
    texto_norm = normalizar_texto(texto[:1200])
    if "PRESTADOR" not in texto_norm:
        return False
    bloco_prestador = texto_norm.split("PRESTADOR", 1)[0]
    if "SISTERMI LOCACAO" in bloco_prestador and "RAZAO SOCIAL" in bloco_prestador:
        return True
    return False
