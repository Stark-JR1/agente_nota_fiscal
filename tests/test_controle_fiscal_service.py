from datetime import datetime
from decimal import Decimal

from openpyxl import load_workbook

from app.services.controle_fiscal_service import (
    ABA_PROCESSOS,
    ARQUIVO_CONTROLE,
    STATUS_FISCAL_INICIAL,
    atualizar_controle_fiscal,
)


def processo_aprovado():
    return {
        "status": "APROVADO",
        "valor_nf": Decimal("100.00"),
        "arquivo_unido": r"C:\saida\FORNECEDOR - NF 123.pdf",
        "documentos": [
            {
                "fornecedor_nome": "FORNECEDOR TESTE",
                "fornecedor_cnpj": "12.345.678/0001-95",
                "numero_nf": "123",
                "numero_pedido": "456",
                "valor_total": Decimal("100.00"),
            }
        ],
    }


def linhas(ws):
    return list(ws.iter_rows(min_row=2, values_only=True))


def test_atualiza_controle_fiscal_somente_com_aprovados(tmp_path):
    processos = [
        processo_aprovado(),
        {"status": "PENDENTE_VALOR", "documentos": [{"numero_nf": "999"}]},
    ]

    caminho = atualizar_controle_fiscal(processos, tmp_path, datetime(2026, 6, 18, 8, 0, 0))

    assert caminho == tmp_path / ARQUIVO_CONTROLE
    wb = load_workbook(caminho)
    ws = wb[ABA_PROCESSOS]
    assert len(linhas(ws)) == 1
    assert ws["A2"].value == "18/06/2026 08:00:00"
    assert ws["B2"].value == "456"
    assert ws["C2"].value == "FORNECEDOR TESTE"
    assert ws["E2"].value == "123"
    assert ws["I2"].value == STATUS_FISCAL_INICIAL


def test_nao_duplica_e_preserva_campos_manuais(tmp_path):
    processos = [processo_aprovado()]
    caminho = atualizar_controle_fiscal(processos, tmp_path, datetime(2026, 6, 18, 8, 0, 0))

    wb = load_workbook(caminho)
    ws = wb[ABA_PROCESSOS]
    ws["I2"] = "ENVIADO"
    ws["J2"] = "19/06/2026"
    ws["K2"] = "Observacao manual"
    wb.save(caminho)

    atualizar_controle_fiscal(processos, tmp_path, datetime(2026, 6, 18, 9, 0, 0))

    wb = load_workbook(caminho)
    ws = wb[ABA_PROCESSOS]
    assert len(linhas(ws)) == 1
    assert ws["A2"].value == "18/06/2026 09:00:00"
    assert ws["I2"].value == "ENVIADO"
    assert ws["J2"].value == "19/06/2026"
    assert ws["K2"].value == "Observacao manual"
