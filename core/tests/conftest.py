from __future__ import annotations

import json
from typing import Any

import pytest

from app.config import CORE_DIR, settings

GOLDEN_PATH = CORE_DIR / "data" / "golden_dataset.json"

SENSITIVE_INTENT = "COBRANCA_INDEVIDA"


def golden_cases() -> list[dict[str, Any]]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))["casos"]


def cases_expecting(intent_id: str) -> list[dict[str, Any]]:
    return [case for case in golden_cases() if case["esperado"] == intent_id]


def cases_not_expecting(intent_id: str) -> list[dict[str, Any]]:
    return [case for case in golden_cases() if case["esperado"] != intent_id]


def texts(cases: list[dict[str, Any]]) -> list[str]:
    return [case["texto"] for case in cases]


@pytest.fixture(scope="session")
def modelo_carregado() -> None:
    """Carrega o modelo uma vez por sessão de teste — leva alguns segundos."""
    from app.embeddings import is_ready, load_model

    if not is_ready():
        load_model()


@pytest.fixture(autouse=True)
def sem_llm_por_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    """A suíte nunca fala com a API do Gemini de verdade.

    Sem isto, ter uma chave no core/.env deixa os testes lentos (mais de um
    segundo por chamada), instáveis (dependem da rede) e caros (queimam cota).
    Quem precisa do caminho generativo liga a chave no próprio teste — é o que
    o test_generator faz — e substitui a chamada de rede por um dublê.
    """
    monkeypatch.setattr(settings, "gemini_api_key", "", raising=False)


@pytest.fixture(autouse=True)
def texto_redigido_limpo() -> None:
    """Zera o cache do generator entre os testes.

    Em produção o cache é o que faz o texto ser redigido uma vez por intenção.
    Na suíte ele esconderia falhas: depois de um teste gerar com sucesso, os
    seguintes receberiam o valor guardado e nunca chegariam ao dublê.
    """
    from app.generator import limpar_cache

    limpar_cache()
