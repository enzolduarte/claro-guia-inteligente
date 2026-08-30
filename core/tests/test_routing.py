from __future__ import annotations

import re
from datetime import datetime, timezone

import pytest

from app.flows import get_config, get_destination, get_flows
from app.routing import gerar_protocolo, resolve

FORMATO = re.compile(r"^[A-Z\-]+-\d{4}-\d{5}$")


def intent_ids() -> list[str]:
    return [intent.id for intent in get_flows().intencoes]


@pytest.mark.parametrize("intent_id", intent_ids())
def test_toda_intencao_resolve_para_destino_existente(intent_id: str) -> None:
    routing = resolve(intent_id=intent_id)
    assert get_destination(routing.destination) is not None
    assert routing.label


def test_intencao_nula_cai_no_destino_padrao() -> None:
    assert resolve().destination == get_config().destino_padrao


def test_intencao_desconhecida_cai_no_destino_padrao() -> None:
    """Catálogo fechado: nunca inferir um destino que não está mapeado."""
    assert resolve(intent_id="NAO_EXISTE").destination == get_config().destino_padrao


def test_destino_de_opcao_tem_precedencia_sobre_a_intencao() -> None:
    routing = resolve(intent_id="PLANO", option_destination="FLUXO_COMERCIAL_UPGRADE")
    assert routing.destination == "FLUXO_COMERCIAL_UPGRADE"


def test_destino_de_opcao_invalido_tambem_cai_no_padrao() -> None:
    routing = resolve(intent_id="PLANO", option_destination="FLUXO_FANTASMA")
    assert routing.destination == get_config().destino_padrao


def destinos_por_protocolo(gera: bool) -> list[str]:
    return [
        destino_id
        for destino_id, destino in get_flows().destinos.items()
        if destino.gera_protocolo is gera
    ]


@pytest.mark.parametrize("destino_id", destinos_por_protocolo(gera=False))
def test_destino_sem_protocolo_devolve_none(destino_id: str) -> None:
    assert resolve(option_destination=destino_id).protocol is None


@pytest.mark.parametrize("destino_id", destinos_por_protocolo(gera=True))
def test_destino_com_protocolo_usa_o_prefixo_do_catalogo(destino_id: str) -> None:
    destino = get_destination(destino_id)
    assert destino is not None and destino.prefixo_protocolo

    routing = resolve(option_destination=destino_id)
    assert routing.protocol is not None
    assert routing.protocol.startswith(f"{destino.prefixo_protocolo}-")
    assert FORMATO.match(routing.protocol)


def test_protocolo_carrega_o_ano_do_relogio() -> None:
    protocolo = gerar_protocolo("CLR")
    assert protocolo.split("-")[1] == str(datetime.now(timezone.utc).year)


def test_dois_protocolos_em_sequencia_sao_diferentes() -> None:
    assert gerar_protocolo("CLR") != gerar_protocolo("CLR")


def test_mil_protocolos_seguidos_nao_repetem() -> None:
    """O passo do contador é coprimo com 100 mil: percorre tudo sem colidir."""
    emitidos = [gerar_protocolo("CLR") for _ in range(1000)]
    assert len(set(emitidos)) == 1000


def test_routing_traz_url_do_catalogo_inclusive_quando_e_nula() -> None:
    """ATENDIMENTO_HUMANO e ESCALACAO_HUMANA não têm URL — a chave fica, o valor é nulo."""
    routing = resolve(option_destination="ATENDIMENTO_HUMANO")
    assert routing.url is None
    assert "url" in routing.model_dump()

    com_url = resolve(intent_id="SEGUNDA_VIA")
    assert com_url.url is not None and com_url.url.startswith("https://")
