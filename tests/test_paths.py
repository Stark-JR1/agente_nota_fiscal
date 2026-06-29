from datetime import date

from app.paths import obter_caminhos_do_dia


def test_paths_respeitam_data(tmp_path):
    caminhos = obter_caminhos_do_dia(tmp_path, date(2026, 6, 10))
    assert caminhos["entrada"].name == "ENTRADA"
    assert "10-06-2026" in str(caminhos["entrada"])
