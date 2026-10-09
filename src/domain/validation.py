"""Validação de dados de entrada e filtros."""
import re
from typing import Optional


def is_valid_cnpj(cnpj: Optional[str]) -> bool:
    """Valida se uma string possui formato numérico compatível com CNPJ (14 dígitos)."""
    if not cnpj:
        return False
    digits = re.sub(r"\D", "", cnpj)
    return len(digits) == 14


def is_valid_ibge_code(ibge: Optional[str]) -> bool:
    """Valida se o código IBGE municipal possui 7 dígitos numéricos."""
    if not ibge:
        return False
    digits = re.sub(r"\D", "", str(ibge))
    return len(digits) in (6, 7)


def is_valid_uf(uf: Optional[str]) -> bool:
    """Valida se a sigla de UF pertence a uma das 27 UFs brasileiras."""
    if not uf:
        return False
    valid_ufs = {
        "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
        "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
        "RS", "RO", "RR", "SC", "SP", "SE", "TO"
    }
    return uf.strip().upper() in valid_ufs


def parse_currency_input(text):
    """Aceita moeda brasileira e decimal simples; rejeita conteúdo inválido."""
    import math
    text=text.strip()
    if not text: return None
    if not re.fullmatch(r"[0-9.,]+",text): raise ValueError('Valor inválido. Exemplo: 1.250,50.')
    if ',' in text:
        if not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+),[0-9]{1,2}",text): raise ValueError('Valor inválido. Exemplo: 1.250,50.')
        text=text.replace('.','').replace(',','.')
    elif re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{3})+",text): text=text.replace('.','')
    value=float(text)
    if not math.isfinite(value): raise ValueError('Valor deve ser finito.')
    return value
