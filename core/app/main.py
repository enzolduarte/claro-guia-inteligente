from __future__ import annotations

import random
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from fastapi import FastAPI

from .classifier import classify
from .embeddings import load_model
from .contract import (
    ConfidenceBand,
    InterpretRequest,
    InterpretResponse,
    ReplySource,
    Routing,
    State,
)
from .flows import (
    Destination,
    Script,
    get_config,
    get_destination,
    get_flows,
    get_intent,
    init_flows,
)

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # flows.json inválido derruba o boot de propósito: erro de base de
    # conhecimento aparece no deploy, não no atendimento.
    init_flows()
    # Modelo de embeddings e matriz do catálogo: uma vez só, aqui.
    load_model()
    yield


app = FastAPI(title="Claro Guia Inteligente — Core", version=VERSION, lifespan=lifespan)


def _protocol(prefix: str) -> str:
    """M4 move isto para routing.py junto com o resto do motor de roteamento."""
    return f"{prefix}-{datetime.now(timezone.utc).year}-{random.randint(10000, 99999)}"


def _render_script(script: Script) -> str:
    """Texto canônico do roteiro. M5 passa isto ao Gemini para reescrever no tom."""
    steps = "\n".join(f"{i}. {step}" for i, step in enumerate(script.passos, 1))
    return f"{script.reconhecimento} {script.resumo}\n\n{steps}\n\n{script.fechamento}"


def _build_routing(destination_id: str, destination: Destination) -> Routing:
    return Routing(
        destination=destination_id,
        label=destination.label,
        url=destination.url,
        protocol=(
            _protocol(destination.prefixo_protocolo)
            if destination.gera_protocolo and destination.prefixo_protocolo
            else None
        ),
    )


@app.get("/health")
def health() -> dict[str, Any]:
    flows = get_flows()
    return {
        "status": "ok",
        "version": VERSION,
        "flows_version": flows.versao,
        "intents_loaded": len(flows.intencoes),
    }


@app.post("/v1/interpret", response_model=InterpretResponse)
def interpret(payload: InterpretRequest) -> InterpretResponse:
    # `def`, não `async def`: o trabalho é CPU-bound (normalização e regex, e no
    # M3 o encode do embedding). O FastAPI roda em threadpool e o event loop
    # segue livre. Trocar para async derruba a latência sob concorrência.
    started = time.perf_counter()
    config = get_config()
    result = classify(payload.text)

    def elapsed_ms() -> int:
        return int((time.perf_counter() - started) * 1000)

    # TRAVA PROVISÓRIA — o M4 remove isto ao implementar CLARIFICANDO.
    # A etapa 3c do CLAUDE.md diz que banda MÉDIA pede confirmação, não roteia.
    # Sem a máquina de estados não há como pedir confirmação, e rotear assim
    # mesmo manda mensagem vaga para escalação humana com protocolo aberto
    # ("oi" pontua 0,68 contra COBRANCA_INDEVIDA). Até lá, banda média cai na
    # pergunta aberta: perde alguns acertos, não inventa nenhum atendimento.
    aguarda_clarificacao = result.band is ConfidenceBand.MEDIO

    if result.intent is None or aguarda_clarificacao:
        fallback = config.resposta_nao_identificada
        suggestions = "\n".join(f"• {item}" for item in fallback.sugestoes)
        return InterpretResponse(
            session_id=payload.session_id,
            state=State(fallback.estado),
            intent=None,
            confidence=result.confidence,
            confidence_band=result.band,
            confidence_source=result.source,
            reply=(
                f"{fallback.texto}\n\n{suggestions}" if suggestions else fallback.texto
            ),
            reply_source=ReplySource.FALLBACK,
            options=None,
            routing=None,
            latency_ms=elapsed_ms(),
        )

    intent = get_intent(result.intent)
    assert intent is not None  # o boot já validou que toda intenção existe

    # Catálogo fechado: sem destino mapeado, cai no padrão. Nunca inferir.
    destination_id = intent.destino
    destination = get_destination(destination_id)
    if destination is None:
        destination_id = config.destino_padrao
        destination = get_destination(destination_id)
        assert destination is not None  # validado no boot

    return InterpretResponse(
        session_id=payload.session_id,
        state=State.ESCALANDO if result.is_sensitive else State.ROTEANDO,
        intent=result.intent,
        confidence=result.confidence,
        confidence_band=result.band,
        confidence_source=result.source,
        reply=_render_script(intent.roteiro),
        reply_source=ReplySource.TEMPLATE,
        options=None,
        routing=_build_routing(destination_id, destination),
        latency_ms=elapsed_ms(),
    )
