"""Normalização de texto — usada por todas as camadas do classificador.

Regex compilados no import e `lru_cache` na função: normalize() roda em todo
request e as mesmas frases se repetem muito no caminho de teste e demo.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")


@lru_cache(maxsize=1024)
def normalize(texto: str) -> str:
    """minúsculas → sem acento → sem pontuação → espaços colapsados.

    A decomposição é NFKD (compatibilidade), não NFD: é ela que converte
    '2ª via' em '2a via', casando com a regra literal do flows.json.
    """
    decomposed = unicodedata.normalize("NFKD", texto.lower())
    unaccented = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    # Pontuação vira espaço, não vazio: 'conta,veio' não pode virar 'contaveio'.
    spaced = _PUNCTUATION.sub(" ", unaccented)
    return _WHITESPACE.sub(" ", spaced).strip()
