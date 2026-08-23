"""Contrato público da API — espelha a seção 3 do CLAUDE.md. CONGELADO.

`options` e `routing` são opcionais em valor, nunca em presença: os modelos
declaram default `None`, e o `model_dump()` do Pydantic v2 inclui todo campo
declarado. As chaves saem como `null` quando não se aplicam — nunca omitidas.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class State(str, Enum):
    AGUARDANDO = "AGUARDANDO"
    PROCESSANDO = "PROCESSANDO"
    CLARIFICANDO = "CLARIFICANDO"
    RESPONDENDO = "RESPONDENDO"
    ROTEANDO = "ROTEANDO"
    ESCALANDO = "ESCALANDO"
    ENCERRADO = "ENCERRADO"


class ConfidenceBand(str, Enum):
    ALTO = "ALTO"
    MEDIO = "MEDIO"
    BAIXO = "BAIXO"


class ConfidenceSource(str, Enum):
    REGRA = "regra"
    EMBEDDING = "embedding"
    NENHUMA = "nenhuma"


class ReplySource(str, Enum):
    GENERATIVE = "generative"
    TEMPLATE = "template"
    FALLBACK = "fallback"


class Channel(str, Enum):
    WEB = "web"
    TELEGRAM = "telegram"


class InterpretRequest(BaseModel):
    session_id: str
    channel: Channel
    text: str


class Option(BaseModel):
    id: str
    label: str


class Routing(BaseModel):
    destination: str
    label: str
    url: str | None = None
    protocol: str | None = None


class InterpretResponse(BaseModel):
    session_id: str
    state: State
    intent: str | None = None
    confidence: float
    confidence_band: ConfidenceBand
    confidence_source: ConfidenceSource
    reply: str
    reply_source: ReplySource
    options: list[Option] | None = None
    routing: Routing | None = None
    latency_ms: int
