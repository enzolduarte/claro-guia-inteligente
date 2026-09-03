/**
 * FALLBACK NÍVEL 3 — o núcleo caiu ou não respondeu a tempo.
 *
 * Porte simplificado das camadas determinísticas do core (normalize.py,
 * sensitivity.py, rules.py), lendo o mesmo flows.json. Sem embeddings e sem
 * sessão: é o modo de sobrevivência, não o produto. O usuário não vê erro —
 * vê uma resposta um pouco menos esperta (reply_source "fallback").
 *
 * Roda SÓ no servidor.
 */

import type { InterpretResponse } from "./contract";
import { getFlows, type FlowIntent, type FlowScript } from "./flows";

/** minúsculas → sem acento (NFKD) → pontuação vira espaço → espaços colapsados */
export function normalize(texto: string): string {
  return texto
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function matches(rule: string, textoNormalizado: string): boolean {
  const alvo = normalize(rule);
  if (!alvo) return false;
  // \b não funciona com acentos no JS; após normalize só há ASCII+dígitos.
  return new RegExp(`\\b${alvo.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`).test(
    textoNormalizado,
  );
}

/** Etapa 1: sensibilidade. Regras simples + condicionais (termo + contexto). */
export function checkSensitive(textoNormalizado: string): FlowIntent | null {
  for (const intent of getFlows().intencoes) {
    if (!intent.sensivel) continue;
    if (intent.regras.some((r) => matches(r, textoNormalizado))) return intent;
    const cond = intent.regras_condicionais;
    if (
      cond &&
      cond.termos.some((t) => matches(t, textoNormalizado)) &&
      cond.exige_contexto.some((c) => matches(c, textoNormalizado))
    ) {
      return intent;
    }
  }
  return null;
}

/** Etapa 2: palavra-chave, regra mais longa vence. */
export function matchRules(textoNormalizado: string): FlowIntent | null {
  let melhor: { intent: FlowIntent; tamanho: number } | null = null;
  for (const intent of getFlows().intencoes) {
    if (intent.sensivel) continue;
    for (const rule of intent.regras) {
      if (matches(rule, textoNormalizado) && (!melhor || rule.length > melhor.tamanho)) {
        melhor = { intent, tamanho: rule.length };
      }
    }
  }
  return melhor?.intent ?? null;
}

function protocolo(prefixo: string): string {
  const n = Math.floor(10000 + Math.random() * 90000);
  return `${prefixo}-${new Date().getUTCFullYear()}-${n}`;
}

function textoDoRoteiro(roteiro: FlowScript): string {
  const passos = roteiro.passos.map((p, i) => `${i + 1}. ${p}`).join("\n");
  return `${roteiro.reconhecimento} ${roteiro.resumo}\n\n${passos}\n\n${roteiro.fechamento}`;
}

/** Resposta completa do contrato, montada localmente. */
export function interpretLocally(sessionId: string, texto: string): InterpretResponse {
  const inicio = Date.now();
  const flows = getFlows();
  const normalizado = normalize(texto);

  const base = {
    session_id: sessionId,
    intent: null as string | null,
    confidence: 0,
    confidence_band: "BAIXO" as const,
    confidence_source: "nenhuma" as const,
    reply_source: "fallback" as const,
    options: null,
    routing: null,
  };

  const sensivel = checkSensitive(normalizado);
  const porRegra = sensivel ?? matchRules(normalizado);

  if (!porRegra) {
    const aberta = flows.config.resposta_nao_identificada;
    const sugestoes = aberta.sugestoes.map((s) => `• ${s}`).join("\n");
    return {
      ...base,
      state: "AGUARDANDO",
      reply: `${aberta.texto}\n\n${sugestoes}`,
      latency_ms: Date.now() - inicio,
    };
  }

  // Catálogo fechado: destino não mapeado cai no padrão. Nunca inferir.
  const destinoId = porRegra.destino in flows.destinos ? porRegra.destino : flows.config.destino_padrao;
  const destino = flows.destinos[destinoId];
  return {
    ...base,
    state: sensivel ? "ESCALANDO" : "ROTEANDO",
    intent: porRegra.id,
    confidence: 0.97,
    confidence_band: "ALTO",
    confidence_source: "regra",
    reply: textoDoRoteiro(porRegra.roteiro),
    routing: {
      destination: destinoId,
      label: destino.label,
      url: destino.url,
      protocol:
        destino.gera_protocolo && destino.prefixo_protocolo
          ? protocolo(destino.prefixo_protocolo)
          : null,
    },
    latency_ms: Date.now() - inicio,
  };
}
