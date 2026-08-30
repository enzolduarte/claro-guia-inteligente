"""Conversa com o núcleo pelo terminal, para testar ponta a ponta sem a web.

O `web` ainda não existe, e este script faz o papel dele: mantém um session_id
entre as mensagens, chama o POST /v1/interpret de verdade e mostra o que voltou.
É a forma mais próxima da experiência real enquanto não há interface.

    # num terminal, o núcleo:
    .venv/bin/uvicorn app.main:app --port 8000
    # noutro, a conversa:
    .venv/bin/python scripts/chat.py

Comandos: /nova (recomeça a sessão), /json (mostra a resposta crua), /sair
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
import uuid

URL = os.environ.get("CORE_URL", "http://localhost:8000") + "/v1/interpret"

VERDE, AMARELO, VERMELHO, CINZA, NEGRITO, FIM = (
    "\033[32m",
    "\033[33m",
    "\033[31m",
    "\033[90m",
    "\033[1m",
    "\033[0m",
)

COR_DA_BANDA = {"ALTO": VERDE, "MEDIO": AMARELO, "BAIXO": VERMELHO}


def enviar(session_id: str, texto: str) -> dict:
    corpo = json.dumps(
        {"session_id": session_id, "channel": "web", "text": texto}
    ).encode()
    req = urllib.request.Request(
        URL, data=corpo, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resposta:
        return json.load(resposta)


def mostrar(dados: dict) -> None:
    banda = dados["confidence_band"]
    cor = COR_DA_BANDA.get(banda, CINZA)

    print(f"\n{NEGRITO}{dados['reply']}{FIM}")

    if dados["options"]:
        print()
        for i, opcao in enumerate(dados["options"], 1):
            print(f"   {NEGRITO}{i}{FIM}. {opcao['label']}")

    if dados["routing"]:
        rota = dados["routing"]
        print(f"\n   {CINZA}→ {rota['label']}{FIM}")
        if rota["url"]:
            print(f"   {CINZA}  {rota['url']}{FIM}")
        if rota["protocol"]:
            print(f"   {CINZA}  protocolo {rota['protocol']}{FIM}")

    intencao = dados["intent"] or "—"
    print(
        f"\n{CINZA}   [{dados['state']}]  {intencao}  "
        f"{cor}{banda} {dados['confidence']:.2f}{CINZA} "
        f"via {dados['confidence_source']}  ·  {dados['latency_ms']}ms  "
        f"· resposta {dados['reply_source']}{FIM}\n"
    )


def main() -> None:
    session_id = f"web:{uuid.uuid4()}"
    mostrar_json = False

    print(f"{NEGRITO}Claro Guia Inteligente{FIM} {CINZA}— núcleo em {URL}{FIM}")
    print(f"{CINZA}sessão {session_id}{FIM}")
    print(
        f"{CINZA}/nova para recomeçar · /json para ver a resposta crua · /sair{FIM}\n"
    )

    while True:
        try:
            texto = input(f"{NEGRITO}você:{FIM} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if not texto:
            continue
        if texto == "/sair":
            return
        if texto == "/nova":
            session_id = f"web:{uuid.uuid4()}"
            print(f"{CINZA}sessão nova: {session_id}{FIM}\n")
            continue
        if texto == "/json":
            mostrar_json = not mostrar_json
            print(f"{CINZA}json {'ligado' if mostrar_json else 'desligado'}{FIM}\n")
            continue

        try:
            dados = enviar(session_id, texto)
        except urllib.error.URLError as erro:
            print(f"{VERMELHO}núcleo não respondeu: {erro.reason}{FIM}")
            print(f"{CINZA}suba com: .venv/bin/uvicorn app.main:app --port 8000{FIM}\n")
            continue

        mostrar(dados)
        if mostrar_json:
            print(CINZA + json.dumps(dados, indent=2, ensure_ascii=False) + FIM + "\n")


if __name__ == "__main__":
    sys.exit(main())
