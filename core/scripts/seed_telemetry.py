"""Semeia a telemetria com interações sintéticas, para o painel ter o que mostrar.

Toda linha entra com `simulado = 1`. Isso não é detalhe: o relatório do
Challenge não pode apresentar um número sem saber quanto dele é invenção.
O /v1/metrics devolve `reais` e `simulados` separados justamente por isso.

    .venv/bin/python scripts/seed_telemetry.py [quantidade]
"""

from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CORE_DIR))

from app import telemetry  # noqa: E402
from app.flows import get_flows, init_flows  # noqa: E402
from app.routing import gerar_protocolo  # noqa: E402

QUANTIDADE_PADRAO = 200
DIAS = 14

# Como as mensagens se distribuem na prática: a maioria resolve sozinha, uma
# parte precisa de esclarecimento, e uma fatia menor vai para gente.
PESOS_DE_BANDA = [("ALTO", 0.62), ("MEDIO", 0.26), ("BAIXO", 0.12)]


def sortear_horario() -> str:
    agora = datetime.now(timezone.utc)
    momento = agora - timedelta(
        days=random.randint(0, DIAS - 1),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    return momento.isoformat(timespec="seconds")


def sortear_evento() -> telemetry.Evento:
    flows = get_flows()
    intencoes = flows.intencoes
    banda = random.choices(
        [b for b, _ in PESOS_DE_BANDA], [p for _, p in PESOS_DE_BANDA]
    )[0]
    canal = random.choices(["web", "telegram"], [0.75, 0.25])[0]

    if banda == "BAIXO":
        return telemetry.Evento(
            session_id=f"{canal}:sim-{random.randrange(10**6):06d}",
            canal=canal,
            texto=random.choice(["oi", "bom dia", "preciso de ajuda", "me ajuda ai"]),
            intent=None,
            confidence=round(random.uniform(0.30, 0.54), 3),
            band="BAIXO",
            confidence_source="embedding",
            state="AGUARDANDO",
            destination=None,
            protocol=None,
            reply_source="fallback",
            latency_ms=random.randint(9, 22),
            simulado=1,
            ts=sortear_horario(),
        )

    intent = random.choice(intencoes)
    texto = random.choice(intent.exemplos)
    por_regra = random.random() < 0.35

    if banda == "MEDIO":
        estado, destino, protocolo, fonte_resposta = (
            "CLARIFICANDO",
            None,
            None,
            "template",
        )
        confianca = round(random.uniform(0.56, 0.74), 3)
    else:
        confianca = 0.97 if por_regra else round(random.uniform(0.76, 0.99), 3)
        destino_id = intent.destino
        destino = flows.destinos[destino_id]
        estado = "ESCALANDO" if intent.sensivel else "ROTEANDO"
        protocolo = (
            gerar_protocolo(destino.prefixo_protocolo)
            if destino.gera_protocolo and destino.prefixo_protocolo
            else None
        )
        destino, fonte_resposta = destino_id, random.choice(["template", "generative"])

    return telemetry.Evento(
        session_id=f"{canal}:sim-{random.randrange(10**6):06d}",
        canal=canal,
        texto=texto,
        intent=intent.id,
        confidence=confianca,
        band=banda,
        confidence_source="regra" if por_regra else "embedding",
        state=estado,
        destination=destino,
        protocol=protocolo,
        reply_source=fonte_resposta,
        latency_ms=random.randint(11, 28)
        + (900 if fonte_resposta == "generative" else 0),
        simulado=1,
        ts=sortear_horario(),
    )


def main() -> int:
    quantidade = int(sys.argv[1]) if len(sys.argv) > 1 else QUANTIDADE_PADRAO
    init_flows()
    telemetry.conectar()

    gravados = telemetry.registrar_muitos([sortear_evento() for _ in range(quantidade)])
    resumo = telemetry.metricas()
    telemetry.fechar()

    print(
        f"{gravados} interações sintéticas gravadas em {telemetry.caminho_do_banco()}"
    )
    print(
        f"  base agora: {resumo['total_geral']} linhas "
        f"({resumo['reais']} reais, {resumo['simulados']} simuladas)"
    )
    print(
        f"  resolução digital: {resumo['taxa_resolucao_digital']:.1%}   "
        f"escalação: {resumo['taxa_escalacao']:.1%}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
