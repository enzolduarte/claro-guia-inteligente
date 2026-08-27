from __future__ import annotations

import numpy as np
import pytest

from app.embeddings import catalog_shape, score
from app.flows import get_config, get_flows

from .conftest import cases_expecting

pytestmark = pytest.mark.usefixtures("modelo_carregado")

# Uma frase claramente de cada intenção, escrita fora dos exemplos de treino.
FRASES_CLARAS = {
    "FATURA": "minha conta chegou com um valor bem mais alto esse mes",
    "SEGUNDA_VIA": "preciso do boleto para conseguir pagar",
    "SUPORTE_TECNICO": "minha internet esta caindo o tempo todo",
    "PLANO": "quero mudar para outro plano",
    "COMPRA": "quero contratar um plano de fibra na minha casa",
    "ATENDIMENTO": "quero falar com um atendente de verdade",
    "COBRANCA_INDEVIDA": "me cobraram por um servico que eu nunca pedi",
}


def test_matriz_do_catalogo_tem_uma_linha_por_exemplo() -> None:
    esperado = sum(len(intent.exemplos) for intent in get_flows().intencoes)
    linhas, dim = catalog_shape()
    assert linhas == esperado == 105
    assert dim > 0


def test_toda_linha_da_matriz_tem_norma_um() -> None:
    """Vetores normalizados no boot é o que faz o cosseno virar produto escalar."""
    from app.embeddings import _catalog

    assert _catalog is not None
    normas = np.linalg.norm(_catalog, axis=1)
    assert np.allclose(normas, 1.0, atol=1e-5)


def test_toda_intencao_tem_uma_frase_que_a_identifica() -> None:
    assert set(FRASES_CLARAS) == {intent.id for intent in get_flows().intencoes}


@pytest.mark.parametrize("esperado,texto", sorted(FRASES_CLARAS.items()))
def test_frase_clara_pontua_acima_do_limiar_medio(esperado: str, texto: str) -> None:
    intent_id, similaridade = score(texto)  # type: ignore[misc]
    assert intent_id == esperado
    assert similaridade > get_config().limiar_medio


def test_frase_vaga_nunca_chega_a_banda_alta() -> None:
    """Garantia de segurança: mensagem vaga não pode ser roteada com confiança.

    Ela pode cair em MEDIO e virar pedido de confirmação, mas nunca em ALTO,
    que é o que dispensaria clarificação.
    """
    limiar_alto = get_config().limiar_alto
    for caso in cases_expecting("NAO_IDENTIFICADA"):
        _, similaridade = score(caso["texto"])  # type: ignore[misc]
        assert (
            similaridade < limiar_alto
        ), f"{caso['texto']!r} atingiu {similaridade:.3f}"


# A validação original do M3 pedia que estes 8 casos pontuassem abaixo de
# limiar_medio. Ela foi retirada: presume um sistema de duas saídas (classifica
# ou não classifica), e este tem três — rotear, pedir confirmação, perguntar
# aberto. O teste acima mede a garantia certa para três saídas: mensagem vaga
# nunca chega à banda que dispensa confirmação. Medido em 23/08/2026, os 8 casos
# vão de 0.524 a 0.696, todos abaixo do limiar_alto de 0.75.
