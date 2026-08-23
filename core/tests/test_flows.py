from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from app.flows import _flows_path, load_flows

REAL_FLOWS = _flows_path()


def raw_flows() -> dict[str, Any]:
    """Cópia crua do arquivo real. Nunca escrevemos de volta nele."""
    return deepcopy(json.loads(REAL_FLOWS.read_text(encoding="utf-8")))


def write_temp(tmp_path: Path, data: dict[str, Any]) -> Path:
    target = tmp_path / "flows.json"
    target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return target


def test_carrega_o_arquivo_real() -> None:
    flows = load_flows()

    assert flows.versao == "1.0.0"
    assert len(flows.intencoes) == 7
    assert flows.config.destino_padrao in flows.destinos
    assert flows.config.limiar_alto > flows.config.limiar_medio

    # Todo destino referenciado resolve dentro do catálogo.
    for intent in flows.intencoes:
        assert intent.destino in flows.destinos
        if intent.clarificacao:
            for option in intent.clarificacao.opcoes:
                assert option.destino in flows.destinos


def test_erro_quando_destino_da_intencao_nao_existe(tmp_path: Path) -> None:
    data = raw_flows()
    data["intencoes"][0]["destino"] = "FLUXO_INEXISTENTE"

    with pytest.raises(RuntimeError) as exc:
        load_flows(write_temp(tmp_path, data))

    assert "intencoes[0].destino" in str(exc.value)
    assert "FLUXO_INEXISTENTE" in str(exc.value)


def test_erro_quando_destino_de_clarificacao_nao_existe(tmp_path: Path) -> None:
    data = raw_flows()
    intent = next(i for i in data["intencoes"] if i.get("clarificacao"))
    intent["clarificacao"]["opcoes"][0]["destino"] = "FLUXO_FANTASMA"

    with pytest.raises(RuntimeError) as exc:
        load_flows(write_temp(tmp_path, data))

    assert "clarificacao.opcoes[0].destino" in str(exc.value)
    assert "FLUXO_FANTASMA" in str(exc.value)


def test_erro_quando_limiar_medio_maior_que_limiar_alto(tmp_path: Path) -> None:
    data = raw_flows()
    data["config"]["limiar_medio"] = 0.90
    data["config"]["limiar_alto"] = 0.80

    with pytest.raises(RuntimeError) as exc:
        load_flows(write_temp(tmp_path, data))

    assert "limiar_alto" in str(exc.value)
    assert "limiar_medio" in str(exc.value)


def test_erro_quando_destino_padrao_nao_existe(tmp_path: Path) -> None:
    data = raw_flows()
    data["config"]["destino_padrao"] = "NAO_MAPEADO"

    with pytest.raises(RuntimeError) as exc:
        load_flows(write_temp(tmp_path, data))

    assert "config.destino_padrao" in str(exc.value)


def test_erro_quando_ha_exemplo_duplicado(tmp_path: Path) -> None:
    data = raw_flows()
    exemplos = data["intencoes"][0]["exemplos"]
    exemplos.append(exemplos[0])

    with pytest.raises(RuntimeError) as exc:
        load_flows(write_temp(tmp_path, data))

    assert "exemplos" in str(exc.value)
    assert "duplicado" in str(exc.value)
