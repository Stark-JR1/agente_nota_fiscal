from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ResultadoProcessamento:
    pasta_entrada: Path
    total_pdfs: int
    processos: list[dict] = field(default_factory=list)
    relatorio_xlsx: Path | None = None
    relatorio_pendencias: Path | None = None
    relatorio_txt: Path | None = None
    dry_run: bool = False
