"""Etapa 2 do pipeline — regras de alta precisão.

Palavra-chave literal do flows.json. Alta precisão, recall baixo de propósito:
o que não bate aqui cai para os embeddings na etapa 3. Só intenções NÃO
sensíveis — as sensíveis já foram resolvidas na etapa 1.

Padrões compilados no import, nunca dentro da função.
"""

from __future__ import annotations

import re

from .flows import get_flows
from .normalize import normalize

RULE_CONFIDENCE = 0.97

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = ()


def _build_patterns() -> tuple[tuple[re.Pattern[str], str], ...]:
    compiled: list[tuple[str, re.Pattern[str], str]] = []
    seen: set[str] = set()

    for intent in get_flows().intencoes:
        if intent.sensivel:
            continue
        for rule in intent.regras:
            normalized = normalize(rule)
            # 'código de barras' e 'codigo de barras' colapsam no mesmo padrão
            # depois de normalizados; compilar as duas seria trabalho repetido.
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            pattern = re.compile(rf"\b{re.escape(normalized)}\b")
            compiled.append((normalized, pattern, intent.id))

    # Regra mais longa primeiro: em empate de match, vence a mais específica.
    compiled.sort(key=lambda item: len(item[0]), reverse=True)
    return tuple((pattern, intent_id) for _, pattern, intent_id in compiled)


_PATTERNS = _build_patterns()


def match_rules(texto_normalizado: str) -> tuple[str, float] | None:
    """(intent_id, 0.97) no primeiro acerto, ou None. Espera texto normalizado."""
    for pattern, intent_id in _PATTERNS:
        if pattern.search(texto_normalizado):
            return intent_id, RULE_CONFIDENCE
    return None
