from pathlib import Path

from app.web_legacy import arquivo_corresponde_processo


def test_pdf_completo_precisa_corresponder_ao_fornecedor_e_nf(tmp_path: Path):
    processo = {"fornecedor": "POLI FILTRO INDUSTRIA LTDA", "nf": "91583", "valor": "R$ 1.052,00"}
    errado = tmp_path / "AUTO ACESSORIOS PAULOMAR - NF 47595 - R$ 99,80 - PROCESSO COMPLETO.pdf"
    certo = tmp_path / "POLI FILTRO INDUSTRIA - NF 91583 - R$ 1.052,00 - PROCESSO COMPLETO.pdf"
    errado.write_bytes(b"%PDF-1.4 errado")
    certo.write_bytes(b"%PDF-1.4 certo")

    assert not arquivo_corresponde_processo(errado, processo)
    assert arquivo_corresponde_processo(certo, processo)
