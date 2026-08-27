"""Loader e validador do flows.json — a única fonte de verdade do projeto.

Carrega uma vez, no lifespan, e guarda em memória. Nenhuma releitura de disco
por requisição. Qualquer inconsistência derruba o boot com RuntimeError
apontando o campo exato, para o erro aparecer no deploy e não no atendimento.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ValidationError

from .config import CORE_DIR, settings


class Destination(BaseModel):
    label: str
    categoria: str
    url: str | None
    gera_protocolo: bool
    exige_autenticacao: bool
    prefixo_protocolo: str | None = None
    prioridade: str | None = None
    transfere_contexto: bool = False


class ClarificationOption(BaseModel):
    id: str
    label: str
    destino: str
    exemplos: list[str] = []


class Clarification(BaseModel):
    pergunta: str
    opcoes: list[ClarificationOption]


class Script(BaseModel):
    reconhecimento: str
    resumo: str
    passos: list[str]
    fechamento: str


class Diagnosis(BaseModel):
    perguntas: list[str]


class ConditionalRules(BaseModel):
    """Termos ambíguos sozinhos: só valem acompanhados de uma palavra de contexto."""

    termos: list[str]
    exige_contexto: list[str]


class Intent(BaseModel):
    id: str
    nome: str
    descricao: str
    sensivel: bool
    destino: str
    regras: list[str]
    exemplos: list[str]
    roteiro: Script
    sempre_clarificar: bool = False
    motivo_sensibilidade: str | None = None
    clarificacao: Clarification | None = None
    diagnostico: Diagnosis | None = None
    regras_condicionais: ConditionalRules | None = None


class UnidentifiedReply(BaseModel):
    estado: str
    texto: str
    sugestoes: list[str]


class FlowsConfig(BaseModel):
    limiar_alto: float
    limiar_medio: float
    destino_padrao: str
    timeout_llm_ms: int
    resposta_nao_identificada: UnidentifiedReply


class Flows(BaseModel):
    versao: str
    atualizado_em: str
    config: FlowsConfig
    destinos: dict[str, Destination]
    intencoes: list[Intent]


_flows: Flows | None = None
_intents_by_id: dict[str, Intent] = {}


def _flows_path() -> Path:
    """Resolve FLOWS_PATH. Caminho relativo é ancorado em core/, não no CWD."""
    path = Path(settings.flows_path)
    return path if path.is_absolute() else CORE_DIR / path


def _validate(flows: Flows, origin: str) -> None:
    """Coerência interna que o schema não cobre. Levanta RuntimeError no 1º erro."""
    catalog = set(flows.destinos)
    known = ", ".join(sorted(catalog))

    if flows.config.destino_padrao not in catalog:
        raise RuntimeError(
            f"{origin}: config.destino_padrao = {flows.config.destino_padrao!r} "
            f"não existe no catálogo 'destinos'. Destinos válidos: {known}"
        )

    if flows.config.limiar_alto <= flows.config.limiar_medio:
        raise RuntimeError(
            f"{origin}: config.limiar_alto ({flows.config.limiar_alto}) deve ser maior "
            f"que config.limiar_medio ({flows.config.limiar_medio})."
        )

    seen_ids: set[str] = set()
    for i, intent in enumerate(flows.intencoes):
        field = f"intencoes[{i}]"

        if intent.id in seen_ids:
            raise RuntimeError(f"{origin}: {field}.id = {intent.id!r} está duplicado.")
        seen_ids.add(intent.id)

        if intent.destino not in catalog:
            raise RuntimeError(
                f"{origin}: {field}.destino = {intent.destino!r} (intenção {intent.id}) "
                f"não existe no catálogo 'destinos'. Destinos válidos: {known}"
            )

        seen_examples: set[str] = set()
        for j, example in enumerate(intent.exemplos):
            if example in seen_examples:
                raise RuntimeError(
                    f"{origin}: {field}.exemplos[{j}] está duplicado na intenção "
                    f"{intent.id}: {example!r}"
                )
            seen_examples.add(example)

        if intent.clarificacao is None:
            continue

        for k, option in enumerate(intent.clarificacao.opcoes):
            if option.destino not in catalog:
                raise RuntimeError(
                    f"{origin}: {field}.clarificacao.opcoes[{k}].destino = "
                    f"{option.destino!r} (opção {option.id!r} da intenção {intent.id}) "
                    f"não existe no catálogo 'destinos'. Destinos válidos: {known}"
                )


def load_flows(path: Path | None = None) -> Flows:
    """Lê, valida e devolve. Não mexe no cache — é o que os testes exercitam."""
    target = path or _flows_path()
    origin = target.name

    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"flows.json não encontrado em {target}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{origin}: JSON inválido na linha {exc.lineno}: {exc.msg}"
        ) from exc

    try:
        flows = Flows.model_validate(raw)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        )
        raise RuntimeError(f"{origin}: estrutura inválida — {problems}") from exc

    _validate(flows, origin)
    return flows


def init_flows(path: Path | None = None) -> Flows:
    """Carrega e memoriza. Chamado uma vez, no lifespan."""
    global _flows
    _flows = load_flows(path)
    _intents_by_id.clear()
    _intents_by_id.update({intent.id: intent for intent in _flows.intencoes})
    return _flows


def get_flows() -> Flows:
    if _flows is None:
        return init_flows()
    return _flows


def get_config() -> FlowsConfig:
    return get_flows().config


def get_intent(intent_id: str) -> Intent | None:
    """None quando a intenção não existe — quem chama decide o fallback."""
    get_flows()
    return _intents_by_id.get(intent_id)


def get_destination(destination_id: str) -> Destination | None:
    """None quando o destino não existe. O catálogo é fechado: nunca inferir."""
    return get_flows().destinos.get(destination_id)
