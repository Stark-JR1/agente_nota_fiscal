from dataclasses import dataclass
from decimal import Decimal


@dataclass
class DocumentoFiscal:
    tipo_documento: str
    arquivo_origem: str
    arquivo_nome: str
    pagina: int
    caminho_original: str | None = None
    fornecedor_nome: str | None = None
    fornecedor_cnpj: str | None = None
    sistermi_cnpj: str | None = None
    numero_nf: str | None = None
    numero_pedido: str | None = None
    valor_total: Decimal | None = None
    vencimento: str | None = None
    origem_texto: str = ""
    confianca_extracao: float = 0.0
    texto_extraido: str = ""

    @classmethod
    def from_dict(cls, dados: dict) -> "DocumentoFiscal":
        return cls(**{campo: dados.get(campo) for campo in cls.__dataclass_fields__})
