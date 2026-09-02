"""Etapa 6 do pipeline — registro das interações (RF008).

Duas decisões da seção 8 do CLAUDE.md moram aqui:

- Uma única conexão SQLite, aberta no boot e reaproveitada, com
  `check_same_thread=False`. O FastAPI atende em várias threads; abrir conexão
  por requisição custaria mais que a própria gravação.
- A gravação sai do caminho da resposta. Quem chama agenda o registro como
  tarefa de fundo do FastAPI, que só roda depois da resposta já ter partido.
  O cliente nunca espera pelo disco.

As linhas semeadas pelo scripts/seed_telemetry.py entram com `simulado = 1`.
Nenhum número apresentado no relatório pode misturar dado real com sintético
sem dizer qual é qual.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import CORE_DIR, settings
from .flows import get_flows

ESQUEMA = """
CREATE TABLE IF NOT EXISTS interacoes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                TEXT    NOT NULL,
    session_id        TEXT    NOT NULL,
    canal             TEXT    NOT NULL,
    texto             TEXT    NOT NULL,
    intent            TEXT,
    confidence        REAL    NOT NULL,
    band              TEXT    NOT NULL,
    confidence_source TEXT    NOT NULL,
    state             TEXT    NOT NULL,
    destination       TEXT,
    protocol          TEXT,
    reply_source      TEXT    NOT NULL,
    latency_ms        INTEGER NOT NULL,
    simulado          INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_interacoes_ts     ON interacoes (ts);
CREATE INDEX IF NOT EXISTS idx_interacoes_intent ON interacoes (intent);
"""

_conexao: sqlite3.Connection | None = None
_trava = threading.Lock()


@dataclass(frozen=True)
class Evento:
    session_id: str
    canal: str
    texto: str
    intent: str | None
    confidence: float
    band: str
    confidence_source: str
    state: str
    destination: str | None
    protocol: str | None
    reply_source: str
    latency_ms: int
    simulado: int = 0
    ts: str = ""

    def com_horario(self) -> Evento:
        if self.ts:
            return self
        agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return Evento(**{**asdict(self), "ts": agora})


def caminho_do_banco(path: str | Path | None = None) -> Path:
    """DB_PATH relativo é ancorado em core/, não no diretório de trabalho."""
    bruto = Path(path or settings.db_path)
    return bruto if bruto.is_absolute() else CORE_DIR / bruto


def conectar(path: str | Path | None = None) -> None:
    """Abre a conexão e garante o esquema. Chamado no lifespan."""
    global _conexao
    destino = caminho_do_banco(path)
    destino.parent.mkdir(parents=True, exist_ok=True)

    conexao = sqlite3.connect(str(destino), check_same_thread=False)
    conexao.row_factory = sqlite3.Row
    conexao.executescript(ESQUEMA)
    conexao.commit()

    with _trava:
        if _conexao is not None:
            _conexao.close()
        _conexao = conexao


def fechar() -> None:
    global _conexao
    with _trava:
        if _conexao is not None:
            _conexao.close()
            _conexao = None


def _exigir_conexao() -> sqlite3.Connection:
    if _conexao is None:
        raise RuntimeError("telemetria não conectada — conectar() roda no lifespan")
    return _conexao


COLUNAS = (
    "ts, session_id, canal, texto, intent, confidence, band, confidence_source, "
    "state, destination, protocol, reply_source, latency_ms, simulado"
)


def registrar(evento: Evento) -> None:
    """Grava uma interação. Roda em tarefa de fundo, fora da resposta.

    Falha de escrita não pode derrubar nada: o atendimento já aconteceu e a
    resposta já foi entregue. Perder uma linha de métrica é aceitável; virar
    erro no cliente, não.
    """
    if _conexao is None:
        return
    dados = evento.com_horario()
    valores = tuple(getattr(dados, coluna.strip()) for coluna in COLUNAS.split(","))
    marcadores = ", ".join("?" * len(valores))
    try:
        with _trava:
            _conexao.execute(
                f"INSERT INTO interacoes ({COLUNAS}) VALUES ({marcadores})", valores
            )
            _conexao.commit()
    except sqlite3.Error:
        return


def registrar_muitos(eventos: list[Evento]) -> int:
    conexao = _exigir_conexao()
    marcadores = ", ".join("?" * len(COLUNAS.split(",")))
    linhas = [
        tuple(getattr(e.com_horario(), c.strip()) for c in COLUNAS.split(","))
        for e in eventos
    ]
    with _trava:
        conexao.executemany(
            f"INSERT INTO interacoes ({COLUNAS}) VALUES ({marcadores})", linhas
        )
        conexao.commit()
    return len(linhas)


def _destinos_humanos() -> set[str]:
    """Do flows.json, não hardcoded: destinos da categoria 'atendimento'."""
    return {
        destino_id
        for destino_id, destino in get_flows().destinos.items()
        if destino.categoria == "atendimento"
    }


def metricas() -> dict[str, Any]:
    """Agregados para o painel. Separa o que é real do que foi semeado."""
    conexao = _exigir_conexao()
    humanos = _destinos_humanos()
    vazio = ", ".join("?" * len(humanos)) or "''"

    with _trava:
        total, simulados, latencia = conexao.execute(
            "SELECT COUNT(*), COALESCE(SUM(simulado), 0), COALESCE(AVG(latency_ms), 0)"
            " FROM interacoes"
        ).fetchone()
        hoje = conexao.execute(
            "SELECT COUNT(*) FROM interacoes WHERE substr(ts, 1, 10) = ?",
            (datetime.now(timezone.utc).date().isoformat(),),
        ).fetchone()[0]
        escalados = conexao.execute(
            f"SELECT COUNT(*) FROM interacoes WHERE state = 'ESCALANDO'"
            f" OR destination IN ({vazio})",
            tuple(humanos),
        ).fetchone()[0]
        por_intencao = conexao.execute(
            "SELECT COALESCE(intent, 'NAO_IDENTIFICADA') AS chave, COUNT(*) AS n"
            " FROM interacoes GROUP BY chave ORDER BY n DESC"
        ).fetchall()
        por_canal = conexao.execute(
            "SELECT canal, COUNT(*) AS n FROM interacoes GROUP BY canal ORDER BY n DESC"
        ).fetchall()

    resolvidos = total - escalados
    return {
        "total_hoje": hoje,
        "total_geral": total,
        "reais": total - simulados,
        "simulados": simulados,
        "taxa_resolucao_digital": round(resolvidos / total, 4) if total else 0.0,
        "taxa_escalacao": round(escalados / total, 4) if total else 0.0,
        "latencia_media_ms": round(latencia, 1),
        "por_intencao": {linha["chave"]: linha["n"] for linha in por_intencao},
        "por_canal": {linha["canal"]: linha["n"] for linha in por_canal},
    }
