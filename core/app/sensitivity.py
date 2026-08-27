"""Etapa 1 do pipeline — verificador de sensibilidade.

Roda ANTES do classificador: assunto sensível nunca chega à IA. Cobre apenas
intenções marcadas com "sensivel": true no flows.json.

Duas famílias de regra, ambas vindas do flows.json:

- `regras` disparam sozinhas. São termos que só existem em contestação de
  cobrança (estorno, procon), então o risco de erro é baixo e a barreira
  precisa ser larga.
- `regras_condicionais` só disparam acompanhadas de uma palavra do universo
  de cobrança. São termos ambíguos: "nao contratei" abre uma contestação, mas
  também descreve um prospect que ainda não é cliente.

Os padrões são compilados uma vez, no import do módulo. Nada de re.compile
dentro da função — ela roda em todo request.
"""

from __future__ import annotations

import re

from .flows import get_flows
from .normalize import normalize

# (padrão, id da intenção), da regra mais longa para a mais curta.
_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = ()

# (padrão do termo, padrão de contexto, id da intenção). O termo só vale se o
# contexto também casar na mesma mensagem.
_CONDITIONAL: tuple[tuple[re.Pattern[str], re.Pattern[str], str], ...] = ()


def _compile_rule(rule: str) -> re.Pattern[str]:
    # A regra vem do flows.json e o texto chega normalizado; normalizar os dois
    # lados é o que faz 'não contratei' e 'nao contratei' colapsarem.
    # \b evita que 'estorno' case dentro de outra palavra.
    return re.compile(rf"\b{re.escape(normalize(rule))}\b")


def _compile_alternatives(terms: list[str]) -> re.Pattern[str]:
    """Um único padrão alternado: uma passada pelo texto em vez de N."""
    parts = sorted({re.escape(normalize(term)) for term in terms if normalize(term)})
    return re.compile(rf"\b(?:{'|'.join(parts)})\b")


def _build() -> None:
    global _PATTERNS, _CONDITIONAL

    plain: list[tuple[str, re.Pattern[str], str]] = []
    conditional: list[tuple[re.Pattern[str], re.Pattern[str], str]] = []

    for intent in get_flows().intencoes:
        if not intent.sensivel:
            continue

        for rule in intent.regras:
            normalized = normalize(rule)
            if normalized:
                plain.append((normalized, _compile_rule(rule), intent.id))

        conditional_rules = intent.regras_condicionais
        if conditional_rules is None or not conditional_rules.exige_contexto:
            continue

        context = _compile_alternatives(conditional_rules.exige_contexto)
        for term in conditional_rules.termos:
            if normalize(term):
                conditional.append((_compile_rule(term), context, intent.id))

    # Mais longa primeiro: o primeiro acerto já é o mais específico.
    plain.sort(key=lambda item: len(item[0]), reverse=True)
    _PATTERNS = tuple((pattern, intent_id) for _, pattern, intent_id in plain)
    _CONDITIONAL = tuple(conditional)


_build()


def check_sensitive(texto_normalizado: str) -> str | None:
    """Devolve o id da intenção sensível, ou None. Espera texto já normalizado."""
    for pattern, intent_id in _PATTERNS:
        if pattern.search(texto_normalizado):
            return intent_id

    for term, context, intent_id in _CONDITIONAL:
        if term.search(texto_normalizado) and context.search(texto_normalizado):
            return intent_id

    return None
