from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI

from .classifier import ClassificationResult, classify
from .contract import (
    ConfidenceBand,
    ConfidenceSource,
    InterpretRequest,
    InterpretResponse,
    Option,
    ReplySource,
    Routing,
    State,
)
from .embeddings import load_model
from .routing import resolve as resolver_destino
from .flows import (
    Intent,
    Script,
    get_config,
    get_flows,
    get_intent,
    init_flows,
)
from .state_machine import (
    MAX_TENTATIVAS_CLARIFICACAO,
    STORE,
    CONFIRMACAO,
    OPCOES,
    Session,
    opcoes_de_clarificacao,
    opcoes_de_confirmacao,
    resolver_escolha,
    texto_da_clarificacao,
    texto_da_confirmacao,
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


def _render_script(script: Script) -> str:
    """Texto canônico do roteiro. M6 passa isto ao Gemini para reescrever no tom."""
    steps = "\n".join(f"{i}. {step}" for i, step in enumerate(script.passos, 1))
    return f"{script.reconhecimento} {script.resumo}\n\n{steps}\n\n{script.fechamento}"


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
    # `def`, não `async def`: o trabalho é CPU-bound (regex e encode do
    # embedding). O FastAPI roda em threadpool e o event loop segue livre.
    started = time.perf_counter()

    def elapsed_ms() -> int:
        return int((time.perf_counter() - started) * 1000)

    sessao = STORE.get(payload.session_id)

    # ETAPA 0 — resposta a uma clarificação em aberto, antes de qualquer
    # classificação. O usuário está respondendo a um menu, não abrindo assunto.
    if sessao.state is State.CLARIFICANDO:
        resposta = _resolver_clarificacao(sessao, payload, elapsed_ms)
        sessao.registrar(payload.text, resposta.intent)
        return resposta

    # Um turno novo parte sempre de AGUARDANDO: a tabela não liga ROTEANDO a
    # PROCESSANDO direto.
    STORE.assentar(sessao)
    STORE.transicionar(sessao, State.PROCESSANDO)

    resultado = classify(payload.text)

    if resultado.intent is None:
        resposta = _pergunta_aberta(sessao, payload, resultado, elapsed_ms)
    else:
        resposta = _decidir_com_intencao(sessao, payload, resultado, elapsed_ms)

    sessao.registrar(payload.text, resposta.intent)
    return resposta


def _decidir_com_intencao(
    sessao: Session,
    payload: InterpretRequest,
    resultado: ClassificationResult,
    elapsed_ms: Any,
) -> InterpretResponse:
    intent = get_intent(resultado.intent or "")
    assert intent is not None  # o boot já validou que toda intenção existe

    if resultado.is_sensitive:
        STORE.transicionar(sessao, State.ESCALANDO)
        return _resposta_de_destino(
            sessao,
            payload,
            intent,
            resolver_destino(intent_id=intent.id),
            resultado,
            elapsed_ms,
        )

    # ETAPA 3b — sempre_clarificar vem ANTES da checagem de banda. A ambiguidade
    # do PLANO é semântica, não de confiança: score 0,95 ainda clarifica.
    if intent.sempre_clarificar:
        return _abrir_clarificacao(
            sessao,
            payload,
            intent,
            resultado,
            opcoes=opcoes_de_clarificacao(intent),
            texto=texto_da_clarificacao(intent, opcoes_de_clarificacao(intent)),
            kind=OPCOES,
            elapsed_ms=elapsed_ms,
        )

    # ETAPA 3c — banda média não roteia: pede confirmação da intenção detectada.
    if resultado.band is ConfidenceBand.MEDIO:
        return _abrir_clarificacao(
            sessao,
            payload,
            intent,
            resultado,
            opcoes=opcoes_de_confirmacao(),
            texto=texto_da_confirmacao(intent),
            kind=CONFIRMACAO,
            elapsed_ms=elapsed_ms,
        )

    STORE.transicionar(sessao, State.RESPONDENDO)
    STORE.transicionar(sessao, State.ROTEANDO)
    return _resposta_de_destino(
        sessao,
        payload,
        intent,
        resolver_destino(intent_id=intent.id),
        resultado,
        elapsed_ms,
    )


def _abrir_clarificacao(
    sessao: Session,
    payload: InterpretRequest,
    intent: Intent,
    resultado: ClassificationResult,
    opcoes: list[Option],
    texto: str,
    kind: str,
    elapsed_ms: Any,
) -> InterpretResponse:
    STORE.transicionar(sessao, State.CLARIFICANDO)
    sessao.abrir_clarificacao(intent.id, opcoes, kind)
    return InterpretResponse(
        session_id=payload.session_id,
        state=State.CLARIFICANDO,
        intent=intent.id,
        confidence=resultado.confidence,
        confidence_band=resultado.band,
        confidence_source=resultado.source,
        reply=texto,
        reply_source=ReplySource.TEMPLATE,
        options=opcoes,
        routing=None,
        latency_ms=elapsed_ms(),
    )


def _resolver_clarificacao(
    sessao: Session, payload: InterpretRequest, elapsed_ms: Any
) -> InterpretResponse:
    intent = get_intent(sessao.pending_intent or "")
    escolhido = resolver_escolha(sessao, payload.text)

    if escolhido is None:
        sessao.clarify_attempts += 1
        if sessao.clarify_attempts >= MAX_TENTATIVAS_CLARIFICACAO:
            # Duas tentativas e nada. Insistir irrita; um humano resolve.
            sessao.fechar_clarificacao()
            STORE.transicionar(sessao, State.ROTEANDO)
            return _resposta_de_atendimento_humano(sessao, payload, elapsed_ms)
        return _repetir_opcoes(sessao, payload, elapsed_ms)

    if sessao.clarification_kind == CONFIRMACAO and escolhido == "nao":
        # Errou o palpite. Volta para a pergunta aberta em vez de tentar de novo.
        sessao.fechar_clarificacao()
        STORE.transicionar(sessao, State.PROCESSANDO)
        vazio = ClassificationResult(
            intent=None,
            confidence=0.0,
            band=ConfidenceBand.BAIXO,
            source=ConfidenceSource.NENHUMA,
            is_sensitive=False,
        )
        return _pergunta_aberta(sessao, payload, vazio, elapsed_ms)

    assert intent is not None
    destino = _destino_da_opcao(intent, escolhido)
    sessao.fechar_clarificacao()

    if intent.sensivel:
        # Mesmo desfecho pelos dois caminhos: confirmar uma contestação de
        # cobrança é ESCALANDO, não ROTEANDO. A tabela não liga CLARIFICANDO a
        # ESCALANDO direto, mas passa por PROCESSANDO — que é honesto, já que
        # houve uma decisão no meio.
        STORE.transicionar(sessao, State.PROCESSANDO)
        STORE.transicionar(sessao, State.ESCALANDO)
    else:
        STORE.transicionar(sessao, State.ROTEANDO)

    resolvido = ClassificationResult(
        intent=intent.id,
        confidence=1.0,
        band=ConfidenceBand.ALTO,
        # O usuário escolheu de uma lista fechada: não é palpite de modelo.
        source=ConfidenceSource.REGRA,
        is_sensitive=intent.sensivel,
    )
    return _resposta_de_destino(
        sessao,
        payload,
        intent,
        resolver_destino(intent_id=intent.id, option_destination=destino),
        resolvido,
        elapsed_ms,
    )


def _destino_da_opcao(intent: Intent, opcao_id: str) -> str:
    if intent.clarificacao is not None:
        for opcao in intent.clarificacao.opcoes:
            if opcao.id == opcao_id:
                return opcao.destino
    # Confirmação sim/não: o destino é o da própria intenção.
    return intent.destino


def _repetir_opcoes(
    sessao: Session, payload: InterpretRequest, elapsed_ms: Any
) -> InterpretResponse:
    """Primeira falha de resolução: mostra as opções de novo, pedindo o número."""
    itens = "\n".join(
        f"{i}. {o.label}" for i, o in enumerate(sessao.offered_options, 1)
    )
    return InterpretResponse(
        session_id=payload.session_id,
        state=State.CLARIFICANDO,
        intent=sessao.pending_intent,
        confidence=0.0,
        confidence_band=ConfidenceBand.BAIXO,
        confidence_source=ConfidenceSource.NENHUMA,
        reply=f"Não consegui entender a escolha. Pode responder pelo número?\n\n{itens}",
        reply_source=ReplySource.FALLBACK,
        options=list(sessao.offered_options),
        routing=None,
        latency_ms=elapsed_ms(),
    )


def _resposta_de_destino(
    sessao: Session,
    payload: InterpretRequest,
    intent: Intent,
    routing: Routing,
    resultado: ClassificationResult,
    elapsed_ms: Any,
) -> InterpretResponse:
    return InterpretResponse(
        session_id=payload.session_id,
        state=sessao.state,
        intent=intent.id,
        confidence=resultado.confidence,
        confidence_band=resultado.band,
        confidence_source=resultado.source,
        reply=_render_script(intent.roteiro),
        reply_source=ReplySource.TEMPLATE,
        options=None,
        routing=routing,
        latency_ms=elapsed_ms(),
    )


def _resposta_de_atendimento_humano(
    sessao: Session, payload: InterpretRequest, elapsed_ms: Any
) -> InterpretResponse:
    return InterpretResponse(
        session_id=payload.session_id,
        state=sessao.state,
        intent=None,
        confidence=0.0,
        confidence_band=ConfidenceBand.BAIXO,
        confidence_source=ConfidenceSource.NENHUMA,
        reply=(
            "Não consegui entender a sua escolha. Vou te encaminhar para um "
            "atendente, que vai poder te ajudar melhor."
        ),
        reply_source=ReplySource.FALLBACK,
        options=None,
        routing=resolver_destino(),
        latency_ms=elapsed_ms(),
    )


def _pergunta_aberta(
    sessao: Session,
    payload: InterpretRequest,
    resultado: ClassificationResult,
    elapsed_ms: Any,
) -> InterpretResponse:
    fallback = get_config().resposta_nao_identificada
    if sessao.state is not State.AGUARDANDO:
        STORE.transicionar(sessao, State.AGUARDANDO)
    sugestoes = "\n".join(f"• {item}" for item in fallback.sugestoes)
    return InterpretResponse(
        session_id=payload.session_id,
        state=State(fallback.estado),
        intent=None,
        confidence=resultado.confidence,
        confidence_band=resultado.band,
        confidence_source=resultado.source,
        reply=f"{fallback.texto}\n\n{sugestoes}" if sugestoes else fallback.texto,
        reply_source=ReplySource.FALLBACK,
        options=None,
        routing=None,
        latency_ms=elapsed_ms(),
    )
