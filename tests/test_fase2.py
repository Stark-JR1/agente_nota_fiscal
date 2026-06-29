from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.services.confianca_service import aplicar_scores, calcular_confianca_documento
from app.services.execucao_service import carregar_ultima_execucao, registrar_execucao
from app.watchers.folder_watcher import aguardar_estabilizacao


def documento(**extras):
    base = {
        "tipo_documento": "NF_PRODUTO",
        "arquivo_origem": "NF.pdf",
        "fornecedor_nome": "FORNECEDOR",
        "fornecedor_cnpj": "12.345.678/0001-95",
        "numero_nf": "123",
        "valor_total": Decimal("100.00"),
        "confianca_ocr": 1.0,
        "confianca_extracao": 1.0,
    }
    return {**base, **extras}


def test_score_documento_considera_ocr_e_campos_encontrados():
    completo = calcular_confianca_documento(documento())
    incompleto = calcular_confianca_documento(
        documento(fornecedor_nome=None, fornecedor_cnpj=None, valor_total=None, confianca_ocr=0.5)
    )
    assert completo == 100
    assert incompleto < completo


def test_score_processo_penaliza_pendencias():
    processos = aplicar_scores([
        {"documentos": [documento()], "erros": []},
        {"documentos": [documento()], "erros": ["Falta boleto", "Divergencia de valor"]},
    ])
    assert processos[0]["confianca_processo"] > processos[1]["confianca_processo"]


def test_registra_ultima_execucao(tmp_path):
    inicio = datetime(2026, 6, 10, 10, 0, 0)
    processos = [{"status": "APROVADO"}, {"status": "PENDENTE_BOLETO"}]
    registrar_execucao(tmp_path, inicio, inicio + timedelta(seconds=12), 3, processos, 1)
    dados = carregar_ultima_execucao(tmp_path)
    assert dados["duracao_segundos"] == 12
    assert dados["processos_aprovados"] == 1
    assert dados["processos_pendentes"] == 1


def test_watchdog_aceita_pdf_estavel(tmp_path):
    pdf = Path(tmp_path) / "estavel.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    assert aguardar_estabilizacao(pdf, segundos=1, intervalo=0.01)
