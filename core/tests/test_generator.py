"""O LLM é redator, não decisor — e o sistema tem que funcionar sem ele.

Os três cenários da validação usam a MESMA intenção e o MESMO roteamento de
propósito: o que muda é só de onde vem o texto. O `routing` idêntico nos três é
a prova de que o Gemini não toca na decisão.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import httpx
import pytest

from app import generator
from app.config import settings
from app.contract import ReplySource
from app.flows import get_intent
from app.generator import generate, render_canonical
from app.routing import resolve

INTENT_ID = "SUPORTE_TECNICO"


@pytest.fixture
def intent():
    intent = get_intent(INTENT_ID)
    assert intent is not None
    return intent


@pytest.fixture
def routing():
    return resolve(intent_id=INTENT_ID)


@pytest.fixture
def sem_chave() -> Iterator[None]:
    original = settings.gemini_api_key
    settings.gemini_api_key = ""
    yield
    settings.gemini_api_key = original


@pytest.fixture
def com_chave() -> Iterator[None]:
    original = settings.gemini_api_key
    settings.gemini_api_key = "chave-de-teste"
    yield
    settings.gemini_api_key = original


def redigir(intent, routing=None) -> tuple[str, ReplySource]:
    """`routing` fica na assinatura só para os testes lerem melhor: o gerador
    não o recebe mais, porque o roteamento deixou de entrar no prompt."""
    return asyncio.run(generate(intent, intent.roteiro))


# ------------------------------------------------------- os três cenários


def test_sem_chave_responde_pelo_template(sem_chave, intent, routing) -> None:
    texto, origem = redigir(intent, routing)
    assert origem is ReplySource.TEMPLATE
    assert texto == render_canonical(intent.roteiro)


def test_sem_chave_nao_chama_a_api(sem_chave, intent, routing, monkeypatch) -> None:
    """Sem credencial o módulo nem tenta — é requisito de avaliação."""

    async def explode(*_a, **_k):
        raise AssertionError("não devia ter chamado a API sem chave")

    monkeypatch.setattr(generator, "_chamar_gemini", explode)
    assert redigir(intent, routing)[1] is ReplySource.TEMPLATE


def test_timeout_cai_no_template(com_chave, intent, routing, monkeypatch) -> None:
    async def estoura(*_a, **_k):
        raise httpx.TimeoutException("tempo esgotado")

    monkeypatch.setattr(generator, "_chamar_gemini", estoura)
    texto, origem = redigir(intent, routing)
    assert origem is ReplySource.TEMPLATE
    assert texto == render_canonical(intent.roteiro)


def test_api_respondendo_gera_texto(com_chave, intent, routing, monkeypatch) -> None:
    async def responde(*_a, **_k):
        return "Sua internet está instável. Vou abrir uma verificação remota agora."

    monkeypatch.setattr(generator, "_chamar_gemini", responde)
    texto, origem = redigir(intent, routing)
    assert origem is ReplySource.GENERATIVE
    assert texto.startswith("Sua internet")


def test_routing_e_identico_nos_tres_cenarios(intent, monkeypatch) -> None:
    """O texto muda; a decisão de destino, nunca."""
    resultados = []

    async def responde(*_a, **_k):
        return "Texto reescrito pelo modelo."

    for chave, falso in [("", None), ("k", "timeout"), ("k", "ok")]:
        settings.gemini_api_key = chave
        if falso == "timeout":

            async def estoura(*_a, **_k):
                raise httpx.ConnectError("sem rede")

            monkeypatch.setattr(generator, "_chamar_gemini", estoura)
        elif falso == "ok":
            monkeypatch.setattr(generator, "_chamar_gemini", responde)

        routing = resolve(intent_id=INTENT_ID)
        _, origem = asyncio.run(generate(intent, intent.roteiro))
        resultados.append((routing.destination, routing.label, routing.url, origem))

    settings.gemini_api_key = ""
    destinos = {(d, lb, u) for d, lb, u, _ in resultados}
    assert len(destinos) == 1, f"o roteamento variou: {destinos}"
    assert [o for *_, o in resultados] == [
        ReplySource.TEMPLATE,
        ReplySource.TEMPLATE,
        ReplySource.GENERATIVE,
    ]


# ------------------------------------------------ ancoragem: nada inventado


@pytest.mark.parametrize(
    "alucinacao",
    [
        "Acesse https://www.claro.com.br/promocao-inventada para resolver.",
        "Seu protocolo é CLR-2026-99999, guarde com você.",
        "Veja em http://site-que-nao-demos.com.br o passo a passo.",
    ],
)
def test_texto_com_dado_inventado_e_descartado(
    com_chave, intent, routing, monkeypatch, alucinacao: str
) -> None:
    """Rede de segurança da regra 1: URL ou protocolo que não demos derruba a saída."""

    async def alucina(*_a, **_k):
        return alucinacao

    monkeypatch.setattr(generator, "_chamar_gemini", alucina)
    texto, origem = redigir(intent, routing)
    assert origem is ReplySource.TEMPLATE
    assert texto == render_canonical(intent.roteiro)


def test_ate_a_url_correta_e_recusada(com_chave, intent, routing, monkeypatch) -> None:
    """O roteamento não entra no prompt, então o texto não deve citá-lo.

    A interface mostra endereço e protocolo ao lado da resposta. Repetir na
    prosa polui, e — como o modelo não recebeu esse dado — significa que ele
    inventou, ainda que por acaso tenha acertado.
    """
    assert routing.url is not None

    async def responde(*_a, **_k):
        return f"Vou te encaminhar. Acesse {routing.url} para acompanhar."

    monkeypatch.setattr(generator, "_chamar_gemini", responde)
    assert redigir(intent, routing)[1] is ReplySource.TEMPLATE


@pytest.mark.parametrize(
    "vazamento",
    [
        "Destino: Diagnostico Tecnico\nVou te ajudar.",
        "Resumo: vou abrir um chamado para você.",
        "Protocolo: guarde este número.",
    ],
)
def test_estrutura_do_prompt_vazando_e_recusada(
    com_chave, intent, routing, monkeypatch, vazamento: str
) -> None:
    """O roteiro chega rotulado para o modelo se orientar; a pessoa não vê isso."""

    async def responde(*_a, **_k):
        return vazamento

    monkeypatch.setattr(generator, "_chamar_gemini", responde)
    assert redigir(intent, routing)[1] is ReplySource.TEMPLATE


def test_prosa_limpa_passa(com_chave, intent, routing, monkeypatch) -> None:
    async def responde(*_a, **_k):
        return (
            "Eu entendo que você está com um problema de conexão.\n"
            "Vou iniciar uma verificação remota agora mesmo.\n"
            "Deseja que eu abra o chamado?"
        )

    monkeypatch.setattr(generator, "_chamar_gemini", responde)
    assert redigir(intent, routing)[1] is ReplySource.GENERATIVE


def test_resposta_vazia_cai_no_template(
    com_chave, intent, routing, monkeypatch
) -> None:
    async def vazio(*_a, **_k):
        return None

    monkeypatch.setattr(generator, "_chamar_gemini", vazio)
    assert redigir(intent, routing)[1] is ReplySource.TEMPLATE


def test_erro_http_cai_no_template(com_chave, intent, routing, monkeypatch) -> None:
    async def erro(*_a, **_k):
        raise httpx.HTTPStatusError(
            "429",
            request=httpx.Request("POST", "http://x"),
            response=httpx.Response(429),
        )

    monkeypatch.setattr(generator, "_chamar_gemini", erro)
    assert redigir(intent, routing)[1] is ReplySource.TEMPLATE


def test_instrucao_proibe_inventar_e_limita_o_tamanho() -> None:
    instrucao = generator.INSTRUCAO_DE_SISTEMA.format(max_linhas=generator.MAX_LINHAS)
    for exigencia in [
        "Nunca invente",  # nada de passo, URL, valor, prazo ou protocolo
        "NUNCA use rótulos",  # a estrutura do roteiro não pode vazar
        "NUNCA escreva endereço",  # a interface já mostra endereço e protocolo
        f"{generator.MAX_LINHAS} linhas",  # limite de tamanho
        "login",  # não prometer o que exige autenticação
    ]:
        assert exigencia in instrucao, f"a instrução perdeu a exigência {exigencia!r}"
