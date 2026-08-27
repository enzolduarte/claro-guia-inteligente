from __future__ import annotations

import pytest

from app.flows import get_flows
from app.normalize import normalize
from app.rules import RULE_CONFIDENCE, match_rules


def plain_rules() -> list[tuple[str, str]]:
    return [
        (rule, intent.id)
        for intent in get_flows().intencoes
        if not intent.sensivel
        for rule in intent.regras
    ]


@pytest.mark.parametrize("rule,intent_id", plain_rules())
def test_toda_regra_dispara_a_propria_intencao(rule: str, intent_id: str) -> None:
    assert match_rules(normalize(rule)) == (intent_id, RULE_CONFIDENCE)


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("wifi nao conecta de jeito nenhum", "SUPORTE_TECNICO"),
        ("queria dar uma olhada em mudar de plano", "PLANO"),
        ("vim do concorrente quero assinar", "COMPRA"),
    ],
)
def test_golden_com_palavra_chave_obvia(texto: str, esperado: str) -> None:
    """Casos do golden_dataset que carregam palavra-chave literal do flows.json."""
    matched = match_rules(normalize(texto))
    assert matched is not None
    assert matched[0] == esperado


@pytest.mark.parametrize("texto", ["quero a 2ª via da fatura", "QUERO A 2A VIA!!"])
def test_acento_caixa_e_pontuacao_nao_atrapalham(texto: str) -> None:
    matched = match_rules(normalize(texto))
    assert matched is not None
    assert matched[0] == "SEGUNDA_VIA"


def test_regra_mais_longa_vence() -> None:
    """'falar com atendente' (19) é mais específica que 'mudar meu plano' (15)."""
    texto = normalize("quero mudar meu plano e falar com atendente")
    matched = match_rules(texto)
    assert matched is not None
    assert matched[0] == "ATENDIMENTO"


def test_intencao_sensivel_nao_aparece_nas_regras() -> None:
    """Sensibilidade é etapa 1 e já encerrou; a etapa 2 não a repete."""
    assert match_rules(normalize("quero estorno")) is None
    assert match_rules(normalize("cobranca indevida")) is None


def test_frase_sem_palavra_chave_nao_casa() -> None:
    """Recall baixo é o projeto: o que não bate aqui cai para os embeddings."""
    assert match_rules(normalize("oi")) is None
    assert match_rules(normalize("esse mes minha conta ficou bem mais alta")) is None


@pytest.mark.xfail(
    strict=True,
    reason=(
        "LIMITACAO PERMANENTE, medida e documentada. A regra 'quero contratar' "
        "(COMPRA) dispara em 'quero contratar mais dados', que o golden_dataset "
        "rotula PLANO. Verificado no M3: tirar a regra NAO resolveria — os "
        "embeddings tambem respondem COMPRA (0.628). As duas camadas concordam "
        "entre si e discordam do rotulo, porque o verbo 'contratar' puxa para "
        "aquisicao enquanto o objeto ('mais dados') e o plano que ja existe. O "
        "proprio golden chama isso de par de confusao classico. Nao ha correcao "
        "sem mudar o rotulo ou os exemplos, e nenhum dos dois compensa."
    ),
)
def test_contratar_mais_dados_deveria_ser_plano() -> None:
    matched = match_rules(normalize("quero contratar mais dados"))
    assert matched is not None
    assert matched[0] == "PLANO"
