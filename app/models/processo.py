from dataclasses import dataclass, field
from decimal import Decimal

from .documento import DocumentoFiscal


@dataclass
class ProcessoFiscal:
    id: str
    documentos: list[DocumentoFiscal]
    fornecedor: str | None = None
    cnpj: str | None = None
    status: str = "PENDENTE"
    erros: list[str] = field(default_factory=list)
    valor_nf: Decimal | None = None
    valor_pedido: Decimal | None = None
    valor_boleto: Decimal | None = None
