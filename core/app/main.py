from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI

from .flows import get_flows, init_flows

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # flows.json inválido derruba o boot de propósito: erro de base de
    # conhecimento aparece no deploy, não no atendimento.
    init_flows()
    # M2: carregar o modelo de embeddings e pré-computar a matriz do catálogo aqui.
    yield


app = FastAPI(title="Claro Guia Inteligente — Core", version=VERSION, lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, Any]:
    flows = get_flows()
    return {
        "status": "ok",
        "version": VERSION,
        "flows_version": flows.versao,
        "intents_loaded": len(flows.intencoes),
    }
