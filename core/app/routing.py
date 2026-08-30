"""Etapa 4 do pipeline — motor de roteamento e protocolos.

Este módulo é o único lugar que decide para onde uma intenção vai, e é onde a
regra 2 do CLAUDE.md mora: o catálogo de destinos é fechado. Intenção sem
destino mapeado cai em `config.destino_padrao`. Nunca se infere um destino.

O destino sai sempre do flows.json — nem o modelo nem o LLM escolhem.
"""

from __future__ import annotations

import itertools
import random
from datetime import datetime, timezone

from .contract import Routing
from .flows import Destination, get_config, get_destination, get_intent

# Espaço de 5 dígitos do protocolo.
_ESPACO = 100_000

# O contador anda de 37 em 37 a partir de um ponto sorteado no boot. Como 37 não
# divide 100 mil, a sequência passa por todos os 100 mil números antes de
# repetir qualquer um — dois protocolos nunca colidem dentro de uma execução.
# O passo e o ponto de partida aleatórios existem para o número não denunciar
# quantos atendimentos o sistema já fez.
_PASSO = 37
_inicio = random.randrange(_ESPACO)
_sequencia = itertools.count()


def _numero_do_protocolo() -> int:
    return (_inicio + next(_sequencia) * _PASSO) % _ESPACO


def gerar_protocolo(prefixo: str) -> str:
    """{prefixo}-{ano}-{5 dígitos}. O ano vem do relógio do sistema."""
    ano = datetime.now(timezone.utc).year
    return f"{prefixo}-{ano}-{_numero_do_protocolo():05d}"


def _resolver_destino(
    intent_id: str | None, option_destination: str | None
) -> tuple[str, Destination]:
    """A opção de clarificação manda, depois a intenção, depois o padrão."""
    candidato = option_destination
    if candidato is None and intent_id is not None:
        intent = get_intent(intent_id)
        candidato = intent.destino if intent is not None else None

    if candidato is not None:
        destino = get_destination(candidato)
        if destino is not None:
            return candidato, destino

    # Catálogo fechado: sem destino mapeado, cai no padrão. Nunca inferir.
    padrao_id = get_config().destino_padrao
    padrao = get_destination(padrao_id)
    assert padrao is not None  # o boot valida que o destino_padrao existe
    return padrao_id, padrao


def resolve(
    intent_id: str | None = None, option_destination: str | None = None
) -> Routing:
    destino_id, destino = _resolver_destino(intent_id, option_destination)
    protocolo = (
        gerar_protocolo(destino.prefixo_protocolo)
        if destino.gera_protocolo and destino.prefixo_protocolo
        else None
    )
    return Routing(
        destination=destino_id,
        label=destino.label,
        url=destino.url,
        protocol=protocolo,
    )
