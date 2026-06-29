from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from ..classificador import classificar_texto
from ..config import carregar_config
from ..extrator_campos import extrair_campos
from ..utils import limpar_espacos, normalizar_texto, parse_valor_brl

VALOR_MAXIMO_NORMAL = Decimal("100000.00")
VALOR_MAXIMO_ABSOLUTO = Decimal("500000.00")
TERMOS_VALOR_INVALIDO = (
    "CHAVE DE ACESSO", "CNPJ", "CPF", "PROTOCOLO", "NOSSO NUMERO",
    "LINHA DIGITAVEL", "CODIGO DE BARRAS", "CEP", "TELEFONE",
)
MESES = {
    "JANEIRO": "01", "FEVEREIRO": "02", "MARCO": "03", "ABRIL": "04",
    "MAIO": "05", "JUNHO": "06", "JULHO": "07", "AGOSTO": "08",
    "SETEMBRO": "09", "OUTUBRO": "10", "NOVEMBRO": "11", "DEZEMBRO": "12",
}

ORIGENS = {
    "01 - BRUTO": ("BRUTO", "DOCUMENTO_BRUTO"),
    "02 - PROCESSADO": ("PROCESSADO", "PROCESSO_TRATADO"),
    "03 - ASSINADO": ("ASSINADO", "PROCESSO_ASSINADO"),
}
COLUNAS_RELATORIO = [
    "Origem", "Ano", "Mes", "Dia", "Fornecedor", "CNPJ", "NF", "Pedido", "Valor",
    "Tipo Documento", "Status Historico", "Confianca", "Nome Arquivo", "Caminho Arquivo",
]


def normalizar_fornecedor(nome: str) -> str:
    texto = normalizar_texto(nome)
    texto = re.sub(r"\b(?:LTDA|LTD|EIRELI|ME|EPP)\b", " ", texto)
    texto = re.sub(r"[^A-Z0-9& ]+", " ", texto)
    return limpar_espacos(texto)


def fornecedor_valido(nome: str | None) -> bool:
    if not nome:
        return False
    texto = limpar_espacos(nome)
    normalizado = normalizar_texto(texto)
    normalizado_limpo = normalizar_fornecedor(texto)
    letras = sum(caractere.isalpha() for caractere in normalizado)
    bloqueados = (
        "PROCESSO COMPLETO", "COMPROVANTE DE PAGAMENTO", "QUESTIONARIO",
        "CHAVE DE ACESSO", "RECEBEMOS", "PRODUTOS CONSTANTES", "R$",
        "SERIE NRO DOCUMENTO", "NRO DOCUMENTO", "NUMERO DOCUMENTO",
        "NOME FORNECEDOR", "RAZAO SOCIAL", "IDENTIFICACAO DO EMITENTE",
    )
    return not (
        len(texto) > 80
        or letras < 3
        or texto.isdigit()
        or normalizado.startswith("NF ")
        or any(item in normalizado or item in normalizado_limpo for item in bloqueados)
        or bool(re.fullmatch(r"[0-9A-F]{8}-[0-9A-F-]{27,}", normalizado))
        or bool(re.fullmatch(r"[A-Z0-9]{12,}", normalizado))
    )


def extrair_fornecedor_nome_arquivo(nome: str) -> str | None:
    stem = Path(nome).stem
    partes = re.split(
        r"\s*[-_]\s*(?=(?:NF|NFS|NFE|BOLETO|BOL|OC|PC|PEDIDO|CTE|CT-E|DACTE|FATURA|PROCESSO)\b)",
        stem,
        maxsplit=1,
        flags=re.IGNORECASE,
    )
    fornecedor = limpar_espacos(partes[0]).strip(" -_.")
    bloqueados = {"BOLETO", "NOTA FISCAL", "PROCESSO COMPLETO", "DOCUMENTO"}
    return fornecedor if fornecedor_valido(fornecedor) and normalizar_texto(fornecedor) not in bloqueados else None


def extrair_fornecedor_historico(nome_arquivo: str, texto: str | None = None) -> tuple[str | None, str]:
    pelo_nome = extrair_fornecedor_nome_arquivo(nome_arquivo)
    if pelo_nome:
        return pelo_nome, "NOME_ARQUIVO"
    if texto:
        tipo, confianca = classificar_texto(texto)
        campos = extrair_campos(
            {"texto": texto, "arquivo_origem": nome_arquivo, "pagina": 1, "origem_texto": "digital", "confianca_ocr": 1.0},
            tipo,
            confianca,
        )
        pelo_texto = campos.get("fornecedor_nome")
        if fornecedor_valido(pelo_texto):
            return pelo_texto, "TEXTO_PDF"
    candidato = limpar_espacos(Path(nome_arquivo).stem)
    return None, "INVALIDO" if candidato else "NAO_ENCONTRADO"


def extrair_nf_nome_arquivo(nome: str) -> str | None:
    match = re.search(r"\b(?:NF|NFS|NFE)\s*[-_.:]?\s*(\d{2,12})\b", Path(nome).stem, re.IGNORECASE)
    return (match.group(1).lstrip("0") or "0") if match else None


def extrair_pedido_nome_arquivo(nome: str) -> str | None:
    match = re.search(r"\b(?:OC|PC|PEDIDO)\s*[-_.:]?\s*(\d{3,12})\b", Path(nome).stem, re.IGNORECASE)
    return (match.group(1).lstrip("0") or "0") if match else None


def extrair_valor_nome_arquivo(nome: str) -> Decimal | None:
    match = re.search(r"R\$\s*(\d[\d.,]*[,.]\d{2})", Path(nome).stem, re.IGNORECASE)
    if not match:
        return None
    return _parse_valor_historico(match.group(1))


def _parse_valor_historico(valor: str) -> Decimal | None:
    digitos = re.sub(r"\D", "", valor)
    if not digitos or len(digitos) >= 12:
        return None
    texto = re.sub(r"[^\d.,]", "", valor)
    separadores = [indice for indice, char in enumerate(texto) if char in ",."]
    if not separadores:
        return None
    ultimo = separadores[-1]
    centavos = re.sub(r"\D", "", texto[ultimo + 1:])
    inteiro = re.sub(r"\D", "", texto[:ultimo])
    if len(centavos) != 2 or not inteiro:
        return None
    return Decimal(f"{inteiro}.{centavos}")


def classificar_valor(valor: Decimal | None) -> str:
    if valor is None or valor <= 0:
        return "SEM_VALOR"
    if valor <= VALOR_MAXIMO_NORMAL:
        return "VALOR_OK"
    if valor <= VALOR_MAXIMO_ABSOLUTO:
        return "VALOR_ALTO_REVISAR"
    return "VALOR_SUSPEITO"


def extrair_valor_historico(texto: str, nome_arquivo: str) -> tuple[Decimal | None, str]:
    valor_nome = extrair_valor_nome_arquivo(nome_arquivo)
    if valor_nome is not None:
        status = classificar_valor(valor_nome)
        return valor_nome, "VALOR_SUSPEITO" if status == "VALOR_SUSPEITO" else "NOME_ARQUIVO"
    for match in re.finditer(r"R\$\s*(\d[\d.,]*[,.]\d{2})", texto or "", re.IGNORECASE):
        contexto = normalizar_texto((texto or "")[max(0, match.start() - 50):match.end() + 20])
        if any(termo in contexto for termo in TERMOS_VALOR_INVALIDO):
            continue
        valor = _parse_valor_historico(match.group(1))
        if valor is not None:
            status = classificar_valor(valor)
            return valor, "VALOR_SUSPEITO" if status == "VALOR_SUSPEITO" else "TEXTO_PDF"
    return None, "NAO_ENCONTRADO"


def normalizar_mes_historico(valor: str | None) -> str:
    texto = normalizar_texto(valor or "")
    match = re.search(r"(?<!\d)(0[1-9]|1[0-2])(?!\d)", texto)
    if match:
        return match.group(1)
    return next((numero for nome, numero in MESES.items() if nome in texto), "SEM_MES")


def extrair_tipo_nome_arquivo(nome: str) -> str:
    texto = normalizar_texto(Path(nome).stem)
    regras = [
        ("PROCESSO_COMPLETO", ("PROCESSO COMPLETO", "COMPLETO")),
        ("PEDIDO_COMPRA", ("PEDIDO", " OC ", "-OC ", " PC ", "-PC ")),
        ("BOLETO", ("BOLETO", "BOLETOS", "BOL ")),
        ("DACTE", ("DACTE", "CT-E", "CTE")),
        ("NF_SERVICO", ("NFS", "NOTA SERVICO")),
        ("NF_PRODUTO", (" NF ", "-NF ", "NFE", "NOTA FISCAL")),
        ("COMPROVANTE", ("COMPROVANTE",)),
        ("CONTRATO", ("CONTRATO",)),
    ]
    delimitado = f" {texto} "
    for tipo, termos in regras:
        if any(termo in delimitado for termo in termos):
            return tipo
    return "DESCONHECIDO"


def hash_arquivo(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def extrair_texto_digital(caminho: Path, max_paginas: int = 3) -> str:
    import fitz

    textos = []
    with fitz.open(caminho) as pdf:
        for indice in range(min(pdf.page_count, max_paginas)):
            textos.append(pdf.load_page(indice).get_text("text") or "")
    return "\n".join(textos)


def metadados_caminho(caminho: Path, raiz_origem: Path, origem: str, status: str) -> dict:
    relativos = caminho.relative_to(raiz_origem).parts
    ano = next((parte for parte in relativos if re.fullmatch(r"20\d{2}", parte)), "")
    dia = next((parte for parte in relativos if re.fullmatch(r"\d{2}-\d{2}-20\d{2}", parte)), "")
    mes = "SEM_MES"
    if dia:
        mes = dia[3:5]
    elif ano:
        indice = relativos.index(ano)
        mes = normalizar_mes_historico(relativos[indice + 1] if indice + 1 < len(relativos) - 1 else "")
    return {"origem": origem, "status_historico": status, "ano": ano, "mes": mes, "dia": dia}


def catalogar_arquivo(
    caminho: Path,
    raiz_origem: Path,
    origem: str,
    status: str,
    hash_precalculado: str | None = None,
) -> dict:
    nome = caminho.name
    fornecedor_nome = extrair_fornecedor_nome_arquivo(nome)
    valor_nome = extrair_valor_nome_arquivo(nome)
    dados = {
        **metadados_caminho(caminho, raiz_origem, origem, status),
        "caminho_arquivo": str(caminho),
        "nome_arquivo": nome,
        "extensao": caminho.suffix.lower(),
        "fornecedor": fornecedor_nome,
        "fornecedor_original": fornecedor_nome,
        "fornecedor_normalizado": normalizar_fornecedor(fornecedor_nome or "") or None,
        "origem_fornecedor": "NOME_ARQUIVO" if fornecedor_nome else "INVALIDO",
        "cnpj": None,
        "numero_nf": extrair_nf_nome_arquivo(nome),
        "numero_pedido": extrair_pedido_nome_arquivo(nome),
        "valor": valor_nome,
        "origem_valor": "NOME_ARQUIVO" if valor_nome is not None else "NAO_ENCONTRADO",
        "valor_status": classificar_valor(valor_nome),
        "tipo_documento": extrair_tipo_nome_arquivo(nome),
        "confianca": 0.45,
        "data_indexacao": datetime.now().isoformat(timespec="seconds"),
        "hash_arquivo": hash_precalculado or hash_arquivo(caminho),
        "erro_categoria": None,
        "observacao_indexacao": None,
    }
    try:
        texto = extrair_texto_digital(caminho)
        if len(texto.strip()) < 150:
            dados["status_historico"] = "PENDENTE_OCR_HISTORICO"
            dados["erro_categoria"] = _categorias_qualidade(dados, pendente_ocr=True)
            return dados
        tipo_conteudo, confianca = classificar_texto(texto)
        tipo = tipo_conteudo if tipo_conteudo != "DESCONHECIDO" else dados["tipo_documento"]
        campos = extrair_campos(
            {"texto": texto, "arquivo_origem": str(caminho), "pagina": 1, "origem_texto": "digital", "confianca_ocr": 1.0},
            tipo,
            confianca,
        )
        fornecedor, origem_fornecedor = extrair_fornecedor_historico(nome, texto)
        valor, origem_valor = extrair_valor_historico(texto, nome)
        dados.update({
            "fornecedor": fornecedor,
            "fornecedor_original": fornecedor,
            "fornecedor_normalizado": normalizar_fornecedor(fornecedor or "") or None,
            "origem_fornecedor": origem_fornecedor,
            "cnpj": campos.get("fornecedor_cnpj"),
            "numero_nf": dados["numero_nf"] or campos.get("numero_nf"),
            "numero_pedido": dados["numero_pedido"] or campos.get("numero_pedido"),
            "valor": valor,
            "origem_valor": origem_valor,
            "valor_status": classificar_valor(valor),
            "tipo_documento": dados["tipo_documento"] if dados["tipo_documento"] != "DESCONHECIDO" else tipo,
            "confianca": round(max(float(campos.get("confianca_extracao") or 0), 0.55), 2),
        })
    except (RuntimeError, ValueError) as exc:
        dados["erro_categoria"] = "ERRO_PDF_CORROMPIDO"
        dados["observacao_indexacao"] = str(exc)[:300]
    except OSError as exc:
        dados["erro_categoria"] = "ERRO_LEITURA_ARQUIVO"
        dados["observacao_indexacao"] = str(exc)[:300]
    dados["erro_categoria"] = _categorias_qualidade(dados, existente=dados.get("erro_categoria"))
    return dados


def _categorias_qualidade(
    dados: dict,
    pendente_ocr: bool = False,
    existente: str | None = None,
) -> str | None:
    categorias = [categoria for categoria in (existente,) if categoria]
    if pendente_ocr:
        categorias.append("PENDENTE_OCR_HISTORICO")
    if not dados.get("fornecedor"):
        categorias.append("NOME_FORNECEDOR_INVALIDO" if dados.get("origem_fornecedor") == "INVALIDO" else "SEM_FORNECEDOR")
    if not dados.get("numero_nf") and dados.get("tipo_documento") in {"NF_PRODUTO", "NF_SERVICO", "PROCESSO_COMPLETO"}:
        categorias.append("SEM_NF")
    if dados.get("valor_status") == "SEM_VALOR":
        categorias.append("SEM_VALOR")
    if dados.get("valor_status") in {"VALOR_ALTO_REVISAR", "VALOR_SUSPEITO"}:
        categorias.append(dados["valor_status"])
    return ",".join(dict.fromkeys(categorias)) or None


def _fornecedor_conteudo_confiavel(nome: str | None) -> str | None:
    if not nome:
        return None
    normalizado = normalizar_texto(nome)
    bloqueados = ("RECEBEMOS", "PRODUTOS CONSTANTES", "ARQUIVO PDF", ".PDF", "CNPJ ", "EQUIPAMENTOS LTDA")
    if any(item in normalizado for item in bloqueados) or len(nome) > 100:
        return None
    return nome


def catalogar_em_paralelo(
    arquivos: list[tuple[Path, Path, str, str]],
    hashes_existentes: set[str] | None = None,
    workers: int = 8,
):
    hashes_existentes = hashes_existentes or set()

    def tarefa(item):
        caminho, raiz, origem, status = item
        try:
            digest = hash_arquivo(caminho)
            if digest in hashes_existentes:
                return None
            return catalogar_arquivo(caminho, raiz, origem, status, digest)
        except Exception as exc:
            nome = caminho.name
            fornecedor = extrair_fornecedor_nome_arquivo(nome)
            valor = extrair_valor_nome_arquivo(nome)
            return {
                **metadados_caminho(caminho, raiz, origem, status),
                "caminho_arquivo": str(caminho), "nome_arquivo": nome, "extensao": caminho.suffix.lower(),
                "fornecedor": fornecedor, "fornecedor_original": fornecedor,
                "fornecedor_normalizado": normalizar_fornecedor(fornecedor or "") or None,
                "origem_fornecedor": "NOME_ARQUIVO" if fornecedor else "INVALIDO",
                "cnpj": None, "numero_nf": extrair_nf_nome_arquivo(nome),
                "numero_pedido": extrair_pedido_nome_arquivo(nome), "valor": valor,
                "origem_valor": "NOME_ARQUIVO" if valor is not None else "NAO_ENCONTRADO",
                "valor_status": classificar_valor(valor), "tipo_documento": extrair_tipo_nome_arquivo(nome),
                "confianca": 0.35, "data_indexacao": datetime.now().isoformat(timespec="seconds"),
                "hash_arquivo": "ERRO_PATH_" + hashlib.sha256(str(caminho).encode("utf-8")).hexdigest(),
                "erro_categoria": _categorias_qualidade(
                    {"fornecedor": fornecedor, "origem_fornecedor": "NOME_ARQUIVO" if fornecedor else "INVALIDO",
                     "numero_nf": extrair_nf_nome_arquivo(nome), "tipo_documento": extrair_tipo_nome_arquivo(nome),
                     "valor_status": classificar_valor(valor)},
                    existente="ERRO_LEITURA_ARQUIVO",
                ),
                "observacao_indexacao": str(exc)[:300],
            }

    with ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="historico") as executor:
        yield from executor.map(tarefa, arquivos)


def listar_historicos(base: Path, ano: str | None = None) -> list[tuple[Path, Path, str, str]]:
    historico = base / "HISTORICO_LEGADO"
    encontrados = []
    for pasta, (origem, status) in ORIGENS.items():
        raiz = historico / pasta
        if not raiz.exists():
            continue
        for caminho in raiz.rglob("*"):
            if caminho.is_file() and caminho.suffix.lower() == ".pdf":
                if ano and ano not in caminho.relative_to(raiz).parts:
                    continue
                encontrados.append((caminho, raiz, origem, status))
    return sorted(encontrados, key=lambda item: str(item[0]))


def conectar_banco(caminho: Path) -> sqlite3.Connection:
    conexao = sqlite3.connect(caminho)
    conexao.executescript(
        """
        CREATE TABLE IF NOT EXISTS documentos_historicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, origem TEXT, ano TEXT, mes TEXT, dia TEXT,
            caminho_arquivo TEXT, nome_arquivo TEXT, extensao TEXT, fornecedor TEXT, cnpj TEXT,
            numero_nf TEXT, numero_pedido TEXT, valor REAL, tipo_documento TEXT,
            status_historico TEXT, confianca REAL, data_indexacao TEXT, hash_arquivo TEXT,
            fornecedor_original TEXT, fornecedor_normalizado TEXT, origem_fornecedor TEXT,
            origem_valor TEXT, valor_status TEXT, erro_categoria TEXT, observacao_indexacao TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_documentos_hash ON documentos_historicos(hash_arquivo);
        CREATE TABLE IF NOT EXISTS fornecedores_historicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, fornecedor TEXT, cnpj TEXT, total_documentos INTEGER,
            total_valor REAL, primeiro_registro TEXT, ultimo_registro TEXT, tipos_documento TEXT,
            regras_sugeridas TEXT
        );
        CREATE TABLE IF NOT EXISTS estatisticas_historicas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chave TEXT, valor TEXT, atualizado_em TEXT
        );
        """
    )
    colunas = {linha[1] for linha in conexao.execute("PRAGMA table_info(documentos_historicos)")}
    novas_colunas = {
        "fornecedor_original": "TEXT", "fornecedor_normalizado": "TEXT", "origem_fornecedor": "TEXT",
        "origem_valor": "TEXT", "valor_status": "TEXT", "erro_categoria": "TEXT", "observacao_indexacao": "TEXT",
    }
    for coluna, tipo in novas_colunas.items():
        if coluna not in colunas:
            conexao.execute(f"ALTER TABLE documentos_historicos ADD COLUMN {coluna} {tipo}")
    conexao.commit()
    return conexao


def inserir_lote(conexao: sqlite3.Connection, registros: list[dict]) -> tuple[int, int]:
    sql = """
        INSERT OR IGNORE INTO documentos_historicos
        (origem, ano, mes, dia, caminho_arquivo, nome_arquivo, extensao, fornecedor, cnpj,
         numero_nf, numero_pedido, valor, tipo_documento, status_historico, confianca,
         data_indexacao, hash_arquivo, fornecedor_original, fornecedor_normalizado,
         origem_fornecedor, origem_valor, valor_status, erro_categoria, observacao_indexacao)
        VALUES (:origem, :ano, :mes, :dia, :caminho_arquivo, :nome_arquivo, :extensao,
         :fornecedor, :cnpj, :numero_nf, :numero_pedido, :valor, :tipo_documento,
         :status_historico, :confianca, :data_indexacao, :hash_arquivo, :fornecedor_original,
         :fornecedor_normalizado, :origem_fornecedor, :origem_valor, :valor_status,
         :erro_categoria, :observacao_indexacao)
    """
    antes = conexao.total_changes
    conexao.executemany(sql, [_serializar(registro) for registro in registros])
    conexao.commit()
    inseridos = conexao.total_changes - antes
    return inseridos, len(registros) - inseridos


def carregar_documentos(conexao: sqlite3.Connection) -> list[dict]:
    conexao.row_factory = sqlite3.Row
    return [dict(linha) for linha in conexao.execute("SELECT * FROM documentos_historicos ORDER BY id")]


def gerar_estatisticas(registros: list[dict]) -> dict:
    origens = Counter(registro.get("origem") for registro in registros)
    fornecedores = Counter(
        registro.get("fornecedor_normalizado")
        for registro in registros
        if fornecedor_valido(registro.get("fornecedor")) and registro.get("fornecedor_normalizado")
    )
    valores_fornecedor: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for registro in registros:
        if (
            registro.get("fornecedor_normalizado")
            and registro.get("valor") is not None
            and registro.get("valor_status") == "VALOR_OK"
        ):
            valores_fornecedor[registro["fornecedor_normalizado"]] += Decimal(str(registro["valor"]))
    valores_suspeitos = [
        {
            "arquivo": r.get("nome_arquivo"),
            "fornecedor": r.get("fornecedor_normalizado"),
            "valor": float(r["valor"]) if r.get("valor") is not None else None,
            "status": r.get("valor_status"),
        }
        for r in registros if r.get("valor_status") in {"VALOR_ALTO_REVISAR", "VALOR_SUSPEITO"}
    ][:100]
    return {
        "total_arquivos": len(registros),
        "total_bruto": origens["BRUTO"],
        "total_processado": origens["PROCESSADO"],
        "total_assinado": origens["ASSINADO"],
        "total_fornecedores": len(fornecedores),
        "valor_total_identificado": float(sum((
            Decimal(str(r["valor"])) for r in registros
            if r.get("valor") is not None and r.get("valor_status") == "VALOR_OK"
        ), Decimal("0"))),
        "top_fornecedores": [{"fornecedor": nome, "total": total} for nome, total in fornecedores.most_common(10)],
        "top_valores": [{"fornecedor": nome, "valor": float(valor)} for nome, valor in sorted(valores_fornecedor.items(), key=lambda item: item[1], reverse=True)[:10]],
        "valores_suspeitos": valores_suspeitos,
        "documentos_por_ano": dict(Counter(r.get("ano") or "SEM_ANO" for r in registros)),
        "documentos_por_mes": dict(Counter(r.get("mes") or "SEM_MES" for r in registros)),
        "tipos_documento": dict(Counter(r.get("tipo_documento") or "DESCONHECIDO" for r in registros)),
        "pendentes_ocr": sum(r.get("status_historico") == "PENDENTE_OCR_HISTORICO" for r in registros),
        "sem_fornecedor": sum(not r.get("fornecedor") for r in registros),
        "sem_nf": sum(not r.get("numero_nf") for r in registros),
        "sem_valor": sum(r.get("valor") is None for r in registros),
    }


def gerar_fornecedores_regras(registros: list[dict]) -> tuple[dict, dict]:
    grupos: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for registro in registros:
        if fornecedor_valido(registro.get("fornecedor")) and registro.get("fornecedor_normalizado"):
            grupos[(registro["fornecedor_normalizado"], registro.get("cnpj") or "")].append(registro)
    fornecedores, regras = [], []
    for (nome, cnpj), docs in sorted(grupos.items()):
        tipos = sorted({doc.get("tipo_documento") for doc in docs if doc.get("tipo_documento")})
        datas = sorted(doc.get("data_indexacao") for doc in docs if doc.get("data_indexacao"))
        total_valor = sum((
            Decimal(str(doc["valor"])) for doc in docs
            if doc.get("valor") is not None and doc.get("valor_status") == "VALOR_OK"
        ), Decimal("0"))
        fornecedores.append({
            "nome": nome, "cnpj": cnpj or None, "total_documentos": len(docs),
            "total_valor": float(total_valor), "tipos_encontrados": tipos,
            "primeiro_registro": datas[0] if datas else "", "ultimo_registro": datas[-1] if datas else "",
        })
        regras.append({
            "fornecedor": nome, "cnpj": cnpj or None,
            "pedido_obrigatorio": "PEDIDO_COMPRA" in tipos,
            "boleto_obrigatorio": "BOLETO" in tipos,
            "aceita_multiplos_pedidos": sum(doc.get("tipo_documento") == "PEDIDO_COMPRA" for doc in docs) > 1,
            "aceita_boleto_parcelado": sum(doc.get("tipo_documento") == "BOLETO" for doc in docs) > 1,
            "observacao": "Regra sugerida com base no historico. Nao aplicada automaticamente.",
        })
    return {"fornecedores": fornecedores}, {"regras_fornecedores": regras}


def atualizar_tabelas_resumo(conexao: sqlite3.Connection, fornecedores: dict, estatisticas: dict) -> None:
    conexao.execute("DELETE FROM fornecedores_historicos")
    for item in fornecedores["fornecedores"]:
        conexao.execute(
            """INSERT INTO fornecedores_historicos
            (fornecedor, cnpj, total_documentos, total_valor, primeiro_registro, ultimo_registro, tipos_documento, regras_sugeridas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (item["nome"], item["cnpj"], item["total_documentos"], item["total_valor"], item["primeiro_registro"],
             item["ultimo_registro"], json.dumps(item["tipos_encontrados"], ensure_ascii=False), "Ver CONFIG/regras.json"),
        )
    conexao.execute("DELETE FROM estatisticas_historicas")
    agora = datetime.now().isoformat(timespec="seconds")
    conexao.executemany(
        "INSERT INTO estatisticas_historicas (chave, valor, atualizado_em) VALUES (?, ?, ?)",
        [(chave, json.dumps(valor, ensure_ascii=False), agora) for chave, valor in estatisticas.items()],
    )
    conexao.commit()


def gerar_relatorios(registros: list[dict], pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    linhas = [{
        "Origem": r.get("origem"), "Ano": r.get("ano"), "Mes": r.get("mes"), "Dia": r.get("dia"),
        "Fornecedor": r.get("fornecedor"), "CNPJ": r.get("cnpj"), "NF": r.get("numero_nf"),
        "Pedido": r.get("numero_pedido"), "Valor": r.get("valor"), "Tipo Documento": r.get("tipo_documento"),
        "Status Historico": r.get("status_historico"), "Confianca": r.get("confianca"),
        "Nome Arquivo": r.get("nome_arquivo"), "Caminho Arquivo": r.get("caminho_arquivo"),
    } for r in registros]
    try:
        import pandas as pd

        pd.DataFrame(linhas, columns=COLUNAS_RELATORIO).to_excel(pasta / "relatorio_historico.xlsx", index=False)
    except ImportError:
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(COLUNAS_RELATORIO)
        for linha in linhas:
            ws.append([linha.get(coluna) for coluna in COLUNAS_RELATORIO])
        wb.save(pasta / "relatorio_historico.xlsx")
    estatisticas = gerar_estatisticas(registros)
    (pasta / "resumo_historico.txt").write_text(
        "\n".join(f"{chave}: {valor}" for chave, valor in estatisticas.items()), encoding="utf-8"
    )
    erros = [{
        "Origem": r.get("origem"), "Ano": r.get("ano"), "Mes": r.get("mes"), "Dia": r.get("dia"),
        "Nome Arquivo": r.get("nome_arquivo"), "Caminho Arquivo": r.get("caminho_arquivo"),
        "Erro Categoria": r.get("erro_categoria"), "Observacao": r.get("observacao_indexacao"),
        "Fornecedor Extraido": r.get("fornecedor"), "Valor Extraido": r.get("valor"),
        "Tipo Documento": r.get("tipo_documento"), "Confianca": r.get("confianca"),
    } for r in registros if r.get("erro_categoria")]
    try:
        import pandas as pd

        pd.DataFrame(erros).to_excel(pasta / "relatorio_erros_indexacao.xlsx", index=False)
    except ImportError:
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        colunas = list(erros[0]) if erros else ["Erro Categoria"]
        ws.append(colunas)
        for linha in erros:
            ws.append([linha.get(coluna) for coluna in colunas])
        wb.save(pasta / "relatorio_erros_indexacao.xlsx")


def gerar_erros_indexacao(registros: list[dict], erros_tecnicos: int = 0) -> dict:
    categorias = Counter()
    amostras = []
    for registro in registros:
        for categoria in str(registro.get("erro_categoria") or "").split(","):
            if categoria:
                categorias[categoria] += 1
                if len(amostras) < 100:
                    amostras.append({
                        "arquivo": registro.get("nome_arquivo"),
                        "categoria": categoria,
                        "observacao": registro.get("observacao_indexacao"),
                    })
    return {
        "total_erros": sum(categorias.values()) + erros_tecnicos,
        "erros_tecnicos": erros_tecnicos,
        "pendencias_qualidade": sum(categorias.values()),
        "por_categoria": dict(categorias),
        "amostras": amostras,
    }


def indexar_historico(
    base: Path,
    dry_run: bool = False,
    ano: str | None = None,
    lote: int = 500,
    limite: int | None = None,
    workers: int = 8,
) -> dict:
    inicio = time.monotonic()
    arquivos = listar_historicos(base, ano)
    if limite:
        arquivos = arquivos[:limite]
    resumo = {"encontrados": len(arquivos), "indexados": 0, "duplicados": 0, "erros": 0, "dry_run": dry_run, "ano": ano}
    print(f"Arquivos historicos encontrados: {len(arquivos)}")
    if dry_run:
        amostra = []
        for indice, registro in enumerate(catalogar_em_paralelo(arquivos, workers=workers), start=1):
            try:
                if registro:
                    if "ERRO_LEITURA_ARQUIVO" in str(registro.get("erro_categoria")):
                        resumo["erros"] += 1
                    amostra.append(registro)
            except Exception as exc:
                resumo["erros"] += 1
                print(f"ERRO no arquivo {indice}: {exc}")
            if indice % lote == 0:
                print(f"Dry-run: {indice}/{len(arquivos)} arquivos lidos")
        resumo["indexados"] = len(amostra)
        resumo["estatisticas"] = gerar_estatisticas(amostra)
        resumo["qualidade"] = gerar_erros_indexacao(amostra, resumo["erros"])
        resumo["tempo_segundos"] = round(time.monotonic() - inicio, 2)
        print(json.dumps(resumo, ensure_ascii=False, indent=2))
        return resumo

    historico = base / "HISTORICO_LEGADO"
    database = historico / "_DATABASE"
    config = base / "CONFIG"
    relatorios = base / "RELATORIOS" / "HISTORICO"
    database.mkdir(parents=True, exist_ok=True)
    config.mkdir(parents=True, exist_ok=True)
    log_path = database / "indexacao.log"

    def log(mensagem: str) -> None:
        linha = f"{datetime.now().isoformat(timespec='seconds')} | {mensagem}"
        print(linha)
        with log_path.open("a", encoding="utf-8") as arquivo:
            arquivo.write(linha + "\n")

    log(f"Inicio da indexacao. Total de arquivos encontrados: {len(arquivos)}")
    conexao = conectar_banco(database / "data_historica.db")
    hashes_existentes = {linha[0] for linha in conexao.execute("SELECT hash_arquivo FROM documentos_historicos")}
    pendentes = []
    for indice, registro in enumerate(catalogar_em_paralelo(arquivos, hashes_existentes, workers), start=1):
        try:
            if registro is None:
                resumo["duplicados"] += 1
            else:
                pendentes.append(registro)
                if "ERRO_LEITURA_ARQUIVO" in str(registro.get("erro_categoria")):
                    resumo["erros"] += 1
                    log(f"Erro ao ler arquivo: {registro['caminho_arquivo']} | {registro['observacao_indexacao']}")
        except Exception as exc:
            resumo["erros"] += 1
            log(f"Erro ao ler arquivo numero {indice}: {exc}")
        if len(pendentes) >= lote or indice == len(arquivos):
            inseridos, duplicados = inserir_lote(conexao, pendentes)
            resumo["indexados"] += inseridos
            resumo["duplicados"] += duplicados
            log(f"Lote concluido: {indice}/{len(arquivos)} | indexados={inseridos} | duplicados={duplicados}")
            pendentes = []
    registros = carregar_documentos(conexao)
    estatisticas = gerar_estatisticas(registros)
    fornecedores, regras = gerar_fornecedores_regras(registros)
    atualizar_tabelas_resumo(conexao, fornecedores, estatisticas)
    conexao.close()
    _salvar_json(database / "estatisticas.json", estatisticas)
    _salvar_json(database / "erros_indexacao.json", gerar_erros_indexacao(registros, resumo["erros"]))
    _salvar_json(config / "fornecedores.json", fornecedores)
    _salvar_json(config / "regras.json", regras)
    if not _json_valido(config / "excecoes.json", "excecoes"):
        _salvar_json(config / "excecoes.json", {"excecoes": []})
    gerar_relatorios(registros, relatorios)
    resumo["tempo_segundos"] = round(time.monotonic() - inicio, 2)
    log(f"Fim da indexacao. Tempo total: {resumo['tempo_segundos']}s")
    return resumo


def limpar_base_historica(base: Path) -> Path:
    database = base / "HISTORICO_LEGADO" / "_DATABASE"
    config = base / "CONFIG"
    relatorios = base / "RELATORIOS" / "HISTORICO"
    backup = database / "BACKUP" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup.mkdir(parents=True, exist_ok=False)
    alvos = [
        database / "data_historica.db", database / "estatisticas.json", database / "erros_indexacao.json",
        database / "indexacao.log", config / "fornecedores.json", config / "regras.json",
        relatorios / "relatorio_historico.xlsx", relatorios / "relatorio_erros_indexacao.xlsx",
        relatorios / "resumo_historico.txt",
    ]
    for alvo in alvos:
        if alvo.exists():
            shutil.copy2(alvo, backup / alvo.name)
            alvo.unlink()
    return backup


def _serializar(registro: dict) -> dict:
    opcionais = (
        "fornecedor_original", "fornecedor_normalizado", "origem_fornecedor", "origem_valor",
        "valor_status", "erro_categoria", "observacao_indexacao",
    )
    return {
        **{chave: registro.get(chave) for chave in opcionais},
        **registro,
        "valor": float(registro["valor"]) if registro.get("valor") is not None else None,
    }


def _salvar_json(caminho: Path, dados: dict) -> None:
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    temporario.replace(caminho)


def _json_valido(caminho: Path, chave: str) -> bool:
    if not caminho.exists():
        return False
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return isinstance(dados, dict) and isinstance(dados.get(chave), list)
    except (OSError, ValueError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Indexa o historico legado sem alterar os documentos.")
    parser.add_argument("--dry-run", action="store_true", help="Le e exibe resumo sem gravar artefatos.")
    parser.add_argument("--ano", choices=["2024", "2025", "2026"], help="Indexa somente o ano informado.")
    parser.add_argument("--lote", type=int, default=500, help="Quantidade de arquivos por transacao.")
    parser.add_argument("--limite", type=int, help="Limite opcional para diagnostico.")
    parser.add_argument("--workers", type=int, default=8, help="Leituras digitais simultaneas.")
    parser.add_argument("--limpar-base", action="store_true", help="Faz backup e limpa os artefatos da base historica.")
    args = parser.parse_args()
    base = carregar_config().base_processamento_fiscal
    if args.limpar_base:
        print(f"Backup criado em: {limpar_base_historica(base)}")
        return
    resultado = indexar_historico(
        base,
        dry_run=args.dry_run,
        ano=args.ano,
        lote=max(1, args.lote),
        limite=args.limite,
        workers=max(1, args.workers),
    )
    print(f"Resumo: {resultado}")


if __name__ == "__main__":
    main()
