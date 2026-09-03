/**
 * Contrato público da API — espelho 1:1 dos modelos Pydantic do núcleo
 * (core/app/contract.py). Fonte única de tipos no front: nenhum outro arquivo
 * declara formas do protocolo.
 *
 * `options` e `routing` são sempre presentes na serialização; `null` quando
 * não se aplicam. Nunca `undefined`.
 */

export type State =
  | "AGUARDANDO"
  | "PROCESSANDO"
  | "CLARIFICANDO"
  | "RESPONDENDO"
  | "ROTEANDO"
  | "ESCALANDO"
  | "ENCERRADO";

export type ConfidenceBand = "ALTO" | "MEDIO" | "BAIXO";

export type ConfidenceSource = "regra" | "embedding" | "nenhuma";

export type ReplySource = "generative" | "template" | "fallback";

export type Channel = "web" | "telegram";

export interface InterpretRequest {
  session_id: string;
  channel: Channel;
  text: string;
}

export interface Option {
  id: string;
  label: string;
}

export interface Routing {
  destination: string;
  label: string;
  url: string | null;
  protocol: string | null;
}

export interface InterpretResponse {
  session_id: string;
  state: State;
  intent: string | null;
  confidence: number;
  confidence_band: ConfidenceBand;
  confidence_source: ConfidenceSource;
  reply: string;
  reply_source: ReplySource;
  options: Option[] | null;
  routing: Routing | null;
  latency_ms: number;
}
