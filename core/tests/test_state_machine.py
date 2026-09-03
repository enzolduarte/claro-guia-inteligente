"""Conversas de vários turnos, exercitadas pelo endpoint de verdade.

Estes testes usam o TestClient em vez de chamar as funções soltas porque o que
se quer verificar é justamente a costura: sessão, transição de estado e resposta
saindo coerentes juntos.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.contract import State
from app.main import app
from app.state_machine import (
    MAX_TENTATIVAS_CLARIFICACAO,
    STORE,
    InvalidTransition,
    Session,
    SessionStore,
    TRANSICOES,
)


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(app) as cliente:  # o `with` dispara o lifespan
        yield cliente


@pytest.fixture(autouse=True)
def sessao_limpa() -> Iterator[None]:
    STORE.limpar()
    yield
    STORE.limpar()


def falar(client: TestClient, texto: str, sessao: str = "web:t") -> dict:
    resposta = client.post(
        "/v1/interpret",
        json={"session_id": sessao, "channel": "web", "text": texto},
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


# ---------------------------------------------------------------- transições


def test_tabela_cobre_os_sete_estados() -> None:
    assert set(TRANSICOES) == set(State)


def test_transicao_fora_da_tabela_levanta_excecao() -> None:
    """É bug de código, não entrada de usuário — por isso explode."""
    loja = SessionStore()
    sessao = loja.get("web:x")
    assert sessao.state is State.AGUARDANDO
    with pytest.raises(InvalidTransition, match="AGUARDANDO -> ROTEANDO"):
        loja.transicionar(sessao, State.ROTEANDO)


def test_sessao_expira_por_tempo() -> None:
    from datetime import timedelta

    loja = SessionStore(ttl=timedelta(seconds=0))
    loja.get("web:velha")
    assert len(loja) == 1
    loja.get("web:nova")  # a leitura é que varre
    assert "web:velha" not in loja._sessions


def test_sessoes_diferentes_nao_se_misturam(client: TestClient) -> None:
    falar(client, "quero mudar meu plano", sessao="web:a")
    assert STORE.get("web:a").state is State.CLARIFICANDO
    assert STORE.get("web:b").state is State.AGUARDANDO


def test_historico_guarda_no_maximo_seis_turnos(client: TestClient) -> None:
    for i in range(8):
        falar(client, f"minha internet caiu {i}", sessao="web:h")
    assert len(STORE.get("web:h").history) == 6


# ------------------------------------------------- clarificação por opções


def test_plano_sempre_clarifica_com_tres_opcoes(client: TestClient) -> None:
    """PLANO tem sempre_clarificar: clarifica mesmo batendo em regra, com 0,97."""
    corpo = falar(client, "quero mudar meu plano")
    assert corpo["state"] == "CLARIFICANDO"
    assert corpo["intent"] == "PLANO"
    assert [o["id"] for o in corpo["options"]] == ["upgrade", "economia", "catalogo"]
    assert corpo["routing"] is None


def test_conversa_completa_plano_para_upgrade(client: TestClient) -> None:
    falar(client, "quero mudar meu plano")
    corpo = falar(client, "quero um plano maior")
    assert corpo["state"] == "ROTEANDO"
    assert corpo["routing"]["destination"] == "FLUXO_COMERCIAL_UPGRADE"
    assert corpo["options"] is None


@pytest.mark.parametrize(
    "resposta,destino",
    [
        ("quero pagar menos", "FLUXO_COMERCIAL_ECONOMIA"),
        ("me mostra as opcoes", "FLUXO_COMERCIAL_CATALOGO"),
        ("2", "FLUXO_COMERCIAL_ECONOMIA"),
        ("upgrade", "FLUXO_COMERCIAL_UPGRADE"),
    ],
)
def test_escolha_resolve_por_texto_numero_ou_id(
    client: TestClient, resposta: str, destino: str
) -> None:
    falar(client, "quero mudar meu plano")
    corpo = falar(client, resposta)
    assert corpo["state"] == "ROTEANDO"
    assert corpo["routing"]["destination"] == destino


def test_sessao_volta_ao_inicio_depois_de_rotear(client: TestClient) -> None:
    """A sessão descansa em ROTEANDO e só volta a AGUARDANDO no turno seguinte.

    Guardar o estado terminal é de propósito: a sessão registra o que de fato
    aconteceu, e a telemetria do M7 vai querer ler isso. Quem devolve a
    AGUARDANDO é o `assentar`, na chegada da próxima mensagem.
    """
    falar(client, "quero mudar meu plano")
    falar(client, "quero um plano maior")
    sessao = STORE.get("web:t")
    assert sessao.state is State.ROTEANDO
    assert sessao.pending_intent is None
    assert sessao.offered_options == []

    # O turno seguinte parte do zero, sem arrastar a clarificação anterior.
    corpo = falar(client, "minha internet ta caindo toda hora")
    assert corpo["state"] == "ROTEANDO"
    assert corpo["intent"] == "SUPORTE_TECNICO"
    assert corpo["routing"]["destination"] == "FLUXO_SUPORTE_TECNICO"


# -------------------------------------------------- confirmação sim/não


def frase_de_banda_media(client: TestClient) -> str:
    """Uma frase que cai em MEDIO hoje. Se a calibragem mudar, o teste avisa."""
    return "tenho uma duvida"


def test_banda_media_pede_confirmacao(client: TestClient) -> None:
    corpo = falar(client, frase_de_banda_media(client))
    assert corpo["state"] == "CLARIFICANDO", f"veio {corpo['confidence']:.3f}"
    assert corpo["confidence_band"] == "MEDIO"
    assert [o["id"] for o in corpo["options"]] == ["sim", "nao"]


def test_confirmacao_sim_encaminha(client: TestClient) -> None:
    primeiro = falar(client, frase_de_banda_media(client))
    corpo = falar(client, "sim")
    assert corpo["intent"] == primeiro["intent"]
    assert corpo["routing"] is not None
    assert corpo["confidence_band"] == "ALTO", "escolha de lista fechada não é palpite"


def test_confirmar_intencao_sensivel_reporta_escalando(client: TestClient) -> None:
    """O mesmo desfecho tem que ter o mesmo estado pelos dois caminhos."""
    direto = falar(client, "fui cobrado por algo que nao contratei", sessao="web:d")
    falar(client, "tenho uma duvida", sessao="web:c")
    confirmado = falar(client, "sim", sessao="web:c")

    assert direto["intent"] == confirmado["intent"] == "COBRANCA_INDEVIDA"
    assert direto["routing"]["destination"] == confirmado["routing"]["destination"]
    assert direto["state"] == confirmado["state"] == "ESCALANDO"


def test_confirmacao_nao_promete_nada_antes_de_confirmar(client: TestClient) -> None:
    """O texto não pode afirmar o problema que ainda é só um palpite."""
    corpo = falar(client, frase_de_banda_media(client))
    assert "lamento" not in corpo["reply"].lower()
    assert corpo["reply"].endswith("?")


def test_confirmacao_nao_volta_para_pergunta_aberta(client: TestClient) -> None:
    falar(client, frase_de_banda_media(client))
    corpo = falar(client, "nao")
    assert corpo["state"] == "AGUARDANDO"
    assert corpo["intent"] is None
    assert corpo["routing"] is None


# ------------------------------------------------------ falha de resolução


def test_duas_falhas_levam_a_atendimento_humano(client: TestClient) -> None:
    falar(client, "quero mudar meu plano")

    primeira = falar(client, "xyzabc")
    assert primeira["state"] == "CLARIFICANDO", "a primeira falha repete as opções"
    assert primeira["options"] is not None

    segunda = falar(client, "xyzabc")
    assert segunda["state"] == "ROTEANDO"
    assert segunda["routing"]["destination"] == "ATENDIMENTO_HUMANO"
    assert segunda["routing"]["protocol"].startswith("CLR-ATD-")
    assert STORE.get("web:t").pending_intent is None


def test_limite_de_tentativas_vem_da_constante() -> None:
    assert MAX_TENTATIVAS_CLARIFICACAO == 2


# ------------------------------------------------------------- sensível


def test_contestacao_de_cobranca_escala_sem_clarificar(client: TestClient) -> None:
    corpo = falar(client, "fui cobrado por algo que nao contratei")
    assert corpo["state"] == "ESCALANDO"
    assert corpo["routing"]["destination"] == "ESCALACAO_HUMANA"
    assert corpo["options"] is None


def test_session_id_e_opaco_para_o_nucleo() -> None:
    """O núcleo não interpreta o canal — a string é só uma chave."""
    sessao = Session(session_id="qualquercoisa-sem-dois-pontos")
    assert sessao.state is State.AGUARDANDO


# ------------------------------------------ regressão: ruído não é escolha


@pytest.mark.parametrize(
    "ruido", ["ola", "oi", "obrigado", "talvez", "hmm", "certo", "bom dia", "xyzabc"]
)
def test_cumprimento_nao_conta_como_escolha(client: TestClient, ruido: str) -> None:
    """Bug encontrado em 30/08/2026 numa conversa real.

    Quem digitava "ola" durante a clarificação do PLANO tinha o destino
    "catálogo" escolhido em seu nome, com confiança 1,00. A similaridade sozinha
    aceitava qualquer texto curto (0,665 para "ola", 0,704 para "obrigado").
    Agora é preciso score alto E margem clara sobre a segunda opção.
    """
    falar(client, "quero mudar meu plano", sessao="web:ruido")
    corpo = falar(client, ruido, sessao="web:ruido")
    assert corpo["state"] == "CLARIFICANDO", f"{ruido!r} virou escolha de destino"
    assert corpo["routing"] is None


@pytest.mark.parametrize(
    "escolha,destino",
    [
        ("quero pagar menos", "FLUXO_COMERCIAL_ECONOMIA"),
        ("mais velocidade", "FLUXO_COMERCIAL_UPGRADE"),
        ("todas as opcoes", "FLUXO_COMERCIAL_CATALOGO"),
    ],
)
def test_escolha_de_verdade_continua_resolvendo(
    client: TestClient, escolha: str, destino: str
) -> None:
    """O aperto no critério não pode ter matado o caso bom."""
    falar(client, "quero mudar meu plano", sessao="web:bom")
    corpo = falar(client, escolha, sessao="web:bom")
    assert corpo["state"] == "ROTEANDO"
    assert corpo["routing"]["destination"] == destino


# --------------------------------- mudança de assunto durante a clarificação


def test_mudar_de_assunto_abandona_a_clarificacao(client: TestClient) -> None:
    """Sessão única, descoberto em 02/09: o cliente não fica preso no menu."""
    falar(client, "tenho uma duvida", sessao="web:troca")  # confirmação pendente
    corpo = falar(client, "quero mudar meu plano", sessao="web:troca")
    assert corpo["intent"] == "PLANO"
    assert corpo["state"] == "CLARIFICANDO"
    assert [o["id"] for o in corpo["options"]] == ["upgrade", "economia", "catalogo"]

    fim = falar(client, "economia", sessao="web:troca")
    assert fim["routing"]["destination"] == "FLUXO_COMERCIAL_ECONOMIA"


def test_contestacao_durante_clarificacao_escala(client: TestClient) -> None:
    """Assunto sensível fura qualquer menu — nunca recebe 'não entendi'."""
    falar(client, "quero mudar meu plano", sessao="web:sens")
    corpo = falar(client, "fui cobrado por algo que nao contratei", sessao="web:sens")
    assert corpo["state"] == "ESCALANDO"
    assert corpo["routing"]["destination"] == "ESCALACAO_HUMANA"


def test_resposta_confusa_ainda_repete_as_opcoes(client: TestClient) -> None:
    """A troca de assunto exige certeza; ruído continua repetindo o menu."""
    falar(client, "quero mudar meu plano", sessao="web:conf")
    corpo = falar(client, "hmm sei la", sessao="web:conf")
    assert corpo["state"] == "CLARIFICANDO"
    assert corpo["intent"] == "PLANO"
