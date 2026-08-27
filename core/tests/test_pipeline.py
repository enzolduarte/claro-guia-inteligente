"""Comportamento do sistema inteiro, não de uma camada isolada.

O que importa para o cliente não é qual etapa reconheceu a mensagem, e sim onde
ela termina. Estes testes olham só o resultado final de `classify`.
"""

from __future__ import annotations

import pytest

from app.classifier import classify
from app.contract import ConfidenceBand

from .conftest import SENSITIVE_INTENT, cases_expecting

pytestmark = pytest.mark.usefixtures("modelo_carregado")


def test_toda_contestacao_de_cobranca_e_reconhecida() -> None:
    """As palavras-chave sozinhas pegavam 0 destes 10.

    O golden_dataset é escrito de propósito sem reusar vocabulário de treino,
    então a camada de regras não tinha como pegá-los. Com a etapa 3 no lugar e
    os limiares calibrados em 23/08/2026, o sistema reconhece os 10.
    """
    casos = cases_expecting(SENSITIVE_INTENT)
    perdidos = [
        caso["texto"]
        for caso in casos
        if classify(caso["texto"]).intent != SENSITIVE_INTENT
    ]
    assert not perdidos, f"contestação não reconhecida: {perdidos}"


def test_nenhuma_contestacao_cai_em_banda_baixa() -> None:
    """Banda baixa viraria pergunta aberta — atraso ruim para quem contesta."""
    for caso in cases_expecting(SENSITIVE_INTENT):
        resultado = classify(caso["texto"])
        assert resultado.band is not ConfidenceBand.BAIXO, (
            f"{caso['texto']!r} ficou em {resultado.confidence:.3f}, "
            "abaixo do piso — o cliente teria que repetir o pedido"
        )


@pytest.mark.parametrize("caso", cases_expecting("NAO_IDENTIFICADA"))
def test_mensagem_vaga_nunca_e_roteada_com_confianca(caso: dict) -> None:
    """A garantia central: sem certeza, o sistema pergunta em vez de decidir."""
    resultado = classify(caso["texto"])
    assert resultado.band is not ConfidenceBand.ALTO, (
        f"{caso['texto']!r} chegou à banda ALTA com {resultado.confidence:.3f} "
        "— seria roteado sem pedir confirmação"
    )
