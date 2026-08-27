"""Mede a latência de classificação. Uso: python scripts/bench_classify.py

Separa o custo de boot (carga do modelo, que acontece uma vez) do custo por
mensagem (que é o que o cliente sente). Só o segundo entra no orçamento
de latência do RNF003.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CORE_DIR))

from app.classifier import classify  # noqa: E402
from app.embeddings import catalog_shape, load_model  # noqa: E402

RODADAS = 100


def frases() -> list[str]:
    """Mistura casos reais do golden com os que param nas etapas 1 e 2."""
    golden = json.loads(
        (CORE_DIR / "data/golden_dataset.json").read_text(encoding="utf-8")
    )["casos"]
    textos = [caso["texto"] for caso in golden]
    textos += ["quero a 2a via da fatura", "fui cobrado por algo que nao contratei"]
    return textos


def main() -> None:
    print("carregando modelo...", end=" ", flush=True)
    inicio = time.perf_counter()
    load_model()
    boot = time.perf_counter() - inicio
    linhas, dim = catalog_shape()
    print(f"{boot:.1f}s   matriz do catálogo: ({linhas}, {dim})")

    textos = frases()
    for i in range(20):  # aquecimento, fora da medição
        classify(textos[i % len(textos)])

    amostras: list[float] = []
    for i in range(RODADAS):
        texto = textos[i % len(textos)]
        t0 = time.perf_counter()
        classify(texto)
        amostras.append((time.perf_counter() - t0) * 1000)

    amostras.sort()
    p50 = statistics.median(amostras)
    p95 = amostras[int(len(amostras) * 0.95)]
    print(f"\n{RODADAS} classificações")
    print(f"  p50 ......... {p50:6.1f} ms")
    print(f"  p95 ......... {p95:6.1f} ms")
    print(f"  min / max ... {amostras[0]:.1f} / {amostras[-1]:.1f} ms")

    orcamento = 120
    veredito = "OK" if p95 < orcamento else "ESTOUROU"
    print(f"\n  orçamento p95 < {orcamento} ms -> {veredito}")
    sys.exit(0 if p95 < orcamento else 1)


if __name__ == "__main__":
    main()
