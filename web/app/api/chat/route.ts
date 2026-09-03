/**
 * BFF — a única porta entre o browser e o núcleo.
 *
 * Roda no servidor do Next.js. O browser fala só com /api/chat; CORE_URL,
 * timeout e fallback vivem aqui e nunca chegam ao bundle do cliente.
 */

import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { randomUUID } from "node:crypto";

import type { InterpretRequest, InterpretResponse } from "@/lib/contract";
import { interpretLocally } from "@/lib/fallback";

const SESSION_COOKIE = "cgi_session";
const MAX_TEXTO = 500;

function coreUrl(): string {
  return process.env.CORE_URL ?? "http://localhost:8000";
}

function coreTimeoutMs(): number {
  return Number(process.env.CORE_TIMEOUT_MS ?? 2500);
}

export async function POST(request: Request): Promise<NextResponse> {
  let texto: unknown;
  try {
    ({ text: texto } = (await request.json()) as { text?: unknown });
  } catch {
    return NextResponse.json({ error: "corpo inválido" }, { status: 400 });
  }
  if (typeof texto !== "string" || !texto.trim() || texto.length > MAX_TEXTO) {
    return NextResponse.json({ error: "text obrigatório (até 500 caracteres)" }, { status: 400 });
  }

  // Sessão: gerada aqui, guardada em cookie, opaca para o núcleo.
  const jar = cookies();
  const sessionId = jar.get(SESSION_COOKIE)?.value ?? `web:${randomUUID()}`;

  const payload: InterpretRequest = {
    session_id: sessionId,
    channel: "web",
    text: texto.trim(),
  };

  let resposta: InterpretResponse;
  try {
    const r = await fetch(`${coreUrl()}/v1/interpret`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(coreTimeoutMs()),
      cache: "no-store",
    });
    if (!r.ok) throw new Error(`core respondeu ${r.status}`);
    resposta = (await r.json()) as InterpretResponse;
  } catch {
    // NÍVEL 3: núcleo fora ou lento demais -> regras locais, mesmo contrato.
    resposta = interpretLocally(sessionId, payload.text);
  }

  const saida = NextResponse.json(resposta);
  saida.cookies.set(SESSION_COOKIE, sessionId, {
    httpOnly: true,
    sameSite: "lax",
    maxAge: 60 * 30,
    path: "/",
  });
  return saida;
}
