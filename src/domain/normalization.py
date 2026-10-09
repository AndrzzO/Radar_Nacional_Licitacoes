"""Normalização de dados, limpeza textual e formatação."""
import re
import unicodedata
from typing import Optional


def normalize_text_search(text: Optional[str]) -> str:
    """
    Normaliza texto para pesquisa insensível a maiúsculas e sem acentos,
    sem alterar o texto original exibido ou persistido.
    """
    if not text:
        return ""
    # Decompõe acentos e converte para minúsculas
    nfkd = unicodedata.normalize("NFKD", text)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento.strip().lower())


def format_cnpj(cnpj: Optional[str]) -> str:
    """Formata CNPJ no padrão 00.000.000/0000-00 se tiver 14 dígitos."""
    if not cnpj:
        return ""
    digits = re.sub(r"\D", "", cnpj)
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    return cnpj


def clean_digits(val: Optional[str]) -> str:
    """Extrai apenas dígitos de uma string."""
    if not val:
        return ""
    return re.sub(r"\D", "", val)


def format_currency_br(val: Optional[float]) -> str:
    """Formata valor em formato de moeda brasileira (R$ 1.234,56) ou '-' se ausente."""
    if val is None:
        return "-"
    # Formatação com separadores brasileiros
    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
