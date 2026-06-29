from __future__ import annotations

import argparse
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from ..agrupador import agrupar_documentos
from ..classificador import classificar_texto
from ..config import carregar_config
from ..extrator_campos import extrair_campos
from ..leitor_pdf import extrair_texto_paginas
from ..models.resultado import ResultadoProcessamento
from ..paths import montar_pastas
from ..origem_documento import caminho_fisico_documento
from ..relatorio import gerar_relatorios
from ..renomeador import SUFIXOS, dados_nome_processo, nome_documento, nome_pdf_unido
from ..unificador import ORDEM, unir_processo
from ..utils import ensure_dir, sanitizar_nome_arquivo
from ..validador import validar_processo
from .confianca_service import aplicar_scores
from .controle_fiscal_service import atualizar_controle_fiscal
from .execucao_service import registrar_execucao


def main() -> None:
    parser = argparse.ArgumentParser(description="Robo de conferencia de PDFs fiscais.")
    parser.add_argument("--dry-run", action="store_true", help="Le, classifica e gera relatorio sem mover/renomear arquivos.")
    args = parser.parse_args()

    resultado = processar_pasta(config=carregar_config(), dry_run=args.dry_run)
    imprimir_resumo_resultado(resultado)


def processar_pasta(config, dry_run: bool = False) -> ResultadoProcessamento:
    inicio = datetime.now()
    pastas = montar_pastas(config)
    configurar_logs(pastas.logs, pastas.data)
    imprimir_inicio(pastas.entrada, dry_run)
    pdfs = listar_pdfs(pastas.entrada)
    progresso(f"Arquivos PDF encontrados: {len(pdfs)}")
    documentos = processar_arquivos_paralelo(pdfs, config)

    progresso("Normalizando paginas do mesmo arquivo...")
    progresso("Agrupando documentos em processos...")
    processos = aplicar_scores(processar_documentos(documentos, config.tolerancia_valor))
    progresso(f"Processos encontrados: {len(processos)}")

    if not dry_run:
        progresso("Gerando arquivos aprovados e pendencias...")
        for processo in processos:
            try:
                if processo.get("status") == "APROVADO":
                    progresso(f"  {processo['id']}: aprovado. Gerando PDFs...")
                    processar_aprovado(processo, pastas)
                else:
                    progresso(f"  {processo['id']}: pendente ({processo.get('status')}). Separando pendencia...")
                    processar_pendente(processo, pastas)
            except FileNotFoundError as exc:
                registrar_erro_arquivo(processo, exc)
                progresso(f"  {processo['id']}: arquivo fisico ausente. Processo mantido como pendencia.")
                tentar_processar_pendencia(processo, pastas)
            except Exception as exc:
                logging.exception("Falha isolada ao gerar saida do processo %s: %s", processo.get("id"), exc)
                processo["status"] = "PENDENTE_ERRO_ARQUIVO"
                processo.setdefault("erros", []).append(f"Erro ao gerar arquivos do processo: {exc}")
                progresso(f"  {processo['id']}: erro ao gerar saida. Lote continuara.")
                tentar_processar_pendencia(processo, pastas)
    else:
        progresso("Dry-run: simulando nomes finais sem mover arquivos...")
        for processo in processos:
            for doc in processo["documentos"]:
                doc["arquivo_final"] = nome_documento(doc, processo)

    progresso("Gerando relatorios...")
    relatorio_xlsx, relatorio_pendencias, relatorio_txt = gerar_relatorios(processos, pastas.relatorios, pastas.data)
    if not dry_run:
        progresso("Atualizando controle fiscal...")
        atualizar_controle_fiscal(processos, pastas.base / "RELATORIOS", datetime.now())
    registrar_execucao(
        pastas.logs,
        inicio,
        datetime.now(),
        len(pdfs),
        processos,
        sum(1 for documento in documentos if documento.get("origem_texto") == "erro"),
    )
    return ResultadoProcessamento(
        pasta_entrada=pastas.entrada,
        total_pdfs=len(pdfs),
        processos=processos,
        relatorio_xlsx=relatorio_xlsx,
        relatorio_pendencias=relatorio_pendencias,
        relatorio_txt=relatorio_txt,
        dry_run=dry_run,
    )


def processar_arquivos_paralelo(pdfs: list[Path], config) -> list[dict]:
    if not pdfs:
        return []
    documentos_por_indice: dict[int, list[dict]] = {}
    workers = min(config.max_workers, len(pdfs))
    progresso(f"Leitura paralela iniciada com {workers} trabalhador(es).")
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="pdf") as executor:
        futuros = {executor.submit(processar_arquivo, pdf, config): (indice, pdf) for indice, pdf in enumerate(pdfs)}
        for futuro in as_completed(futuros):
            indice, pdf = futuros[futuro]
            documentos_por_indice[indice] = futuro.result()
            progresso(f"[{indice + 1}/{len(pdfs)}] Leitura concluida: {pdf.name}")
    return [documento for indice in sorted(documentos_por_indice) for documento in documentos_por_indice[indice]]


def processar_arquivo(pdf: Path, config) -> list[dict]:
    documentos = []
    try:
        paginas = extrair_texto_paginas(
            pdf,
            config.limite_texto_minimo_pdf_digital,
            config.tesseract_path,
            habilitar_cache=config.habilitar_cache,
        )
        progresso(f"  Paginas encontradas: {len(paginas)}")
        for pagina in paginas:
            tipo, confianca = classificar_texto(pagina["texto"])
            campos = extrair_campos(pagina, tipo, confianca)
            documentos.append(campos)
            progresso(f"  Pagina {pagina['pagina']}: {tipo} | origem={pagina['origem_texto']} | valor={campos.get('valor_total') or '-'}")
            logging.info("Campos extraidos: %s", campos_seguros_para_log(campos))
    except Exception as exc:
        progresso(f"  ERRO ao processar {pdf.name}: {exc}")
        logging.exception("Erro ao processar arquivo %s: %s", pdf, exc)
        documentos.append({"tipo_documento": "DESCONHECIDO", "arquivo_origem": str(pdf), "caminho_original": str(pdf), "arquivo_nome": pdf.name, "pagina": 1, "observacoes": str(exc), "origem_texto": "erro", "texto_extraido": "", "confianca_extracao": 0.0})
    return documentos


def campos_seguros_para_log(campos: dict) -> dict:
    sensiveis = {
        "texto_extraido",
        "linha_digitavel",
        "codigo_barras",
        "dados_bancarios",
        "agencia",
        "conta",
        "pix",
    }
    permitidos = {
        "tipo_documento",
        "arquivo_nome",
        "pagina",
        "origem_texto",
        "fornecedor_nome",
        "numero_nf",
        "numero_pedido",
        "valor_total",
        "confianca_extracao",
    }
    return {chave: valor for chave, valor in campos.items() if chave in permitidos and chave not in sensiveis}


def processar_documentos(documentos: list[dict], tolerancia: float) -> list[dict]:
    normalizados = normalizar_paginas_mesmo_arquivo(documentos)
    processos = agrupar_documentos(normalizados) if normalizados else []
    return validar_processos_com_progresso(processos, tolerancia)


def imprimir_resumo_resultado(resultado: ResultadoProcessamento) -> None:
    imprimir_resumo(
        resultado.pasta_entrada,
        resultado.total_pdfs,
        resultado.processos,
        resultado.relatorio_xlsx,
        resultado.relatorio_txt,
        resultado.dry_run,
        resultado.relatorio_pendencias,
    )


def progresso(mensagem: str) -> None:
    agora = datetime.now().strftime("%H:%M:%S")
    print(f"[{agora}] {mensagem}", flush=True)


def imprimir_inicio(pasta_entrada: Path, dry_run: bool) -> None:
    print("========================================", flush=True)
    print("ROBO DE CONFERENCIA PDF - FINANCEIRO", flush=True)
    print("========================================", flush=True)
    print(f"Modo: {'DRY-RUN' if dry_run else 'EXECUCAO'}", flush=True)
    print(f"Pasta de entrada: {pasta_entrada}", flush=True)
    print("", flush=True)


def validar_processos_com_progresso(processos: list[dict], tolerancia: float) -> list[dict]:
    validados = []
    for processo in processos:
        validado = validar_processo(processo, tolerancia)
        erros = "; ".join(validado.get("erros", [])) or "sem divergencias"
        tipos = ", ".join(sorted({str(doc.get("tipo_documento")) for doc in validado.get("documentos", [])}))
        progresso(f"  {validado['id']}: {validado['status']} | {tipos} | {erros}")
        validados.append(validado)
    return validados


def configurar_logs(pasta_logs: Path, data_ref) -> None:
    ensure_dir(pasta_logs)
    caminho_log = pasta_logs / f"robo_fiscal_{data_ref.strftime('%Y-%m-%d')}.log"
    logging.basicConfig(
        filename=caminho_log,
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        encoding="utf-8",
    )


def listar_pdfs(pasta: Path) -> list[Path]:
    if not pasta.exists():
        logging.warning("Pasta de entrada nao encontrada: %s", pasta)
        return []
    return sorted(p for p in pasta.glob("*.pdf") if p.is_file())


def normalizar_paginas_mesmo_arquivo(documentos: list[dict]) -> list[dict]:
    por_arquivo: dict[str, list[dict]] = {}
    for doc in documentos:
        por_arquivo.setdefault(str(doc.get("arquivo_origem")), []).append(doc)

    campos_herdados = [
        "fornecedor_nome",
        "fornecedor_cnpj",
        "sistermi_cnpj",
        "numero_nf",
        "numero_pedido",
        "serie_nf",
        "filial_pedido",
        "centro_custo",
        "frota",
        "placa",
        "contrato_sem_pedido",
    ]

    for docs in por_arquivo.values():
        docs.sort(key=lambda d: int(d.get("pagina") or 0))
        if len(docs) > 1:
            for doc in docs:
                doc["grupo_arquivo"] = str(doc.get("arquivo_origem"))
        referencias_por_tipo: dict[str, dict] = {}
        for doc in docs:
            if doc.get("tipo_documento") in {"NF_PRODUTO", "NF_SERVICO"} and doc.get("valor_total") == 0:
                doc["valor_total"] = None
                doc["valor_produtos"] = None
                doc["valor_servico"] = None

            tipo = doc.get("tipo_documento")
            if tipo and tipo != "DESCONHECIDO" and tipo not in referencias_por_tipo:
                referencias_por_tipo[tipo] = doc

        tem_documento_conhecido = bool(referencias_por_tipo)
        for doc in docs:
            if doc.get("tipo_documento") == "DESCONHECIDO" and tem_documento_conhecido:
                referencia = next(iter(referencias_por_tipo.values()))
                for campo in campos_herdados:
                    if not doc.get(campo) and referencia.get(campo):
                        doc[campo] = referencia[campo]
                doc["tipo_documento"] = "OUTRO_ANEXO"
                doc["observacoes"] = "Pagina tratada como anexo dentro de PDF com documentos identificados."
                continue

            referencia = referencias_por_tipo.get(doc.get("tipo_documento"))
            if not referencia:
                continue
            for campo in campos_herdados:
                if not doc.get(campo) and referencia.get(campo):
                    doc[campo] = referencia[campo]

    return documentos


def processar_aprovado(processo: dict, pastas) -> None:
    pasta_processados = ensure_dir(pastas.processados)
    pasta_completos = ensure_dir(pastas.completos)

    for doc in sorted(processo["documentos"], key=lambda d: (ORDEM.get(d.get("tipo_documento"), 99), d.get("pagina", 0))):
        destino = caminho_unico(pasta_processados / nome_documento(doc, processo))
        doc["nome_normalizado"] = destino.name
        salvar_pagina_individual(doc, destino)
        doc["arquivo_final"] = str(destino)
        logging.info("Arquivo movido/gerado: %s", destino)

    destino_unido = caminho_unico(pasta_completos / nome_pdf_unido(processo))
    unir_processo(processo, destino_unido)
    processo["arquivo_unido"] = str(destino_unido)
    logging.info("PDF unido gerado: %s", destino_unido)


def registrar_erro_arquivo(processo: dict, exc: FileNotFoundError) -> None:
    processo["status"] = "PENDENTE_ERRO_ARQUIVO"
    mensagem = str(exc)
    processo.setdefault("erros", []).append(mensagem)
    logging.exception(
        "Arquivo fisico ausente ao gerar processo %s | documentos=%s",
        processo.get("id"),
        [
            {
                "caminho_original": doc.get("caminho_original"),
                "arquivo_nome": doc.get("arquivo_nome"),
                "nome_normalizado": doc.get("nome_normalizado"),
            }
            for doc in processo.get("documentos", [])
        ],
    )


def tentar_processar_pendencia(processo: dict, pastas) -> None:
    try:
        processar_pendente(processo, pastas)
    except Exception as exc:
        logging.exception("Nao foi possivel materializar a pendencia do processo %s: %s", processo.get("id"), exc)


def processar_pendente(processo: dict, pastas) -> None:
    nome_base = nome_pasta_pendencia(processo)
    pasta_processo = ensure_dir(pastas.pendencias_dia / nome_base)
    pasta_geral = ensure_dir(pastas.pendencias_geral / nome_base)

    originais_copiados = set()
    for doc in processo["documentos"]:
        try:
            origem = caminho_fisico_documento(doc)
        except FileNotFoundError:
            continue
        if origem in originais_copiados:
            continue
        nome_final = nome_documento_pendencia(doc, processo)
        destino = caminho_unico(pasta_processo / nome_final)
        destino_geral = caminho_unico(pasta_geral / nome_final)
        shutil.copy2(origem, destino)
        shutil.copy2(origem, destino_geral)
        doc["arquivo_final"] = str(destino)
        originais_copiados.add(origem)

    erro = texto_erro(processo)
    (pasta_processo / "erro.txt").write_text(erro, encoding="utf-8")
    (pasta_geral / "erro.txt").write_text(erro, encoding="utf-8")
    logging.info("Erro encontrado: %s | %s", processo.get("status"), processo.get("erros"))


def nome_pasta_pendencia(processo: dict) -> str:
    fornecedor, nf, _valor = dados_nome_processo(processo)
    fornecedor = sanitizar_nome_arquivo(fornecedor, limite=14)
    pedidos = sorted({str(doc.get("numero_pedido")) for doc in processo["documentos"] if doc.get("numero_pedido")})
    pedido = "PC" + "-".join(pedidos) if pedidos else "SEMPC"
    rotulo_nf = f"NF{nf}" if nf and nf != "SEM NF" else "SEMNF"
    return sanitizar_nome_arquivo(f"{fornecedor} {rotulo_nf} {pedido}", limite=40)


def nome_documento_pendencia(doc: dict, processo: dict) -> str:
    sufixo = SUFIXOS.get(doc.get("tipo_documento"), "OUTRO")
    return sanitizar_nome_arquivo(f"{sufixo}.pdf", limite=32)


def backup_originais(processo: dict, pasta_backup: Path) -> None:
    pasta_originais = ensure_dir(pasta_backup / processo["id"] / "arquivos_originais")
    vistos = set()
    for doc in processo["documentos"]:
        try:
            origem = caminho_fisico_documento(doc)
        except FileNotFoundError:
            continue
        if origem in vistos:
            continue
        shutil.copy2(origem, caminho_unico(pasta_originais / origem.name))
        vistos.add(origem)


def salvar_pagina_individual(doc: dict, destino: Path) -> None:
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError as exc:
        raise RuntimeError("Instale as dependencias com: pip install -r requirements.txt") from exc

    origem = caminho_fisico_documento(doc)
    if not origem.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {origem}")
    pagina = int(doc.get("pagina") or 1) - 1
    reader = PdfReader(str(origem))
    writer = PdfWriter()
    if 0 <= pagina < len(reader.pages):
        writer.add_page(reader.pages[pagina])
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("wb") as arquivo:
        writer.write(arquivo)


def caminho_unico(caminho: Path) -> Path:
    if not caminho.exists():
        return caminho
    stem, suffix = caminho.stem, caminho.suffix
    contador = 2
    while True:
        candidato = caminho.with_name(f"{stem} ({contador}){suffix}")
        if not candidato.exists():
            return candidato
        contador += 1


def texto_erro(processo: dict) -> str:
    docs = processo["documentos"]
    fornecedor = next((d.get("fornecedor_nome") for d in docs if d.get("fornecedor_nome")), "Nao identificado")
    nf = next((d.get("numero_nf") for d in docs if d.get("numero_nf")), "Nao identificada")
    linhas = [
        f"Fornecedor: {fornecedor}",
        f"NF: {nf}",
        f"Status: {processo.get('status')}",
        "Problema: " + ("; ".join(processo.get("erros", [])) or "Conferencia manual necessaria."),
        f"Valor NF: {processo.get('valor_nf')}",
        f"Soma pedidos: {processo.get('valor_pedidos')}",
        f"Soma boletos: {processo.get('valor_boletos')}",
        "Acao necessaria: verificar documentos ausentes, CNPJ, valores ou qualidade do OCR.",
    ]
    return "\n".join(linhas)


def imprimir_resumo(
    pasta_entrada: Path,
    total_pdfs: int,
    processos: list[dict],
    relatorio_xlsx: Path,
    relatorio_txt: Path,
    dry_run: bool,
    relatorio_pendencias: Path | None = None,
) -> None:
    aprovados = sum(1 for p in processos if p.get("status") == "APROVADO")
    pendentes = len(processos) - aprovados
    modo = "DRY-RUN" if dry_run else "EXECUCAO"
    print("========================================")
    print("ROBO DE CONFERENCIA PDF - FINANCEIRO")
    print("========================================")
    print(f"Modo: {modo}")
    print("")
    print("Pasta de entrada:")
    print(pasta_entrada)
    print("")
    print(f"Arquivos encontrados: {total_pdfs}")
    print(f"Processos aprovados: {aprovados}")
    print(f"Processos pendentes: {pendentes}")
    print("")
    print("Relatorio gerado em:")
    print(relatorio_xlsx)
    if relatorio_pendencias:
        print(relatorio_pendencias)
    print(relatorio_txt)


if __name__ == "__main__":
    main()
