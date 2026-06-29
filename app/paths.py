from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .config import Config
from .utils import ensure_dir

MESES_PT = {
    1: "01-JANEIRO",
    2: "02-FEVEREIRO",
    3: "03-MARCO",
    4: "04-ABRIL",
    5: "05-MAIO",
    6: "06-JUNHO",
    7: "07-JULHO",
    8: "08-AGOSTO",
    9: "09-SETEMBRO",
    10: "10-OUTUBRO",
    11: "11-NOVEMBRO",
    12: "12-DEZEMBRO",
}

@dataclass(frozen=True)
class PastasDia:
    data: date
    base: Path
    processo_dia: Path
    entrada: Path
    processados: Path
    completos: Path
    pendencias_dia: Path
    assinados: Path
    pendencias_geral: Path
    relatorios: Path
    logs: Path
    config: Path

def obter_data_execucao(config: Config) -> date:
    if config.usar_data_atual:
        return date.today()
    if not config.data_manual:
        raise ValueError("data_manual deve ser preenchida quando usar_data_atual=false")
    return datetime.strptime(config.data_manual, "%d/%m/%Y").date()


def get_ano_atual(data_ref: date | None = None) -> str:
    data_ref = data_ref or date.today()
    return str(data_ref.year)


def get_mes_atual_formatado(data_ref: date | None = None) -> str:
    data_ref = data_ref or date.today()
    return MESES_PT[data_ref.month]


def get_dia_atual_formatado(data_ref: date | None = None) -> str:
    data_ref = data_ref or date.today()
    return data_ref.strftime("%d-%m-%Y")


def obter_caminhos_do_dia(base_path: str | Path, data: datetime | date | None = None) -> dict[str, Path]:
    if data is None:
        data_ref = date.today()
    elif isinstance(data, datetime):
        data_ref = data.date()
    else:
        data_ref = data

    ano = get_ano_atual(data_ref)
    mes = get_mes_atual_formatado(data_ref)
    dia = get_dia_atual_formatado(data_ref)

    base = Path(base_path)
    processo_dia = base / "PROCESSOS" / ano / mes / dia
    caminhos = {
        "base": base,
        "processo_dia": processo_dia,
        "entrada": processo_dia / "ENTRADA",
        "processados": processo_dia / "PROCESSADOS",
        "completos": processo_dia / "COMPLETOS",
        "pendencias_dia": processo_dia / "PENDENCIAS",
        "assinados": base / "ASSINADOS" / ano / mes / dia,
        "pendencias_geral": base / "PENDENCIAS" / ano / mes / dia,
        "relatorios": base / "RELATORIOS" / ano / mes / dia,
        "logs": base / "LOGS",
        "config": base / "CONFIG",
    }
    for caminho in caminhos.values():
        ensure_dir(caminho)
    return caminhos


def pasta_data(base: Path, nome_pasta: str, data_ref: date) -> Path:
    ano = str(data_ref.year)
    mes = MESES_PT[data_ref.month]
    dia = data_ref.strftime("%d-%m-%Y")
    return base / nome_pasta / ano / mes / dia

def montar_pastas(config: Config) -> PastasDia:
    data_ref = obter_data_execucao(config)
    caminhos = obter_caminhos_do_dia(config.base_processamento_fiscal, data_ref)
    return PastasDia(
        data=data_ref,
        base=caminhos["base"],
        processo_dia=caminhos["processo_dia"],
        entrada=caminhos["entrada"],
        processados=caminhos["processados"],
        completos=caminhos["completos"],
        pendencias_dia=caminhos["pendencias_dia"],
        assinados=caminhos["assinados"],
        pendencias_geral=caminhos["pendencias_geral"],
        relatorios=caminhos["relatorios"],
        logs=caminhos["logs"],
        config=caminhos["config"],
    )
