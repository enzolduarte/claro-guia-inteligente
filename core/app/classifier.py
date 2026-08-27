"""Orquestra o pipeline de classificação: normalize → sensibilidade → regras.

`classify` é uma função pura: sem I/O, sem log, sem banco. Ela lê o catálogo já
carregado em memória e devolve um resultado — quem persiste ou responde é outro.
É isso que permite reusá-la no fallback e testá-la sem subir a aplicação.

Etapa 3 (embeddings) entra no M3, entre `match_rules` e o retorno vazio.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contract import ConfidenceBand, ConfidenceSource
from .flows import get_config
from .normalize import normalize
from .rules import match_rules
from .sensitivity import check_sensitive


@dataclass(frozen=True)
class ClassificationResult:
    intent: str | None
    confidence: float
    band: ConfidenceBand
    source: ConfidenceSource
    is_sensitive: bool


def band_for(confidence: float) -> ConfidenceBand:
    """Faixa de confiança segundo os limiares do flows.json."""
    config = get_config()
    if confidence >= config.limiar_alto:
        return ConfidenceBand.ALTO
    if confidence >= config.limiar_medio:
        return ConfidenceBand.MEDIO
    return ConfidenceBand.BAIXO


def classify(texto: str) -> ClassificationResult:
    normalized = normalize(texto)

    sensitive_intent = check_sensitive(normalized)
    if sensitive_intent is not None:
        return ClassificationResult(
            intent=sensitive_intent,
            confidence=1.0,
            band=ConfidenceBand.ALTO,
            source=ConfidenceSource.REGRA,
            is_sensitive=True,
        )

    matched = match_rules(normalized)
    if matched is not None:
        intent_id, confidence = matched
        return ClassificationResult(
            intent=intent_id,
            confidence=confidence,
            band=band_for(confidence),
            source=ConfidenceSource.REGRA,
            is_sensitive=False,
        )

    # M3: etapa 3 (embeddings) entra aqui. Sem ela, nada mais a tentar.
    return ClassificationResult(
        intent=None,
        confidence=0.0,
        band=ConfidenceBand.BAIXO,
        source=ConfidenceSource.NENHUMA,
        is_sensitive=False,
    )
