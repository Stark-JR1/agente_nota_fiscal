from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path


INVALID_FILENAME_CHARS = r'\/:*?"<>|'


def normalizar_texto(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return texto.upper()


def limpar_espacos(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def sanitizar_nome_arquivo(nome: str, limite: int = 85) -> str:
    for char in INVALID_FILENAME_CHARS:
        nome = nome.replace(char, " ")
    nome = limpar_espacos(nome).strip(". ")
    if len(nome) <= limite:
        return nome or "DOCUMENTO"
    sufixo = ".pdf" if nome.lower().endswith(".pdf") else ""
    corpo = nome[:-4] if sufixo else nome
    return ((corpo[: limite - len(sufixo)].rstrip() + sufixo) or "DOCUMENTO")


def somente_digitos(valor: str | None) -> str:
    return re.sub(r"\D", "", valor or "")


def parse_valor_brl(valor: str | None) -> Decimal | None:
    if not valor:
        return None
    limpo = re.sub(r"[^\d,.-]", "", valor)
    if "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    try:
        return Decimal(limpo)
    except (InvalidOperation, ValueError):
        return None


def formatar_valor_brl(valor: Decimal | float | int | None) -> str:
    if valor is None:
        return "R$ 0,00"
    valor = Decimal(str(valor)).quantize(Decimal("0.01"))
    inteiro, decimal = f"{valor:.2f}".split(".")
    partes = []
    while inteiro:
        partes.append(inteiro[-3:])
        inteiro = inteiro[:-3]
    return f"R$ {'.'.join(reversed(partes))},{decimal}"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def primeiro(*valores):
    for valor in valores:
        if valor not in (None, "", []):
            return valor
    return None
