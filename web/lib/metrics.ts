/**
 * Leitura da telemetria. Roda SÓ no servidor — é aqui que CORE_URL vive.
 *
 * Usada tanto pelo componente de servidor do painel quanto pela rota
 * /api/metrics; a lógica de busca mora num lugar só.
 */

import type { ConfidenceBand, ConfidenceSource, ReplySource, State } from "./contract";

/** Uma linha da tabela `interacoes` do núcleo. */
export interface Interacao {
  ts: string;
  canal: string;
  texto: string;
  intent: string | null;
  confidence: number;
  band: ConfidenceBand;
  confidence_source: ConfidenceSource;
  state: State;
  destination: string | null;
  protocol: string | null;
  reply_source: ReplySource;
  latency_ms: number;
  /** 1 quando a linha veio do seed sintético. */
  simulado: number;
}

export interface Metricas {
  total_hoje: number;
  total_geral: number;
  reais: number;
  simulados: number;
  taxa_resolucao_digital: number;
  taxa_escalacao: number;
  latencia_media_ms: number;
  por_intencao: Record<string, number>;
  por_canal: Record<string, number>;
  /** série diária, do dia mais antigo para o mais recente */
  por_dia: { dia: string; n: number }[];
  /** a cascata do pipeline: regra / embedding / nenhuma */
  por_camada: Record<string, number>;
  /** a escada de degradação: generative / template / fallback */
  por_origem_resposta: Record<string, number>;
  ultimas: Interacao[];
}

/** `null` quando o núcleo não respondeu — o painel decide o que mostrar. */
export async function buscarMetricas(): Promise<Metricas | null> {
  const base = process.env.CORE_URL ?? "http://localhost:8000";
  const limite = Number(process.env.CORE_TIMEOUT_MS ?? 2500);
  try {
    const r = await fetch(`${base}/v1/metrics`, {
      signal: AbortSignal.timeout(limite),
      cache: "no-store",
    });
    if (!r.ok) return null;
    return (await r.json()) as Metricas;
  } catch {
    return null;
  }
}
