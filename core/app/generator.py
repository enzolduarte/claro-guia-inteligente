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

import asyncio
import re
import threading
from collections.abc import Awaitable, Callable, Sequence

import httpx

from .config import settings
from .contract import ReplySource
from .flows import Intent, Script, get_flows

ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
)

MAX_LINHAS = 6

# Texto já redigido, por (tipo, intenção). O que o Gemini escreve aqui não
# depende da mensagem do cliente — depende só da intenção —, então gerar de
# novo a cada atendimento seria pagar latência e cota por um texto idêntico.
# Medido em 31/08/2026: a chamada tem mediana de 3s e cauda de 10s; sem cache,
# metade dos turnos cairia no texto canônico e a conversa ficaria alternando
# entre fluida e robótica.
_redigidos: dict[tuple[str, str], str] = {}

# Redações em andamento, para pedidos simultâneos do mesmo texto não
# dispararem chamadas duplicadas. O Event avisa quando a redação terminou.
_em_andamento: dict[tuple[str, str], threading.Event] = {}
_trava = threading.Lock()

# Quanto o caminho da RESPOSTA espera pela redação. Curto de propósito: o BFF
# corta a chamada ao núcleo em 2,5s (CORE_TIMEOUT_MS), então esperar mais que
# isso aqui derruba a conversa inteira no fallback do BFF. Se o Gemini não
# couber no orçamento, o cliente recebe o texto canônico e a redação termina
# em segundo plano — o próximo já a recebe pronta.
ORCAMENTO_SINCRONO_S = 1.5

INSTRUCAO_DE_PERGUNTA = """\
Você é o redator do Guia Inteligente da Claro. Reescreva uma pergunta de \
atendimento no tom da marca.

TOM: clara, curta, direta. Trate por "você". Sem jargão, sem formalidade \
excessiva, sem emoji.

REGRAS ABSOLUTAS
- A pessoa vê as alternativas como botões ao lado da pergunta. NÃO liste, não
  numere e não repita as alternativas dentro do texto.
- A pergunta precisa fazer sentido para EXATAMENTE essas alternativas. Não
  troque a pergunta por outra, nem invente caminho que não está na lista.
- No máximo 2 linhas. Responda só com a pergunta final, sem aspas.\
"""

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
- NUNCA use rótulos como "Destino:", "Passos:" ou "Resumo:" — o roteiro chega
  rotulado só para você se orientar; a pessoa não pode ver essa estrutura.
- NUNCA escreva endereço de site nem número de protocolo. A interface mostra
  os dois ao lado da sua resposta; repetir polui o texto.
- Escreva em prosa corrida, no máximo {max_linhas} linhas. Encadeie as ideias
  em frases; não faça lista nem enumere passos.
- Você orienta, não executa. Não prometa fazer nada que exija login, senha ou
  acesso à conta da pessoa.
- Responda somente com o texto final: sem título, sem aspas, sem comentário seu.\
"""


def render_canonical(roteiro: Script) -> str:
    """Texto do roteiro sem nenhum LLM no meio. É o piso da degradação."""
    passos = "\n".join(f"{i}. {passo}" for i, passo in enumerate(roteiro.passos, 1))
    return (
        f"{roteiro.reconhecimento} {roteiro.resumo}\n\n{passos}\n\n{roteiro.fechamento}"
    )


def _montar_pedido(intent: Intent, roteiro: Script) -> str:
    passos = "\n".join(f"- {passo}" for passo in roteiro.passos)

    # O roteamento NÃO entra no prompt. O endereço, o rótulo do destino e o
    # protocolo já viajam no objeto `routing` e são apresentados pela interface.
    # Repetir aqui foi testado duas vezes e falhou das duas: primeiro o modelo
    # copiou os rótulos ("Destino: ..."), depois copiou a frase em que eu os
    # embrulhei ("o protocolo do atendimento é ..."). Ele reproduz o formato que
    # recebe. Não mandar é a única forma de não ver vazar.
    partes = [
        f"ASSUNTO: {intent.nome}",
        "",
        "ROTEIRO A REESCREVER (a estrutura abaixo é sua, não da pessoa):",
        f"Reconhecimento: {roteiro.reconhecimento}",
        f"Resumo: {roteiro.resumo}",
        "Passos:",
        passos,
        f"Fechamento: {roteiro.fechamento}",
    ]
    return "\n".join(partes)


async def _com_prazo(tarefa: Awaitable[str | None]) -> str | None:
    """Prazo de relógio sobre a chamada inteira.

    O timeout do httpx vale por tentativa de conexão, não pelo todo: quando o
    DNS devolve vários endereços, ele tenta um a um e o total vira um múltiplo
    do limite. Medido em 31/08/2026: uma resposta levou 25 segundos com o
    limite em 8. Aqui o prazo é do relógio e não tem como esticar.
    """
    return await asyncio.wait_for(tarefa, timeout=settings.llm_timeout_ms / 1000)


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
# Rótulo no começo de uma linha é a estrutura do prompt vazando para a resposta.
_ROTULO = re.compile(
    r"^\s*(destino|endere[çc]o|protocolo|resumo|passos?|reconhecimento|fechamento|assunto)\s*:",
    re.IGNORECASE | re.MULTILINE,
)


def _ancorado(texto: str) -> bool:
    """O texto é só prosa: sem endereço, sem protocolo, sem rótulo do prompt.

    Como o roteamento não entra no prompt, o modelo não tem de onde tirar um
    endereço ou protocolo — se algum aparecer, ele inventou, e a regra 1 do
    CLAUDE.md diz que isso não pode chegar ao cliente. A checagem de rótulo
    pega a estrutura do roteiro vazando. Qualquer uma descarta a saída.
    """
    if _URL.search(texto) or _PROTOCOLO.search(texto):
        return False
    if _ROTULO.search(texto):
        return False
    return len(texto.splitlines()) <= MAX_LINHAS * 2


async def generate(intent: Intent, roteiro: Script) -> tuple[str, ReplySource]:
    """Texto da resposta e de onde ele veio. Nunca levanta exceção.

    O texto é guardado por intenção. Ele não depende da mensagem do cliente —
    o roteiro é o mesmo — então redigir de novo a cada atendimento pagaria
    latência e cota por um resultado idêntico.
    """
    canonico = render_canonical(roteiro)

    async def montar() -> str | None:
        # Timeout, erro de rede, HTTP 4xx/5xx, JSON quebrado, texto que não
        # passou na ancoragem — qualquer falha devolve None e o texto canônico
        # continua valendo. Nada disso vira exceção para quem chamou.
        instrucao = INSTRUCAO_DE_SISTEMA.format(max_linhas=MAX_LINHAS)
        pedido = _montar_pedido(intent, roteiro)
        limite = settings.llm_timeout_ms / 1000
        texto = await _com_prazo(_chamar_gemini(instrucao, pedido, limite))
        return texto if texto and _ancorado(texto) else None

    texto = _garantir_redacao(("roteiro", intent.id), montar)
    if texto is None:
        return canonico, ReplySource.TEMPLATE
    return texto, ReplySource.GENERATIVE


def _pergunta_valida(texto: str) -> bool:
    """Pergunta é frase curta: sem endereço, sem protocolo, sem lista numerada."""
    if _URL.search(texto) or _PROTOCOLO.search(texto) or _ROTULO.search(texto):
        return False
    if re.search(r"^\s*\d+\s*[.)]", texto, re.MULTILINE):
        return False
    return len(texto.splitlines()) <= 3


async def _redigir_pergunta(chave: tuple[str, str], pedido: str) -> str | None:
    """Chama o Gemini uma vez por chave e guarda. None se não deu."""

    async def montar() -> str | None:
        limite = settings.llm_timeout_ms / 1000
        texto = await _com_prazo(_chamar_gemini(INSTRUCAO_DE_PERGUNTA, pedido, limite))
        return texto if texto and _pergunta_valida(texto) else None

    return _garantir_redacao(chave, montar)


async def gerar_pergunta_de_clarificacao(
    intent: Intent, opcoes: Sequence[str]
) -> tuple[str, ReplySource] | None:
    """Reescreve a pergunta do flows.json mantendo-a coerente com as opções."""
    if intent.clarificacao is None:
        return None
    alternativas = "\n".join(f"- {rotulo}" for rotulo in opcoes)
    pedido = (
        f"PERGUNTA ATUAL: {intent.clarificacao.pergunta}\n\n"
        f"ALTERNATIVAS que a pessoa verá como botões (não as escreva no texto):\n"
        f"{alternativas}"
    )
    texto = await _redigir_pergunta(("clarificacao", intent.id), pedido)
    return (texto, ReplySource.GENERATIVE) if texto else None


async def gerar_confirmacao(intent: Intent) -> tuple[str, ReplySource] | None:
    """Pergunta de sim/não para a banda média, no lugar do rótulo de catálogo."""
    pedido = (
        f"Preciso confirmar com a pessoa se o assunto dela é este.\n"
        f"ASSUNTO (rótulo interno, não use estas palavras): {intent.nome}\n"
        f"O QUE SIGNIFICA: {intent.descricao}\n\n"
        f"ALTERNATIVAS que a pessoa verá como botões: Sim / Não.\n"
        f"Faça uma pergunta de sim ou não que descubra se é isso."
    )
    texto = await _redigir_pergunta(("confirmacao", intent.id), pedido)
    return (texto, ReplySource.GENERATIVE) if texto else None


def limpar_cache() -> None:
    _redigidos.clear()
    with _trava:
        _em_andamento.clear()


def aquecer_tudo() -> None:
    """Manda o Gemini redigir todos os textos, uma vez. Roda no boot.

    São três textos por intenção — o roteiro, a confirmação de banda média e,
    quando existe, a pergunta de clarificação. Nenhum depende da mensagem do
    cliente, então dá para escrever todos antes de o primeiro chegar.

    Sem isto, o primeiro atendimento de cada assunto esperaria a chamada de
    rede e provavelmente receberia o texto canônico, deixando a conversa
    alternando entre fluida e robótica.
    """
    if not settings.gemini_api_key:
        return
    # Sequencial e paciente: disparar tudo em paralelo estoura a cota da API
    # (medido em 02/09: 64 de 78 chamadas paralelas voltaram HTTP 429).
    for intent in get_flows().intencoes:
        for _tentativa in range(2):
            try:
                asyncio.run(generate(intent, intent.roteiro))
                asyncio.run(gerar_confirmacao(intent))
                if intent.clarificacao is not None:
                    asyncio.run(
                        gerar_pergunta_de_clarificacao(
                            intent, [o.label for o in intent.clarificacao.opcoes]
                        )
                    )
                break
            except Exception:
                # Aquecimento é melhor-esforço: o que não vier agora vem no uso.
                continue


def textos_redigidos() -> int:
    return len(_redigidos)


def textos_esperados() -> int:
    intencoes = get_flows().intencoes
    return 2 * len(intencoes) + sum(1 for i in intencoes if i.clarificacao is not None)


def _garantir_redacao(
    chave: tuple[str, str],
    montar: "Callable[[], Awaitable[str | None]]",
    espera_s: float = ORCAMENTO_SINCRONO_S,
) -> str | None:
    """Devolve o texto redigido, esperando no máximo `espera_s`.

    A redação roda numa thread própria e continua mesmo depois de a espera
    acabar — o resultado fica guardado para o próximo pedido. É isto que
    mantém o LLM fora do caminho crítico da resposta: o pior caso do cliente
    é receber o texto canônico uma vez.
    """
    if chave in _redigidos:
        return _redigidos[chave]
    if not settings.gemini_api_key:
        return None

    with _trava:
        evento = _em_andamento.get(chave)
        if evento is None:
            evento = threading.Event()
            _em_andamento[chave] = evento

            def trabalhar() -> None:
                try:
                    texto = asyncio.run(montar())
                    if texto:
                        _redigidos[chave] = texto
                except Exception:
                    pass
                finally:
                    with _trava:
                        _em_andamento.pop(chave, None)
                    evento.set()

            threading.Thread(target=trabalhar, daemon=True).start()

    evento.wait(espera_s)
    return _redigidos.get(chave)
