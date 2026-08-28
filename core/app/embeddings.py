"""Etapa 3 do pipeline — similaridade semântica.

O desenho aqui é o que cumpre o requisito de latência da seção 8 do CLAUDE.md:

- O modelo é carregado UMA vez, quando o servidor liga. Nunca por requisição.
- Os 105 exemplos do catálogo são embedados no boot e guardados como UMA matriz
  numpy `(105, dim)`. Nunca são recalculados.
- Os vetores são L2-normalizados no boot. Com vetores de norma 1, o cosseno vira
  produto escalar puro — sem divisão por norma a cada chamada.
- Por requisição: UM encode da mensagem e UM produto de matriz. Nenhum laço
  Python sobre exemplos.

O texto NÃO passa por normalize() aqui. Aquela função existe para as camadas de
palavra-chave; o modelo foi treinado em texto natural, com acento e pontuação.
(Medido neste catálogo: não muda o resultado, porque os exemplos do flows.json
já são escritos sem acento.)
"""

from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from .config import settings
from .flows import get_flows

_model: SentenceTransformer | None = None
_catalog: np.ndarray | None = None  # (n_exemplos, dim), L2-normalizada
_intent_ids: np.ndarray | None = None  # (n_exemplos,), paralelo à matriz

# Exemplos das opções de clarificação, uma matriz por intenção que clarifica.
# Pré-computados no boot pelo mesmo motivo do catálogo principal: resolver a
# escolha do usuário não pode custar um encode de catálogo por mensagem.
_option_catalogs: dict[str, tuple[np.ndarray, np.ndarray]] = {}


def load_model() -> None:
    """Carrega o modelo e pré-computa a matriz do catálogo. Chamado no lifespan."""
    global _model, _catalog, _intent_ids

    model = SentenceTransformer(settings.embedding_model)
    flows = get_flows()

    examples: list[str] = []
    intent_ids: list[str] = []
    for intent in flows.intencoes:
        for example in intent.exemplos:
            examples.append(example)
            intent_ids.append(intent.id)

    matrix = model.encode(
        examples,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    option_catalogs: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for intent in flows.intencoes:
        if intent.clarificacao is None:
            continue
        option_texts: list[str] = []
        option_ids: list[str] = []
        for option in intent.clarificacao.opcoes:
            for example in option.exemplos:
                option_texts.append(example)
                option_ids.append(option.id)
        if not option_texts:
            continue
        option_matrix = model.encode(
            option_texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        option_catalogs[intent.id] = (
            np.ascontiguousarray(option_matrix, dtype=np.float32),
            np.array(option_ids),
        )

    _model = model
    _catalog = np.ascontiguousarray(matrix, dtype=np.float32)
    _intent_ids = np.array(intent_ids)
    _option_catalogs.clear()
    _option_catalogs.update(option_catalogs)


def is_ready() -> bool:
    return _model is not None and _catalog is not None


def catalog_shape() -> tuple[int, int]:
    if _catalog is None:
        raise RuntimeError("load_model() ainda não foi chamado.")
    return _catalog.shape[0], _catalog.shape[1]


def score(texto: str) -> tuple[str, float] | None:
    """(intent_id, similaridade) do exemplo mais próximo, ou None sem modelo.

    Devolver None em vez de levantar é deliberado: sem o modelo carregado o
    classificador degrada para as camadas determinísticas em vez de derrubar
    o atendimento.
    """
    if _model is None or _catalog is None or _intent_ids is None:
        return None

    query = _model.encode(
        [texto],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )[0]

    # Ambos os lados têm norma 1, então o produto escalar JÁ é o cosseno.
    similarities = _catalog @ query.astype(np.float32)
    best = int(np.argmax(similarities))
    return str(_intent_ids[best]), float(similarities[best])


def score_options(intent_id: str, texto: str) -> tuple[str, float] | None:
    """(option_id, similaridade) contra os exemplos das opções da intenção.

    None quando o modelo não está carregado ou a intenção não tem clarificação.
    """
    catalog = _option_catalogs.get(intent_id)
    if _model is None or catalog is None:
        return None

    matrix, option_ids = catalog
    query = _model.encode(
        [texto],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )[0]
    similarities = matrix @ query.astype(np.float32)
    best = int(np.argmax(similarities))
    return str(option_ids[best]), float(similarities[best])
