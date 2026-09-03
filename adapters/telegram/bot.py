"""Adaptador de Telegram — segundo canal do assistente, por long polling.

Este processo não decide nada. Ele traduz: pega o que chega do Telegram, monta
o corpo do `POST /v1/interpret`, e desenha a resposta no formato que o Telegram
entende. Toda a inteligência (sensibilidade, regras, embeddings, roteamento,
geração) mora no núcleo, e é ele quem responde igual em qualquer canal. Isso é
a seção 2 do CLAUDE.md: adaptadores são finos.

Por que long polling e não webhook: webhook exige URL pública com HTTPS válido,
o que numa apresentação em sala não existe. Com `getUpdates` o processo abre uma
conexão de saída e espera; funciona atrás de qualquer NAT, sem túnel e sem
domínio. As duas formas são mutuamente exclusivas na API do Telegram, então o
`deleteWebhook` no start é obrigatório: se sobrou webhook de um teste anterior,
`getUpdates` responde 409 e nada chega.

    python adapters/telegram/bot.py

Sem `TELEGRAM_BOT_TOKEN` o adaptador avisa e encerra limpo, sem stacktrace. É
requisito de avaliação (regra 3 do CLAUDE.md): o sistema roda sem chave nenhuma,
e a ausência do token desliga só este canal, nunca o núcleo.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from types import FrameType
from typing import Any, Callable

import httpx

RAIZ = Path(__file__).resolve().parent.parent.parent

log = logging.getLogger("telegram")

# Limites da própria API do Telegram, não escolhas nossas.
LIMITE_DA_MENSAGEM = 4096
LIMITE_DO_CALLBACK = 64  # bytes, não caracteres

# Quantos update_id guardar para não responder duas vezes à mesma mensagem.
JANELA_DE_DEDUPLICACAO = 512

# Espera entre tentativas quando a rede falha, em segundos. Cresce até o teto
# para não martelar a API do Telegram enquanto ela estiver fora.
BACKOFF_INICIAL_S = 1.0
BACKOFF_MAXIMO_S = 30.0

AVISO_SEM_TOKEN = (
    "TELEGRAM_BOT_TOKEN não definido: o adaptador de Telegram não vai subir.\n"
    "  Isso não é erro. O núcleo e a web funcionam sem ele.\n"
    "  Para ligar este canal: fale com o @BotFather no Telegram, crie um bot,\n"
    "  e coloque o token em core/.env como TELEGRAM_BOT_TOKEN=..."
)

BOAS_VINDAS = (
    "Oi! Sou o Guia Inteligente da Claro.\n\n"
    "Me conte com suas palavras o que você precisa e eu te levo direto ao "
    "lugar certo. Não precisa saber o nome do serviço nem escolher em menu.\n\n"
    "Por exemplo: <i>minha conta veio mais cara esse mês</i>"
)

SO_ENTENDO_TEXTO = (
    "Por enquanto eu só consigo ler mensagens de texto. "
    "Me escreve o que você precisa?"
)

NUCLEO_FORA = (
    "Não consegui completar seu atendimento agora. "
    "Tenta de novo em alguns instantes, por favor."
)


@dataclass(frozen=True)
class Config:
    token: str
    core_url: str
    core_timeout_s: float
    chats_liberados: frozenset[int]
    poll_timeout_s: int

    @staticmethod
    def do_ambiente() -> Config:
        return Config(
            token=os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
            core_url=os.environ.get("CORE_URL", "http://localhost:8000").rstrip("/"),
            core_timeout_s=int(os.environ.get("CORE_TIMEOUT_MS", "2500")) / 1000,
            chats_liberados=_ler_allowlist(
                os.environ.get("TELEGRAM_ALLOWED_CHATS", "")
            ),
            poll_timeout_s=int(os.environ.get("TELEGRAM_POLL_TIMEOUT_S", "30")),
        )


def _ler_allowlist(bruto: str) -> frozenset[int]:
    """Lista de chat_id separados por vírgula. Vazio significa todos liberados.

    Um bot de Telegram é público por natureza: qualquer pessoa que descubra o
    nome dele consegue mandar mensagem, e cada mensagem custa uma chamada ao
    núcleo e possivelmente uma ao Gemini. Numa entrega acadêmica com cota
    gratuita, isso é o suficiente para derrubar a demonstração.
    """
    ids: set[int] = set()
    for pedaco in bruto.split(","):
        pedaco = pedaco.strip()
        if not pedaco:
            continue
        try:
            ids.add(int(pedaco))
        except ValueError:
            log.warning("TELEGRAM_ALLOWED_CHATS: ignorando %r, não é um número", pedaco)
    return frozenset(ids)


def carregar_env() -> None:
    """Preenche variáveis ausentes a partir dos arquivos .env do projeto.

    O que já está no ambiente sempre vence: o arquivo é conveniência de
    desenvolvimento, não fonte de verdade. `core/.env` entra na lista porque é
    onde os segredos deste projeto já moram, e ter o token num segundo arquivo
    só cria a chance de editar o lugar errado.
    """
    for caminho in (Path(__file__).resolve().parent / ".env", RAIZ / "core" / ".env"):
        if not caminho.is_file():
            continue
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, _, valor = linha.partition("=")
            chave = chave.strip()
            if chave and chave not in os.environ:
                os.environ[chave] = valor.strip().strip("'\"")


# ---------------------------------------------------------------- Telegram


class Telegram:
    """Cliente mínimo da API do Telegram. Só os cinco métodos que usamos."""

    def __init__(self, token: str, poll_timeout_s: int) -> None:
        self._token = token
        self._base = f"https://api.telegram.org/bot{token}"
        self._poll_timeout_s = poll_timeout_s
        # O read do getUpdates tem que ser maior que o timeout do long polling,
        # senão o cliente desiste antes de o servidor responder e toda espera
        # vazia vira um erro de timeout.
        self._http = httpx.Client(timeout=httpx.Timeout(20.0, read=poll_timeout_s + 15))

    def fechar(self) -> None:
        self._http.close()

    def _mascarar(self, texto: str) -> str:
        """Tira o token de qualquer texto antes de ele virar log.

        Na API do Telegram o token vai DENTRO da URL, então toda mensagem de
        erro do httpx carrega o segredo junto. Sem isto, um 401 num terminal
        compartilhado ou num log de container entrega o bot inteiro para quem
        estiver lendo.
        """
        return texto.replace(self._token, "***")

    def _chamar(self, metodo: str, **params: Any) -> Any:
        try:
            resposta = self._http.post(f"{self._base}/{metodo}", json=params)
            resposta.raise_for_status()
            corpo = resposta.json()
        except httpx.HTTPError as erro:
            limpo = self._mascarar(f"{type(erro).__name__}: {erro}")
            raise RuntimeError(limpo) from None
        if not corpo.get("ok"):
            raise RuntimeError(f"{metodo}: {corpo.get('description', corpo)}")
        return corpo.get("result")

    def quem_sou_eu(self) -> dict[str, Any]:
        return self._chamar("getMe")

    def apagar_webhook(self) -> None:
        self._chamar("deleteWebhook")

    def buscar_updates(self, offset: int | None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "timeout": self._poll_timeout_s,
            # Pedir só o que sabemos tratar evita acordar à toa com edições de
            # mensagem, entradas em canal e reações.
            "allowed_updates": ["message", "callback_query"],
        }
        if offset is not None:
            params["offset"] = offset
        return self._chamar("getUpdates", **params) or []

    def digitando(self, chat_id: int) -> None:
        self._chamar("sendChatAction", chat_id=chat_id, action="typing")

    def enviar(
        self, chat_id: int, texto: str, teclado: dict[str, Any] | None = None
    ) -> None:
        params: dict[str, Any] = {
            "chat_id": chat_id,
            "text": texto[:LIMITE_DA_MENSAGEM],
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }
        if teclado is not None:
            params["reply_markup"] = teclado
        self._chamar("sendMessage", **params)

    def responder_callback(self, callback_id: str) -> None:
        # Sem isto o Telegram deixa o botão girando por vários segundos.
        self._chamar("answerCallbackQuery", callback_query_id=callback_id)

    def registrar_escolha(
        self, chat_id: int, message_id: int, texto: str, escolha: str
    ) -> None:
        """Reescreve o menu já respondido, marcando o que foi escolhido.

        Serve para duas coisas: a conversa passa a ler direito (o clique num
        botão não vira mensagem visível no Telegram) e o menu antigo perde os
        botões, então ninguém responde de novo a uma pergunta já encerrada.
        """
        self._chamar(
            "editMessageText",
            chat_id=chat_id,
            message_id=message_id,
            text=f"{texto}\n\n➤ <i>{escapar(escolha)}</i>"[:LIMITE_DA_MENSAGEM],
            parse_mode="HTML",
            link_preview_options={"is_disabled": True},
        )


# ------------------------------------------------------------- apresentação


def escapar(texto: str) -> str:
    """Escapa o mínimo exigido pelo parse_mode HTML do Telegram.

    O texto vem do Gemini ou do flows.json. Um `<` solto derruba a mensagem
    inteira com erro de parse, e o cliente não recebe nada.
    """
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def montar_mensagem(resposta: dict[str, Any]) -> str:
    """Resposta do núcleo virando texto de Telegram. Nada é acrescentado aqui.

    O encaminhamento é reproduzido campo a campo, como veio. A URL aparece
    escrita por extenso em vez de escondida atrás de um link: é o cliente
    conferindo para onde está sendo mandado, e é a forma mais rápida de flagrar
    endereço inventado numa demonstração.
    """
    partes = [escapar(resposta.get("reply") or "")]

    rota = resposta.get("routing")
    if rota:
        linhas = ["", "<b>Encaminhamento</b>", escapar(rota.get("label") or "")]
        if rota.get("protocol"):
            linhas.append(f"Protocolo <code>{escapar(rota['protocol'])}</code>")
        if rota.get("url"):
            linhas.append(escapar(rota["url"]))
        partes.append("\n".join(linhas))

    return "\n".join(partes)


def montar_teclado(opcoes: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    """Opções do contrato viram botões inline, uma por linha.

    O `callback_data` carrega o `id` da opção porque é isso que o núcleo casa
    primeiro ao resolver uma escolha. Se o id não couber nos 64 bytes da API,
    cai para o número da posição, que o núcleo também aceita. Assim o botão
    nunca fica sem resposta válida.
    """
    if not opcoes:
        return None

    linhas = []
    for posicao, opcao in enumerate(opcoes, start=1):
        dado = opcao["id"]
        if len(dado.encode("utf-8")) > LIMITE_DO_CALLBACK:
            dado = str(posicao)
        linhas.append([{"text": opcao["label"], "callback_data": dado}])
    return {"inline_keyboard": linhas}


def rotulo_do_botao(mensagem: dict[str, Any], dado: str) -> str:
    """Qual botão foi clicado, lendo o teclado da mensagem original."""
    teclado = (mensagem.get("reply_markup") or {}).get("inline_keyboard") or []
    for linha in teclado:
        for botao in linha:
            if botao.get("callback_data") == dado:
                return str(botao.get("text", dado))
    return dado


# ------------------------------------------------------------------ núcleo


class Nucleo:
    """A única saída deste processo em direção ao cérebro do sistema."""

    def __init__(self, url: str, timeout_s: float) -> None:
        self._url = f"{url}/v1/interpret"
        self._http = httpx.Client(timeout=timeout_s)

    def fechar(self) -> None:
        self._http.close()

    def interpretar(self, chat_id: int, texto: str) -> dict[str, Any] | None:
        """Devolve a resposta do contrato, ou None se o núcleo não respondeu.

        Quando falha, este adaptador NÃO tenta classificar por conta própria. O
        BFF da web faz isso porque é ele quem sustenta a interface principal e
        precisa continuar de pé numa demonstração; aqui seria copiar regra de
        negócio para dentro de um adaptador, exatamente o que a seção 2 do
        CLAUDE.md proíbe. Sem núcleo, este canal admite que não sabe.
        """
        corpo = {
            # O núcleo trata isto como identificador opaco: ele nunca separa o
            # canal do id. É só a convenção que mantém a conversa do Telegram
            # separada da conversa da web.
            "session_id": f"telegram:{chat_id}",
            "channel": "telegram",
            "text": texto,
        }
        try:
            resposta = self._http.post(self._url, json=corpo)
            resposta.raise_for_status()
            return resposta.json()
        except (httpx.HTTPError, json.JSONDecodeError) as erro:
            log.error("núcleo não respondeu (%s): %s", type(erro).__name__, erro)
            return None


# -------------------------------------------------------------------- loop


class Adaptador:
    def __init__(self, cfg: Config, telegram: Telegram, nucleo: Nucleo) -> None:
        self._cfg = cfg
        self._tg = telegram
        self._nucleo = nucleo
        self._vistos: deque[int] = deque(maxlen=JANELA_DE_DEDUPLICACAO)

    def ja_tratado(self, update_id: int) -> bool:
        """O offset já protege contra repetição; isto cobre a janela em que ele
        ainda não foi confirmado, quando um envio falha e o Telegram reentrega.
        """
        if update_id in self._vistos:
            return True
        self._vistos.append(update_id)
        return False

    def liberado(self, chat_id: int) -> bool:
        if not self._cfg.chats_liberados:
            return True
        if chat_id in self._cfg.chats_liberados:
            return True
        log.warning("chat %s fora da allowlist: ignorado", chat_id)
        return False

    def tratar(self, update: dict[str, Any]) -> None:
        if "callback_query" in update:
            self._tratar_botao(update["callback_query"])
        elif "message" in update:
            self._tratar_mensagem(update["message"])

    def _tratar_mensagem(self, mensagem: dict[str, Any]) -> None:
        chat_id = mensagem["chat"]["id"]
        if not self.liberado(chat_id):
            return

        texto = (mensagem.get("text") or "").strip()
        if not texto:
            self._tg.enviar(chat_id, SO_ENTENDO_TEXTO)
            return
        if texto.startswith("/start"):
            self._tg.enviar(chat_id, BOAS_VINDAS)
            return

        self._conversar(chat_id, texto)

    def _tratar_botao(self, callback: dict[str, Any]) -> None:
        self._tg.responder_callback(callback["id"])

        mensagem = callback.get("message") or {}
        chat_id = mensagem.get("chat", {}).get("id")
        dado = callback.get("data")
        if chat_id is None or not dado or not self.liberado(chat_id):
            return

        rotulo = rotulo_do_botao(mensagem, dado)
        try:
            self._tg.registrar_escolha(
                chat_id, mensagem["message_id"], mensagem.get("text") or "", rotulo
            )
        except (httpx.HTTPError, RuntimeError) as erro:
            # Falhar aqui é cosmético: o menu antigo continua com botões. A
            # escolha em si não pode ser perdida por causa disso.
            log.warning("não consegui atualizar o menu: %s", erro)

        # A escolha entra como turno normal, exatamente como se o cliente
        # tivesse digitado. É o núcleo que resolve qual opção é essa.
        self._conversar(chat_id, dado)

    def _conversar(self, chat_id: int, texto: str) -> None:
        try:
            self._tg.digitando(chat_id)
        except (httpx.HTTPError, RuntimeError):
            pass  # enfeite, não bloqueia o atendimento

        resposta = self._nucleo.interpretar(chat_id, texto)
        if resposta is None:
            self._tg.enviar(chat_id, NUCLEO_FORA)
            return

        self._tg.enviar(
            chat_id,
            montar_mensagem(resposta),
            montar_teclado(resposta.get("options")),
        )
        log.info(
            "chat=%s intent=%s state=%s %sms",
            chat_id,
            resposta.get("intent") or "-",
            resposta.get("state"),
            resposta.get("latency_ms"),
        )


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    # O httpx registra cada requisição em INFO, com a URL inteira. Como o token
    # do Telegram viaja na URL, isso encheria o terminal e vazaria o segredo a
    # cada rodada de espera.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    carregar_env()
    cfg = Config.do_ambiente()

    if not cfg.token:
        log.warning(AVISO_SEM_TOKEN)
        return 0

    telegram = Telegram(cfg.token, cfg.poll_timeout_s)
    nucleo = Nucleo(cfg.core_url, cfg.core_timeout_s)

    try:
        eu = telegram.quem_sou_eu()
    except (httpx.HTTPError, RuntimeError) as erro:
        # Token presente mas inválido é erro de configuração de verdade, e
        # merece código de saída diferente de "não configurado".
        log.error("o Telegram recusou o token: %s", erro)
        telegram.fechar()
        nucleo.fechar()
        return 1

    telegram.apagar_webhook()
    log.info("conectado como @%s", eu.get("username", "?"))
    log.info("núcleo em %s", cfg.core_url)
    log.info(
        "allowlist: %s",
        ", ".join(str(c) for c in sorted(cfg.chats_liberados)) or "aberta a todos",
    )

    parar = False

    def encerrar(_sinal: int, _quadro: FrameType | None) -> None:
        """Primeiro pedido encerra com ordem; o segundo encerra na hora.

        O laço passa quase todo o tempo parado dentro do `getUpdates`, esperando
        o Telegram por até 30 segundos. O sinal chega, marca a saída, e o
        processo VOLTA a esperar a conexão terminar: quem apertou Ctrl+C fica
        olhando um terminal que não responde e aperta de novo, sem efeito.
        Devolver o comportamento padrão do sistema no segundo pedido resolve
        isso sem inventar nada.
        """
        nonlocal parar
        if parar:
            log.warning("encerrando agora, sem terminar a espera")
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
            raise KeyboardInterrupt
        parar = True
        log.info(
            "encerrando quando esta espera terminar (ate %ss). "
            "Ctrl+C de novo sai na hora.",
            cfg.poll_timeout_s,
        )

    signal.signal(signal.SIGINT, encerrar)
    signal.signal(signal.SIGTERM, encerrar)

    adaptador = Adaptador(cfg, telegram, nucleo)
    offset: int | None = None
    espera = BACKOFF_INICIAL_S

    try:
        while not parar:
            try:
                updates = telegram.buscar_updates(offset)
                espera = BACKOFF_INICIAL_S
            except (httpx.HTTPError, RuntimeError) as erro:
                log.warning(
                    "falha ao buscar mensagens: %s (nova tentativa em %.0fs)",
                    erro,
                    espera,
                )
                if _dormir(espera, lambda: parar):
                    break
                espera = min(espera * 2, BACKOFF_MAXIMO_S)
                continue

            for update in updates:
                # O offset avança mesmo se o tratamento falhar: uma mensagem que
                # quebra o adaptador não pode ser reentregue para sempre,
                # travando a fila atrás dela.
                offset = update["update_id"] + 1
                if adaptador.ja_tratado(update["update_id"]):
                    continue
                try:
                    adaptador.tratar(update)
                except Exception:
                    log.exception("erro ao tratar update %s", update["update_id"])
    except KeyboardInterrupt:
        # Segundo Ctrl+C. Sair aqui, e não deixar estourar, mantém o encerramento
        # com uma linha de log em vez de um rastro de pilha.
        pass

    telegram.fechar()
    nucleo.fechar()
    log.info("adaptador encerrado")
    return 0


def _dormir(segundos: float, cancelado: Callable[[], bool]) -> bool:
    """Espera fatiada, para o Ctrl-C não ficar preso num backoff longo."""
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        if cancelado():
            return True
        time.sleep(0.2)
    return cancelado()


if __name__ == "__main__":
    sys.exit(main())
