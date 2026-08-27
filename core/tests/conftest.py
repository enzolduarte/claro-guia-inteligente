from __future__ import annotations

import json
from typing import Any

import pytest

from app.config import CORE_DIR

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
