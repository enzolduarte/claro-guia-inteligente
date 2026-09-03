/**
 * Loader do flows.json para o fallback do BFF. Roda SÓ no servidor.
 *
 * É o mesmo arquivo que o núcleo usa — fonte única de verdade (regra 5 do
 * CLAUDE.md). Lido uma vez por processo e guardado em memória.
 */

import { readFileSync } from "node:fs";
import path from "node:path";

export interface FlowDestination {
  label: string;
  categoria: string;
  url: string | null;
  gera_protocolo: boolean;
  prefixo_protocolo?: string;
}

export interface FlowScript {
  reconhecimento: string;
  resumo: string;
  passos: string[];
  fechamento: string;
}

export interface FlowConditionalRules {
  termos: string[];
  exige_contexto: string[];
}

export interface FlowIntent {
  id: string;
  nome: string;
  sensivel: boolean;
  regras: string[];
  regras_condicionais?: FlowConditionalRules;
  destino: string;
  roteiro: FlowScript;
}

export interface Flows {
  versao: string;
  config: {
    destino_padrao: string;
    resposta_nao_identificada: { estado: string; texto: string; sugestoes: string[] };
  };
  destinos: Record<string, FlowDestination>;
  intencoes: FlowIntent[];
}

let cached: Flows | null = null;

export function getFlows(): Flows {
  if (cached) return cached;
  const configured = process.env.FLOWS_PATH ?? "../core/data/flows.json";
  const target = path.isAbsolute(configured)
    ? configured
    : path.resolve(process.cwd(), configured);
  cached = JSON.parse(readFileSync(target, "utf-8")) as Flows;
  return cached;
}
