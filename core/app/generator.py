"""Etapa 5 do pipeline — geração ancorada.

O Gemini entra aqui como REDATOR, nunca como decisor (regra 1 do CLAUDE.md).
Quando esta função é chamada, o destino já foi decidido por código
determinístico e o roteiro já veio pronto do flows.json. O modelo só reescreve
aquele texto no tom de voz da marca.

Degradação graciosa (nível 2 do documento de fluxo): qualquer falha — sem chave,
tempo esgotado, erro da API, resposta vazia, ou resposta que inventou dado —
devolve o texto canônico do roteiro. Este módulo NUNCA levanta exceção; um
problema no LLM não pode virar erro para o cliente.

É a única parte assíncrona do pipeline. O resto segue síncrono porque é
CPU-bound; aqui a espera é de rede.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

import httpx

from .config import settings
from .contract import ReplySource, Routing
from .flows import Intent, Script

ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
)

MAX_LINHAS = 6

INSTRUCAO_DE_SISTEMA = """\
Você é o redator do Guia Inteligente da Claro. Sua única tarefa é reescrever, no \
tom de voz da marca, um roteiro de atendimento que já vem pronto.

TOM DE VOZ
- Claro e direto. Frases curtas.
- Empático sem ser piegas. Trate a pessoa por "você".
- Sem jargão técnico, sem linguagem corporativa, sem emoji.

REGRAS ABSOLUTAS
- Reescreva APENAS o conteúdo recebido. Não acrescente informação nova.
- Nunca invente passo, endereço de site, valor, prazo ou número de protocolo.
  Se o roteiro não traz um dado, esse dado não existe.
- Os DADOS FIXOS abaixo são literais: copie exatamente ou omita. Nunca altere.
- Você orienta, não executa. Não prometa fazer nada que exija login, senha ou
  acesso à conta da pessoa.
- No máximo {max_linhas} linhas.
- Responda somente com o texto final: sem título, sem aspas, sem comentário seu.\
"""


def render_canonical(roteiro: Script) -> str:
    """Texto do roteiro sem nenhum LLM no meio. É o piso da degradação."""
    passos = "\n".join(f"{i}. {passo}" for i, passo in enumerate(roteiro.passos, 1))
    return (
        f"{roteiro.reconhecimento} {roteiro.resumo}\n\n{passos}\n\n{roteiro.fechamento}"
    )


def _montar_pedido(
    intent: Intent, routing: Routing, roteiro: Script, history: Sequence[str]
) -> str:
    passos = "\n".join(f"- {passo}" for passo in roteiro.passos)
    dados_fixos = [f"Destino: {routing.label}"]
    if routing.url:
        dados_fixos.append(f"Endereço: {routing.url}")
    if routing.protocol:
        dados_fixos.append(f"Protocolo: {routing.protocol}")

    partes = [f"ASSUNTO: {intent.nome}", "", "ROTEIRO A REESCREVER:"]
    partes += [
        f"Reconhecimento: {roteiro.reconhecimento}",
        f"Resumo: {roteiro.resumo}",
        "Passos:",
        passos,
        f"Fechamento: {roteiro.fechamento}",
        "",
        "DADOS FIXOS (literais, não altere):",
        "\n".join(dados_fixos),
    ]
    if history:
        anteriores = "\n".join(f"- {t}" for t in list(history)[-3:])
        partes += [
            "",
            "CONTEXTO (mensagens anteriores da pessoa, só para o tom; não responda a elas):",
            anteriores,
        ]
    return "\n".join(partes)


async def _chamar_gemini(instrucao: str, pedido: str, timeout_s: float) -> str | None:
    """Isolada para o teste conseguir substituir sem tocar no resto."""
    url = ENDPOINT.format(modelo=settings.gemini_model)
    corpo = {
        "system_instruction": {"parts": [{"text": instrucao}]},
        "contents": [{"role": "user", "parts": [{"text": pedido}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 400},
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_s)) as cliente:
        resposta = await cliente.post(
            url,
            json=corpo,
            headers={"x-goog-api-key": settings.gemini_api_key},
        )
        resposta.raise_for_status()
        dados = resposta.json()

    candidatos = dados.get("candidates") or []
    if not candidatos:
        return None
    partes = (candidatos[0].get("content") or {}).get("parts") or []
    texto = "".join(parte.get("text", "") for parte in partes).strip()
    return texto or None


_URL = re.compile(r"https?://\S+")
_PROTOCOLO = re.compile(r"\b[A-Z]{3}(?:-[A-Z]{3})?-\d{4}-\d{4,6}\b")


def _ancorado(texto: str, routing: Routing) -> bool:
    """O texto só cita endereço e protocolo que nós demos. Nada inventado.

    É a rede de segurança da regra 1: mesmo instruído, o modelo pode alucinar
    uma URL. Se citar qualquer coisa que não veio de nós, a saída é descartada.
    """
    for encontrado in _URL.findall(texto):
        limpo = encontrado.rstrip(".,;:)]}\"'")
        if routing.url is None or limpo != routing.url:
            return False
    for encontrado in _PROTOCOLO.findall(texto):
        if routing.protocol is None or encontrado != routing.protocol:
            return False
    return len(texto.splitlines()) <= MAX_LINHAS * 2


async def generate(
    intent: Intent,
    routing: Routing,
    roteiro: Script,
    history: Sequence[str] = (),
) -> tuple[str, ReplySource]:
    """Texto da resposta e de onde ele veio. Nunca levanta exceção."""
    canonico = render_canonical(roteiro)

    # Sem chave o módulo nem tenta: é requisito de avaliação que o sistema
    # funcione inteiro sem nenhuma credencial (regra 3 do CLAUDE.md).
    if not settings.gemini_api_key:
        return canonico, ReplySource.TEMPLATE

    instrucao = INSTRUCAO_DE_SISTEMA.format(max_linhas=MAX_LINHAS)
    pedido = _montar_pedido(intent, routing, roteiro, history)

    try:
        texto = await _chamar_gemini(instrucao, pedido, settings.llm_timeout_ms / 1000)
    except Exception:
        # Timeout, erro de rede, HTTP 4xx/5xx, JSON quebrado — o motivo não muda
        # a decisão: cai para o texto canônico e o atendimento segue.
        return canonico, ReplySource.TEMPLATE

    if not texto or not _ancorado(texto, routing):
        return canonico, ReplySource.TEMPLATE

    return texto, ReplySource.GENERATIVE
