"""Registro das interações e as métricas que saem dele.

Cada teste usa um banco temporário próprio: telemetria compartilhada entre
testes esconderia exatamente o tipo de erro que estes testes procuram.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import telemetry
from app.main import app
from app.state_machine import STORE
from app.telemetry import Evento

pytestmark = pytest.mark.usefixtures("modelo_carregado")


def evento(**ajustes) -> Evento:
    base = dict(
        session_id="web:t",
        canal="web",
        texto="minha internet caiu",
        intent="SUPORTE_TECNICO",
        confidence=0.9,
        band="ALTO",
        confidence_source="embedding",
        state="ROTEANDO",
        destination="FLUXO_SUPORTE_TECNICO",
        protocol="CLR-2026-00001",
        reply_source="template",
        latency_ms=15,
    )
    return Evento(**{**base, **ajustes})


@pytest.fixture(scope="module")
def cliente() -> Iterator[TestClient]:
    """Um único lifespan para o arquivo — carregar o modelo por teste custa 6s cada."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def banco(tmp_path: Path) -> Iterator[Path]:
    """Banco novo a cada teste, criado DEPOIS do lifespan.

    O lifespan conecta no caminho real de produção; esta fixture é de escopo de
    função, então roda depois dele e reaponta para o temporário. Telemetria
    compartilhada entre testes esconderia justamente os erros que eles procuram.
    """
    destino = tmp_path / "telemetria.db"
    telemetry.conectar(destino)
    STORE.limpar()
    yield destino
    telemetry.fechar()
    STORE.limpar()


def linhas() -> int:
    from app.telemetry import _exigir_conexao

    return _exigir_conexao().execute("SELECT COUNT(*) FROM interacoes").fetchone()[0]


# ------------------------------------------------------------ esquema


def test_boot_cria_tabela_e_indices() -> None:
    from app.telemetry import _exigir_conexao

    conexao = _exigir_conexao()
    nomes = {
        linha[0]
        for linha in conexao.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','index')"
        )
    }
    assert "interacoes" in nomes
    assert "idx_interacoes_ts" in nomes
    assert "idx_interacoes_intent" in nomes


def test_conectar_e_idempotente(banco: Path) -> None:
    telemetry.registrar(evento())
    telemetry.conectar(banco)  # de novo, sobre o mesmo arquivo
    assert linhas() == 1, "reconectar não pode apagar nem duplicar"


def test_horario_e_preenchido_sozinho() -> None:
    telemetry.registrar(evento())
    from app.telemetry import _exigir_conexao

    ts = _exigir_conexao().execute("SELECT ts FROM interacoes").fetchone()[0]
    assert ts and len(ts) >= 19


# ------------------------------------------------- uma chamada, uma linha


def test_uma_chamada_grava_exatamente_uma_linha(cliente: TestClient) -> None:
    assert linhas() == 0
    resposta = cliente.post(
        "/v1/interpret",
        json={"session_id": "web:1", "channel": "web", "text": "minha internet caiu"},
    )
    assert resposta.status_code == 200
    assert linhas() == 1


def test_a_linha_espelha_a_resposta(cliente: TestClient) -> None:
    corpo = cliente.post(
        "/v1/interpret",
        json={
            "session_id": "web:2",
            "channel": "web",
            "text": "quero a 2a via da fatura",
        },
    ).json()
    from app.telemetry import _exigir_conexao

    linha = _exigir_conexao().execute("SELECT * FROM interacoes").fetchone()
    assert linha["intent"] == corpo["intent"]
    assert linha["state"] == corpo["state"]
    assert linha["destination"] == corpo["routing"]["destination"]
    assert linha["canal"] == "web"
    assert (
        linha["simulado"] == 0
    ), "interação real não pode entrar marcada como simulada"


def test_conversa_de_tres_turnos_grava_tres_linhas(cliente: TestClient) -> None:
    for texto in ["quero mudar meu plano", "quero um plano maior", "oi"]:
        cliente.post(
            "/v1/interpret",
            json={"session_id": "web:3", "channel": "web", "text": texto},
        )
    assert linhas() == 3


# ------------------------------------------------------------ métricas


def base_conhecida() -> None:
    """4 escalados de 10 — números redondos para a conta ser conferível."""
    telemetry.registrar_muitos(
        [evento(canal="web", intent="FATURA") for _ in range(4)]
        + [evento(canal="telegram", intent="SUPORTE_TECNICO") for _ in range(2)]
        + [
            evento(
                canal="web",
                intent="COBRANCA_INDEVIDA",
                state="ESCALANDO",
                destination="ESCALACAO_HUMANA",
                simulado=1,
            )
            for _ in range(3)
        ]
        + [
            evento(
                canal="web",
                intent=None,
                state="ROTEANDO",
                destination="ATENDIMENTO_HUMANO",
            )
        ]
    )


def test_metricas_somam_a_base_conhecida() -> None:
    base_conhecida()
    m = telemetry.metricas()

    assert m["total_geral"] == 10
    assert m["simulados"] == 3 and m["reais"] == 7
    # escalados = 3 ESCALANDO + 1 roteado para ATENDIMENTO_HUMANO
    assert m["taxa_escalacao"] == 0.4
    assert m["taxa_resolucao_digital"] == 0.6
    assert m["por_canal"] == {"web": 8, "telegram": 2}
    assert m["por_intencao"]["FATURA"] == 4
    assert m["por_intencao"]["NAO_IDENTIFICADA"] == 1


def test_atendimento_humano_conta_como_escalacao() -> None:
    """Roteado para gente não é resolução digital, mesmo em estado ROTEANDO."""
    telemetry.registrar(evento(state="ROTEANDO", destination="ATENDIMENTO_HUMANO"))
    assert telemetry.metricas()["taxa_escalacao"] == 1.0


def test_metricas_de_base_vazia_nao_dividem_por_zero() -> None:
    m = telemetry.metricas()
    assert m["total_geral"] == 0
    assert m["taxa_resolucao_digital"] == 0.0
    assert m["taxa_escalacao"] == 0.0


def test_endpoint_de_metricas_responde(cliente: TestClient) -> None:
    base_conhecida()
    corpo = cliente.get("/v1/metrics").json()
    assert corpo["total_geral"] == 10
    assert corpo["simulados"] == 3


# ------------------------------------------------------------ latência


def test_gravacao_nao_pesa_no_caminho_da_resposta(cliente: TestClient) -> None:
    """A tarefa de fundo roda depois da resposta — o cliente não espera o disco.

    Compara a latência que o próprio serviço mede com a telemetria ligada
    contra a mesma medida sem conexão aberta. O teto é 5 ms.
    """
    texto = {"session_id": "web:l", "channel": "web", "text": "minha internet caiu"}

    def medir() -> float:
        amostras = []
        for _ in range(12):
            corpo = cliente.post("/v1/interpret", json=texto).json()
            amostras.append(corpo["latency_ms"])
        return statistics.median(amostras)

    com = medir()
    telemetry.fechar()
    sem = medir()

    assert com - sem <= 5, f"telemetria custou {com - sem:.1f} ms na resposta"


def test_registrar_sem_conexao_nao_explode() -> None:
    """Perder uma linha de métrica é aceitável; virar erro no cliente, não."""
    telemetry.fechar()
    telemetry.registrar(evento())  # não deve levantar nada


# ------------------------------------------------------ últimas conversas


def test_ultimas_vem_da_mais_nova_para_a_mais_velha() -> None:
    for i in range(3):
        telemetry.registrar(evento(texto=f"mensagem {i}"))
    ultimas = telemetry.metricas()["ultimas"]
    assert [linha["texto"] for linha in ultimas] == [
        "mensagem 2",
        "mensagem 1",
        "mensagem 0",
    ]


def test_ultimas_para_em_vinte() -> None:
    telemetry.registrar_muitos([evento(texto=f"m{i}") for i in range(30)])
    assert len(telemetry.metricas()["ultimas"]) == telemetry.ULTIMAS_NO_PAINEL == 20


def test_ultimas_marcam_o_que_e_sintetico() -> None:
    telemetry.registrar(evento(texto="real"))
    telemetry.registrar(evento(texto="semeado", simulado=1))
    por_texto = {
        linha["texto"]: linha["simulado"] for linha in telemetry.metricas()["ultimas"]
    }
    assert por_texto["real"] == 0
    assert por_texto["semeado"] == 1


# ------------------------------------------- séries do painel


def test_serie_por_dia_vem_em_ordem_crescente() -> None:
    telemetry.registrar(evento(ts="2026-08-30T10:00:00+00:00"))
    telemetry.registrar(evento(ts="2026-09-01T10:00:00+00:00"))
    telemetry.registrar(evento(ts="2026-08-31T10:00:00+00:00"))
    dias = [linha["dia"] for linha in telemetry.metricas()["por_dia"]]
    assert dias == sorted(dias), "o gráfico lê da esquerda para a direita"


def test_cascata_separa_as_camadas_de_decisao() -> None:
    telemetry.registrar_muitos(
        [evento(confidence_source="regra") for _ in range(3)]
        + [evento(confidence_source="embedding") for _ in range(2)]
        + [evento(confidence_source="nenhuma")]
    )
    assert telemetry.metricas()["por_camada"] == {
        "regra": 3,
        "embedding": 2,
        "nenhuma": 1,
    }


def test_escada_de_degradacao_separa_origem_da_resposta() -> None:
    telemetry.registrar_muitos(
        [evento(reply_source="generative") for _ in range(2)]
        + [evento(reply_source="template")]
    )
    assert telemetry.metricas()["por_origem_resposta"] == {
        "generative": 2,
        "template": 1,
    }
