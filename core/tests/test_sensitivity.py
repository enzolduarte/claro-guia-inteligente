from __future__ import annotations

import pytest

from app.flows import get_flows
from app.normalize import normalize
from app.sensitivity import check_sensitive

from .conftest import SENSITIVE_INTENT, cases_expecting, cases_not_expecting, texts


def sensitive_rules() -> list[str]:
    return [
        rule
        for intent in get_flows().intencoes
        if intent.sensivel
        for rule in intent.regras
    ]


@pytest.mark.parametrize("rule", sensitive_rules())
def test_toda_regra_sensivel_dispara_a_si_mesma(rule: str) -> None:
    assert check_sensitive(normalize(rule)) == SENSITIVE_INTENT


@pytest.mark.parametrize(
    "texto",
    [
        "fui cobrado por algo que nao contratei",
        "FUI COBRADO POR ALGO QUE NÃO CONTRATEI",
        "quero estorno, por favor!",
        "isso é cobrança indevida",
        "vou no procon se não resolverem",
    ],
)
def test_frases_com_palavra_chave_sao_detectadas(texto: str) -> None:
    """Acento, caixa e pontuação não podem furar a barreira de sensibilidade."""
    assert check_sensitive(normalize(texto)) == SENSITIVE_INTENT


@pytest.mark.parametrize("texto", texts(cases_not_expecting(SENSITIVE_INTENT)))
def test_zero_falso_positivo_em_caso_nao_sensivel(texto: str) -> None:
    """Requisito duro: assunto não sensível jamais pode ser escalado por engano."""
    assert check_sensitive(normalize(texto)) is None


@pytest.mark.parametrize(
    "texto",
    [
        "nao contratei nada ainda, queria ver os planos de fibra",
        "ainda não contratei, quanto custa a fibra",
        "nunca contratei nada com voces, como faco pra ser cliente",
        "nao contratei ainda, tem cobertura no meu bairro",
    ],
)
def test_prospect_nao_escala(texto: str) -> None:
    """Quem ainda não é cliente não está contestando cobrança nenhuma.

    Sem palavra do universo de cobrança na frase, 'nao contratei' não abre
    escalação — era o falso positivo que mandava prospect para o especialista
    com pedido de desculpas por uma cobrança que não existia.
    """
    assert check_sensitive(normalize(texto)) is None


@pytest.mark.parametrize(
    "texto",
    [
        "fui cobrado por algo que nao contratei",
        "nunca contratei esse servico e ta na minha conta",
        "nao contratei essa assinatura que ta na fatura",
        "tem um valor na conta que eu nao contratei",
        "debitaram no cartao algo que nunca contratei",
    ],
)
def test_contestacao_real_continua_escalando(texto: str) -> None:
    """O outro lado da moeda: exigir contexto não pode furar a barreira."""
    assert check_sensitive(normalize(texto)) == SENSITIVE_INTENT


def test_termo_condicional_sozinho_nao_dispara() -> None:
    assert check_sensitive(normalize("nao contratei")) is None
    assert check_sensitive(normalize("nunca contratei")) is None
    # Basta uma palavra de cobrança na mesma mensagem para valer.
    assert check_sensitive(normalize("nao contratei essa taxa")) == SENSITIVE_INTENT


@pytest.mark.xfail(
    strict=True,
    reason=(
        "LACUNA CONHECIDA, reportada e não corrigida: as `regras` de "
        "COBRANCA_INDEVIDA no flows.json são palavras-chave literais, e o "
        "golden_dataset declara em _metodologia.disjuncao que nenhuma frase "
        "dele reusa vocabulário de treino. Resultado: 0/10 de recall nesta "
        "camada. A detecção desses casos depende dos embeddings (M3). "
        "Este xfail é strict de propósito: se alguém ampliar as regras no "
        "flows.json, o teste passa a XPASS e quebra o suite, pedindo revisão."
    ),
)
@pytest.mark.parametrize("texto", texts(cases_expecting(SENSITIVE_INTENT)))
def test_golden_cobranca_indevida_detectado(texto: str) -> None:
    assert check_sensitive(normalize(texto)) == SENSITIVE_INTENT
