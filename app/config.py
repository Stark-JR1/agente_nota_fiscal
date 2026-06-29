from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Config:
    base_processamento_fiscal: Path
    usar_data_atual: bool
    data_manual: str | None
    tesseract_path: str | None
    limite_texto_minimo_pdf_digital: int
    tolerancia_valor: float
    habilitar_cache: bool
    habilitar_watchdog: bool
    watchdog_delay_seconds: int
    watchdog_stable_checks: int
    watchdog_stable_interval_seconds: int
    max_workers: int
    modo_debug: bool


BASE_PROCESSAMENTO_FISCAL = Path(
    r"C:\Users\paulo.junior\SISTERMI LOCACAO DE MAQUINAS E EQUIPAMENTOS LTDA\FILIAL MG - Adminsitrativo\FINANCEIRO\13 - PROCESSAMENTO FISCAL"
)


def carregar_config() -> Config:
    caminho = ROOT_DIR / "config" / "caminhos.json"
    with caminho.open("r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    return Config(
        base_processamento_fiscal=Path(dados.get("base_processamento_fiscal") or BASE_PROCESSAMENTO_FISCAL),
        usar_data_atual=bool(dados.get("usar_data_atual", True)),
        data_manual=dados.get("data_manual"),
        tesseract_path=dados.get("tesseract_path"),
        limite_texto_minimo_pdf_digital=int(dados.get("limite_texto_minimo_pdf_digital", 150)),
        tolerancia_valor=float(dados.get("tolerancia_valor", 0.05)),
        habilitar_cache=bool(dados.get("habilitar_cache", True)),
        habilitar_watchdog=bool(dados.get("watchdog_enabled", dados.get("habilitar_watchdog", False))),
        watchdog_delay_seconds=max(1, int(dados.get("watchdog_delay_seconds", 30))),
        watchdog_stable_checks=max(1, int(dados.get("watchdog_stable_checks", 3))),
        watchdog_stable_interval_seconds=max(1, int(dados.get("watchdog_stable_interval_seconds", 5))),
        max_workers=max(1, int(dados.get("max_workers", 4))),
        modo_debug=bool(dados.get("modo_debug", False)),
    )
