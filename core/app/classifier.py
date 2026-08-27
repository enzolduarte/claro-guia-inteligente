"""Orquestra o pipeline de classificação: sensibilidade → regras → embeddings.

`classify` é uma função pura: sem I/O, sem log, sem banco. Ela lê o catálogo já
carregado em memória e devolve um resultado — quem persiste ou responde é outro.
É isso que permite reusá-la no fallback e testá-la sem subir a aplicação.

A cascata completa é: sensibilidade → regras → embeddings → banda.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import embeddings
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

    scored = embeddings.score(texto)
    if scored is None:
        # Sem modelo carregado: degrada para as camadas determinísticas.
        return ClassificationResult(
            intent=None,
            confidence=0.0,
            band=ConfidenceBand.BAIXO,
            source=ConfidenceSource.NENHUMA,
            is_sensitive=False,
        )

    intent_id, similarity = scored
    band = band_for(similarity)

    # Etapa 3a do CLAUDE.md: banda BAIXA não identifica intenção, dispara a
    # pergunta aberta. O score é preservado para a telemetria enxergar quão
    # perto ficou.
    if band is ConfidenceBand.BAIXO:
        return ClassificationResult(
            intent=None,
            confidence=similarity,
            band=band,
            source=ConfidenceSource.EMBEDDING,
            is_sensitive=False,
        )

    return ClassificationResult(
        intent=intent_id,
        confidence=similarity,
        band=band,
        source=ConfidenceSource.EMBEDDING,
        is_sensitive=False,
    )
