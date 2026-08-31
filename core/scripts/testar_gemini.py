"""Testa a chamada real ao Gemini, SEM a rede de proteção do generator.

O `generator.py` engole qualquer falha de propósito — é o que mantém o
atendimento no ar quando o LLM cai. O efeito colateral é que uma configuração
errada fica invisível: a resposta volta como "template" e parece tudo certo.

Este script chama a API sem o try/except, então o erro aparece inteiro.

    .venv/bin/python scripts/testar_gemini.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CORE_DIR))

from app.config import settings  # noqa: E402
from app.contract import ReplySource  # noqa: E402
from app.flows import get_intent, init_flows  # noqa: E402
from app.generator import (  # noqa: E402
    INSTRUCAO_DE_SISTEMA,
    MAX_LINHAS,
    _ancorado,
    _chamar_gemini,
    _montar_pedido,
    generate,
)
from app.routing import resolve  # noqa: E402

INTENCAO = "SUPORTE_TECNICO"


def main() -> int:
    init_flows()

    print("1. CHAVE")
    if not settings.gemini_api_key:
        print("   nenhuma chave carregada.")
        print(f"   Coloque GEMINI_API_KEY no arquivo {CORE_DIR / '.env'}")
        print("   ou exporte no ambiente ANTES de subir o servidor.")
        return 1
    chave = settings.gemini_api_key
    print(f"   carregada: {chave[:6]}...{chave[-4:]} ({len(chave)} caracteres)")
    print(f"   modelo: {settings.gemini_model}")
    print(f"   timeout: {settings.llm_timeout_ms} ms")

    intent = get_intent(INTENCAO)
    assert intent is not None
    routing = resolve(intent_id=INTENCAO)
    pedido = _montar_pedido(intent, routing, intent.roteiro, [])

    print("\n2. CHAMADA REAL (sem try/except — erro aparece inteiro)")
    texto = asyncio.run(
        _chamar_gemini(
            INSTRUCAO_DE_SISTEMA.format(max_linhas=MAX_LINHAS),
            pedido,
            settings.llm_timeout_ms / 1000,
        )
    )
    if not texto:
        print("   a API respondeu, mas sem texto. Resposta vazia ou bloqueada.")
        return 1
    print("   respondeu:")
    for linha in texto.splitlines():
        print(f"     {linha}")

    print("\n3. ANCORAGEM (o texto inventou endereço ou protocolo?)")
    if _ancorado(texto, routing):
        print("   passou — só cita o que demos.")
    else:
        print("   REPROVADO — o texto seria descartado e viraria template.")
        print(f"   url permitida: {routing.url}")
        print(f"   protocolo permitido: {routing.protocol}")
        return 1

    print("\n4. PELO CAMINHO COMPLETO")
    _, origem = asyncio.run(generate(intent, routing, intent.roteiro))
    print(f"   reply_source: {origem.value}")
    if origem is not ReplySource.GENERATIVE:
        print("   ainda caiu no template — algo acima falhou.")
        return 1

    print("\nTudo certo. O endpoint vai responder com reply_source 'generative'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
