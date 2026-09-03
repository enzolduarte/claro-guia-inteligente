/**
 * O badge que torna a arquitetura visível: estado, intenção, confiança e por
 * qual camada a decisão passou. É discreto de propósito — informação para o
 * vídeo e para avaliadores, não para o cliente final.
 */

import type { InterpretResponse } from "@/lib/contract";

const COR_DA_BANDA: Record<string, string> = {
  ALTO: "text-green-700 bg-green-50 border-green-200",
  MEDIO: "text-amber-700 bg-amber-50 border-amber-200",
  BAIXO: "text-red-700 bg-red-50 border-red-200",
};

export function Badge({ resposta }: { resposta: InterpretResponse }) {
  const banda = COR_DA_BANDA[resposta.confidence_band] ?? COR_DA_BANDA.BAIXO;
  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-1.5 font-mono text-[10px] text-gray-400">
      <span className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5">
        {resposta.state}
      </span>
      {resposta.intent && (
        <span className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5">
          {resposta.intent}
        </span>
      )}
      <span className={`rounded border px-1.5 py-0.5 ${banda}`}>
        {resposta.confidence_band} {resposta.confidence.toFixed(2)}
      </span>
      <span className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5">
        via {resposta.confidence_source}
      </span>
      <span className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5">
        {resposta.reply_source} · {resposta.latency_ms}ms
      </span>
    </div>
  );
}
