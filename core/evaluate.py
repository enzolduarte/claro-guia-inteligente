"""Avaliação do classificador contra o golden dataset.

Roda o classificador de verdade — o mesmo `classify` do endpoint — sobre os 78
casos do golden_dataset.json e imprime as duas métricas que o próprio dataset
define em `_metodologia`:

  ACURÁCIA DE INTENÇÃO  sobre os 70 casos com intenção esperada
  ACURÁCIA DE REJEIÇÃO  sobre os 8 casos vagos (NAO_IDENTIFICADA)

Sem LLM e sem HTTP: o Gemini não participa da classificação (regra 1 do
CLAUDE.md), então avaliá-lo aqui só adicionaria ruído de rede.

Uso:  cd core && python evaluate.py
Sai com código 1 se a acurácia de intenção ficar abaixo de 0,70.
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CORE_DIR))

from app.classifier import classify  # noqa: E402
from app.contract import ConfidenceBand  # noqa: E402
from app.embeddings import load_model  # noqa: E402
from app.flows import get_config, get_flows, init_flows  # noqa: E402

PISO_DE_ACEITE = 0.70
REJEITADA = "NAO_IDENTIFICADA"


def carregar_casos() -> list[dict]:
    caminho = CORE_DIR / "data" / "golden_dataset.json"
    return json.loads(caminho.read_text(encoding="utf-8"))["casos"]


def rotulo(intent: str | None) -> str:
    return intent if intent is not None else REJEITADA


def linha(texto: str = "") -> None:
    print(texto)


def cabecalho(titulo: str) -> None:
    linha()
    linha(f"═══ {titulo} " + "═" * max(0, 64 - len(titulo)))
    linha()


def main() -> int:
    init_flows()
    print("carregando modelo de embeddings...", end=" ", flush=True)
    t0 = time.perf_counter()
    load_model()
    print(f"{time.perf_counter() - t0:.1f}s")

    casos = carregar_casos()
    config = get_config()
    intencoes = [intent.id for intent in get_flows().intencoes]

    # aquecimento fora da medição
    classify("aquecimento")

    resultados = []
    tempos = []
    for caso in casos:
        t0 = time.perf_counter()
        resultado = classify(caso["texto"])
        tempos.append((time.perf_counter() - t0) * 1000)
        resultados.append((caso, resultado))

    com_intencao = [(c, r) for c, r in resultados if c["esperado"] != REJEITADA]
    vagos = [(c, r) for c, r in resultados if c["esperado"] == REJEITADA]

    # ---------------------------------------------- 1. acurácia de intenção
    acertos = [(c, r) for c, r in com_intencao if r.intent == c["esperado"]]
    erros = [(c, r) for c, r in com_intencao if r.intent != c["esperado"]]
    acc_intencao = len(acertos) / len(com_intencao)

    cabecalho("1 · ACURÁCIA DE INTENÇÃO")
    linha(
        f"  global: {len(acertos)}/{len(com_intencao)} = {acc_intencao:.1%}"
        f"   (meta do dataset: 80% · piso deste script: {PISO_DE_ACEITE:.0%})"
    )

    linha()
    linha("  por dificuldade:")
    por_dif: dict[str, list[bool]] = defaultdict(list)
    for c, r in com_intencao:
        por_dif[c["dificuldade"]].append(r.intent == c["esperado"])
    for dif in ("facil", "medio", "dificil"):
        oks = por_dif[dif]
        linha(f"    {dif:8} {sum(oks):2}/{len(oks):2} = {sum(oks)/len(oks):6.1%}")

    linha()
    linha("  por intenção:")
    por_int: dict[str, list[bool]] = defaultdict(list)
    for c, r in com_intencao:
        por_int[c["esperado"]].append(r.intent == c["esperado"])
    for iid in intencoes:
        oks = por_int[iid]
        barra = "█" * sum(oks) + "·" * (len(oks) - sum(oks))
        linha(f"    {iid:18} {sum(oks):2}/{len(oks):2}  {barra}")

    # ---------------------------------------------- 2. acurácia de rejeição
    cabecalho("2 · ACURÁCIA DE REJEIÇÃO (8 casos vagos)")
    rejeitados = [(c, r) for c, r in vagos if r.confidence < config.limiar_medio]
    linha(
        f"  estrita (score < limiar_medio {config.limiar_medio}): "
        f"{len(rejeitados)}/{len(vagos)} = {len(rejeitados)/len(vagos):.1%}"
        f"   (meta do dataset: 75%)"
    )

    sem_rota = [(c, r) for c, r in vagos if r.band is not ConfidenceBand.ALTO]
    linha(
        f"  sem roteamento confiante (banda ≠ ALTO):     "
        f"{len(sem_rota)}/{len(vagos)} = {len(sem_rota)/len(vagos):.1%}"
    )
    linha()
    linha("  A métrica estrita assume duas saídas (classifica ou rejeita); esta")
    linha("  arquitetura tem três: rotear, pedir confirmação, pergunta aberta.")
    linha("  Caso vago em banda MÉDIA vira pergunta de sim/não — não é roteado.")
    linha("  A garantia operacional é a segunda linha; a primeira fica reportada")
    linha("  porque é a que o dataset define.")
    linha()
    for c, r in vagos:
        destino_pratico = (
            "pergunta aberta"
            if r.band is ConfidenceBand.BAIXO
            else (
                "pede confirmação"
                if r.band is ConfidenceBand.MEDIO
                else "ROTEIA (falha!)"
            )
        )
        linha(
            f"    {c['texto']:26} score {r.confidence:.3f}  {r.band.value:5}  → {destino_pratico}"
        )

    # ---------------------------------------------- 3. matriz de confusão
    cabecalho("3 · MATRIZ DE CONFUSÃO  (linha = esperado, coluna = obtido)")
    rotulos = intencoes + [REJEITADA]
    curto = {iid: iid[:4] for iid in rotulos}
    curto[REJEITADA] = "NAO_ID"
    matriz: dict[tuple[str, str], int] = defaultdict(int)
    for c, r in resultados:
        matriz[(c["esperado"], rotulo(r.intent))] += 1

    larg = 19
    linha(" " * larg + "".join(f"{curto[o]:>7}" for o in rotulos))
    for esperado in rotulos:
        celulas = ""
        for obtido in rotulos:
            n = matriz[(esperado, obtido)]
            celulas += f"{n if n else '·':>7}"
        linha(f"  {esperado:17}{celulas}")

    # ---------------------------------------------- 4. casos errados
    cabecalho(f"4 · CASOS ERRADOS ({len(erros)})")
    for c, r in erros:
        linha(f"  «{c['texto']}»")
        linha(
            f"     esperado {c['esperado']} · obtido {rotulo(r.intent)}"
            f" · score {r.confidence:.3f} ({r.source.value}) · {c['dificuldade']}"
        )
        if c.get("nota"):
            linha(f"     nota do dataset: {c['nota']}")
        linha()

    # ---------------------------------------------- 5. tempo
    media = sum(tempos) / len(tempos)
    cabecalho("5 · DESEMPENHO")
    linha(f"  tempo médio de classificação: {media:.1f} ms  ({len(tempos)} casos)")

    linha()
    if acc_intencao < PISO_DE_ACEITE:
        linha(
            f"REPROVADO: acurácia de intenção {acc_intencao:.1%} abaixo do piso {PISO_DE_ACEITE:.0%}."
        )
        return 1
    linha(f"OK: acurácia de intenção {acc_intencao:.1%} (piso {PISO_DE_ACEITE:.0%}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
