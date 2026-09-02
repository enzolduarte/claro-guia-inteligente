"""Memória de conversa e o fluxo de clarificação (RF004).

A sessão vive em memória, num dicionário. Isso é escolha, não limitação: o
CLAUDE.md lista banco gerenciado e cache distribuído como anti-objetivos, e uma
conversa de atendimento não sobrevive a um restart de propósito — ninguém quer
retomar um menu de três opções vinte minutos depois.

A chave é o `session_id` do contrato, no formato `{canal}:{id_externo}`. O
núcleo NUNCA interpreta essa string: para ele é um identificador opaco. É o que
mantém o adaptador de canal fino, como manda a seção 2.

A tabela de transições é a da seção 7 do documento de fluxo. Transição inválida
levanta exceção porque é bug de código, não caso de negócio — a distinção está
na seção 7 do CLAUDE.md.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .contract import Option, State
from .embeddings import score_options
from .flows import Intent
from .normalize import normalize

# Para aceitar uma escolha por semelhança, os DOIS critérios têm que passar.
# Medido em 30/08/2026 sobre as opções do PLANO, com o modelo em uso:
#   escolhas de verdade ("quero pagar menos", "mais velocidade", ...):
#       score mínimo 0,773  ·  margem mínima 0,328
#   ruído ("ola", "obrigado", "talvez", "hmm", "certo", "sim"):
#       score máximo 0,704  ·  margem máxima 0,250
# Sem a margem, "obrigado" virava escolha de plano com 0,704 — o sistema
# fechava um destino que o cliente nunca pediu. TROCAR DE MODELO EXIGE REFAZER
# ESTA MEDIÇÃO: os números não são comparáveis entre modelos.
SCORE_MINIMO_DA_ESCOLHA = 0.72
MARGEM_MINIMA_DA_ESCOLHA = 0.28

TTL = timedelta(minutes=30)
MAX_TENTATIVAS_CLARIFICACAO = 2
TAMANHO_HISTORICO = 6

TRANSICOES: dict[State, frozenset[State]] = {
    State.AGUARDANDO: frozenset({State.PROCESSANDO}),
    State.PROCESSANDO: frozenset(
        {State.CLARIFICANDO, State.RESPONDENDO, State.ESCALANDO, State.AGUARDANDO}
    ),
    State.CLARIFICANDO: frozenset({State.PROCESSANDO, State.ROTEANDO}),
    State.RESPONDENDO: frozenset({State.ROTEANDO}),
    State.ROTEANDO: frozenset({State.ENCERRADO, State.AGUARDANDO}),
    State.ESCALANDO: frozenset({State.ENCERRADO}),
    State.ENCERRADO: frozenset({State.AGUARDANDO}),
}

# Estados de descanso: de onde a próxima mensagem do usuário pode partir.
TERMINAIS = (State.ROTEANDO, State.ESCALANDO, State.ENCERRADO)

CONFIRMACAO = "confirmacao"
OPCOES = "opcoes"

_SIM = frozenset(
    {"sim", "isso", "exato", "exatamente", "claro", "correto", "aham", "uhum", "s"}
)
_NAO = frozenset({"nao", "errado", "negativo", "n"})


class InvalidTransition(RuntimeError):
    """Transição fora da tabela. É bug — nunca resultado de entrada do usuário."""


@dataclass(frozen=True)
class Turn:
    texto: str
    state: State
    intent: str | None


@dataclass
class Session:
    session_id: str
    state: State = State.AGUARDANDO
    pending_intent: str | None = None
    offered_options: list[Option] = field(default_factory=list)
    clarification_kind: str | None = None
    clarify_attempts: int = 0
    history: deque[Turn] = field(
        default_factory=lambda: deque(maxlen=TAMANHO_HISTORICO)
    )
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def abrir_clarificacao(
        self, intent_id: str, options: list[Option], kind: str
    ) -> None:
        self.pending_intent = intent_id
        self.offered_options = list(options)
        self.clarification_kind = kind

    def fechar_clarificacao(self) -> None:
        self.pending_intent = None
        self.offered_options = []
        self.clarification_kind = None
        self.clarify_attempts = 0

    def registrar(self, texto: str, intent: str | None) -> None:
        self.history.append(Turn(texto=texto, state=self.state, intent=intent))


class SessionStore:
    """Sessões em memória, com expiração preguiçosa."""

    def __init__(self, ttl: timedelta = TTL) -> None:
        self._sessions: dict[str, Session] = {}
        self._ttl = ttl

    def get(self, session_id: str) -> Session:
        self._expirar()
        sessao = self._sessions.get(session_id)
        if sessao is None:
            sessao = Session(session_id=session_id)
            self._sessions[session_id] = sessao
        return sessao

    def _expirar(self) -> None:
        """Varre na leitura. Sem thread de limpeza para manter isto simples."""
        limite = datetime.now(timezone.utc) - self._ttl
        vencidas = [sid for sid, s in self._sessions.items() if s.updated_at < limite]
        for sid in vencidas:
            del self._sessions[sid]

    def transicionar(self, sessao: Session, novo: State) -> None:
        permitidos = TRANSICOES[sessao.state]
        if novo not in permitidos:
            raise InvalidTransition(
                f"sessão {sessao.session_id}: {sessao.state.value} -> {novo.value} "
                f"não está na tabela. Válidos daqui: "
                f"{', '.join(sorted(e.value for e in permitidos))}"
            )
        sessao.state = novo
        sessao.updated_at = datetime.now(timezone.utc)

    def assentar(self, sessao: Session) -> None:
        """Traz um estado terminal de volta a AGUARDANDO, um passo por vez.

        A tabela não liga ROTEANDO a PROCESSANDO direto: é preciso passar por
        AGUARDANDO. Sem isto, o segundo turno de uma conversa quebraria.
        """
        if sessao.state is State.ESCALANDO:
            self.transicionar(sessao, State.ENCERRADO)
        if sessao.state in (State.ROTEANDO, State.ENCERRADO):
            self.transicionar(sessao, State.AGUARDANDO)

    def limpar(self) -> None:
        self._sessions.clear()

    def __len__(self) -> int:
        return len(self._sessions)


STORE = SessionStore()


def resolver_escolha(sessao: Session, texto: str) -> str | None:
    """Qual opção o usuário escolheu, ou None se não deu para saber.

    Três caminhos, nesta ordem: o id literal, o número da lista, e por último a
    similaridade com os `exemplos` da opção. O número vem antes da similaridade
    porque '1' tem semelhança semântica alta com qualquer coisa curta.
    """
    normalizado = normalize(texto)
    if not normalizado or not sessao.offered_options:
        return None

    ids = [opcao.id for opcao in sessao.offered_options]

    for opcao_id in ids:
        if normalizado == normalize(opcao_id):
            return opcao_id

    if normalizado.isdigit():
        indice = int(normalizado) - 1
        if 0 <= indice < len(ids):
            return ids[indice]

    if sessao.clarification_kind == CONFIRMACAO:
        return _resolver_sim_nao(normalizado, ids)

    if sessao.pending_intent is None:
        return None
    pontuado = score_options(sessao.pending_intent, texto)
    if pontuado is None:
        return None

    opcao_id, similaridade, margem = pontuado
    escolheu = (
        opcao_id in ids
        and similaridade >= SCORE_MINIMO_DA_ESCOLHA
        and margem >= MARGEM_MINIMA_DA_ESCOLHA
    )
    return opcao_id if escolheu else None


def _resolver_sim_nao(normalizado: str, ids: list[str]) -> str | None:
    palavras = set(normalizado.split())
    disse_sim = bool(palavras & _SIM)
    disse_nao = bool(palavras & _NAO)
    if disse_sim == disse_nao:  # nenhum dos dois, ou os dois juntos
        return None
    escolhido = "sim" if disse_sim else "nao"
    return escolhido if escolhido in ids else None


def opcoes_de_clarificacao(intent: Intent) -> list[Option]:
    """Opções do flows.json viram opções do contrato. Sem nada inventado aqui."""
    if intent.clarificacao is None:
        return []
    return [
        Option(id=opcao.id, label=opcao.label) for opcao in intent.clarificacao.opcoes
    ]


def opcoes_de_confirmacao() -> list[Option]:
    return [
        Option(id="sim", label="Sim, é isso"),
        Option(id="nao", label="Não, é outra coisa"),
    ]


def texto_da_clarificacao(intent: Intent) -> str:
    """Só a pergunta. As alternativas viajam no campo `options` do contrato.

    Enumerar no texto duplicava o que a interface já mostra como botões, e era
    o que dava à conversa cara de menu de URA.
    """
    return intent.clarificacao.pergunta if intent.clarificacao else ""


def texto_da_confirmacao(intent: Intent) -> str:
    """Pergunta neutra, montada a partir do `nome` da intenção.

    Não usa o `reconhecimento` do roteiro de propósito: aquele texto foi escrito
    para quando a intenção JÁ está confirmada, e afirma o problema. Em
    COBRANCA_INDEVIDA ele abre com "lamento pelo transtorno" — pedir desculpas
    por uma cobrança antes de saber se ela existe, com um palpite de confiança
    média, é pior que não responder.
    """
    return f"Você quer falar sobre {intent.nome.lower()}?"
