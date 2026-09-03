/**
 * Painel operacional — componente de SERVIDOR, sem estado no cliente.
 *
 * Lê a telemetria real do núcleo a cada carregamento. Os gráficos são SVG e
 * CSS: nenhuma biblioteca, nenhum JavaScript enviado ao browser por causa
 * deste painel. As dicas de valor usam tooltip nativo (`title`), que funciona
 * sem script.
 *
 * Tema escuro de propósito: separa o painel operacional do site do cliente e
 * é o que a paleta foi validada para (ver charts.tsx).
 */

import Link from "next/link";

import { TemaToggle } from "../components/TemaToggle";

import { buscarMetricas, type Interacao, type Metricas } from "@/lib/metrics";
import {
  AreaNoTempo,
  BarrasDeMagnitude,
  EscadaEmpilhada,
  Medidor,
  StatTile,
} from "./charts";

export const dynamic = "force-dynamic";

const COR_DA_BANDA: Record<string, string> = {
  ALTO: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  MEDIO: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  BAIXO: "bg-rose-500/15 text-rose-700 dark:text-rose-300",
};

const CAMADAS = ["regra", "embedding", "nenhuma"] as const;
const ROTULO_CAMADA = {
  regra: "Regra determinística (etapa 2)",
  embedding: "Similaridade semântica (etapa 3)",
  nenhuma: "Não identificada (pergunta aberta)",
};

const ORIGENS = ["generative", "template", "fallback"] as const;
const ROTULO_ORIGEM = {
  generative: "Redigida pelo Gemini",
  template: "Roteiro canônico do flows.json",
  fallback: "Fallback: núcleo ou LLM fora",
};

function horario(ts: string): string {
  const d = new Date(ts.endsWith("Z") || ts.includes("+") ? ts : `${ts}Z`);
  if (Number.isNaN(d.getTime())) return ts.slice(0, 16).replace("T", " ");
  return d.toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

function Linha({ interacao }: { interacao: Interacao }) {
  const sintetica = interacao.simulado === 1;
  return (
    <tr className={sintetica ? "bg-amber-400/[0.06]" : undefined}>
      <td className="whitespace-nowrap px-3 py-2 tabular-nums" style={{ color: "var(--tinta-3)" }}>
        {horario(interacao.ts)}
        {sintetica && (
          <span title="linha do seed sintético"
                className="ml-1.5 rounded px-1 text-[9px] font-bold uppercase"
                style={{ background: "var(--aviso-etiqueta)", color: "var(--aviso-tinta)" }}>
            seed
          </span>
        )}
      </td>
      <td className="px-3 py-2" style={{ color: "var(--tinta-3)" }}>{interacao.canal}</td>
      <td className="max-w-[22rem] truncate px-3 py-2" style={{ color: "var(--tinta-2)" }} title={interacao.texto}>
        {interacao.texto}
      </td>
      <td className="px-3 py-2 font-medium" style={{ color: "var(--tinta)" }}>
        {interacao.intent ?? <span style={{ color: "var(--tinta-3)", opacity: 0.5 }}>—</span>}
      </td>
      <td className="px-3 py-2">
        <span className={`rounded px-1.5 py-0.5 text-[11px] font-semibold tabular-nums ${
          COR_DA_BANDA[interacao.band] ?? ""}`}>
          {interacao.confidence.toFixed(2)}
        </span>
        <span className="ml-1.5 text-[11px]" style={{ color: "var(--tinta-3)" }}>{interacao.confidence_source}</span>
      </td>
      <td className="px-3 py-2" style={{ color: "var(--tinta-3)" }}>
        {interacao.destination ?? <span style={{ color: "var(--tinta-3)", opacity: 0.5 }}>—</span>}
      </td>
    </tr>
  );
}

function NucleoFora() {
  return (
    <div className="rounded-xl border p-6"
         style={{ borderColor: "var(--aviso-borda)", background: "var(--aviso-fundo)", color: "var(--aviso-tinta)" }}>
      <h2 className="text-sm font-bold">Núcleo indisponível</h2>
      <p className="mt-1 text-sm opacity-90">
        O painel lê a telemetria direto do núcleo e não tem cópia local. Sem ele
        não há número para mostrar. O chat continua funcionando pelas regras
        locais; só o painel depende do núcleo estar no ar.
      </p>
      <p className="mt-3 font-mono text-xs opacity-75">
        cd core &amp;&amp; .venv/bin/uvicorn app.main:app --port 8000
      </p>
    </div>
  );
}

function Painel({ m }: { m: Metricas }) {
  const soSintetico = m.reais === 0 && m.simulados > 0;
  const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

  return (
    <>
      {m.simulados > 0 && (
        <div className="mb-5 flex flex-wrap items-center gap-2 rounded-xl border px-4 py-2.5 text-xs"
          style={{ borderColor: "var(--aviso-borda)", background: "var(--aviso-fundo)", color: "var(--aviso-tinta)" }}>
          <span className="rounded px-1.5 py-0.5 text-[10px] font-bold uppercase"
            style={{ background: "var(--aviso-etiqueta)" }}>
            atenção
          </span>
          <span>
            {m.simulados} das {m.total_geral} interações vieram do seed sintético
            {soSintetico
              ? ". Todos os números abaixo são de dados inventados."
              : ` (${m.reais} são de uso real). Os agregados misturam os dois.`}
          </span>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile rotulo="Atendimentos" valor={m.total_geral.toLocaleString("pt-BR")}
                  detalhe={`${m.total_hoje} hoje · ${m.reais} reais · ${m.simulados} semeados`} />
        <StatTile rotulo="Resolução digital" valor={pct(m.taxa_resolucao_digital)}
                  detalhe="resolvidos sem passar por uma pessoa" heroi />
        <StatTile rotulo="Escalação" valor={pct(m.taxa_escalacao)}
                  detalhe="encaminhados a atendimento humano" />
        <StatTile rotulo="Latência média" valor={`${m.latencia_media_ms.toFixed(0)} ms`}
                  detalhe="do pedido até a resposta pronta" />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[2fr_1fr]">
        <AreaNoTempo titulo="Atendimentos por dia" pontos={m.por_dia} />
        <Medidor titulo="Resolução digital" valor={m.taxa_resolucao_digital}
                 legenda="meta operacional: quanto maior, menos transbordo" />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <BarrasDeMagnitude titulo="Distribuição por intenção"
                           subtitulo="o que os clientes mais pedem"
                           dados={m.por_intencao} />
        <EscadaEmpilhada titulo="Cascata de decisão"
                         subtitulo="qual camada do pipeline resolveu a mensagem"
                         ordem={CAMADAS} dados={m.por_camada} rotulos={ROTULO_CAMADA} />
        <div className="space-y-4">
          <EscadaEmpilhada titulo="Origem da resposta"
                           subtitulo="escada de degradação graciosa"
                           ordem={ORIGENS} dados={m.por_origem_resposta}
                           rotulos={ROTULO_ORIGEM} />
          <BarrasDeMagnitude titulo="Distribuição por canal"
                             subtitulo="mesmo núcleo, canais diferentes"
                             dados={m.por_canal} />
        </div>
      </div>

      <div className="mt-4 overflow-hidden rounded-xl border" style={{ borderColor: "var(--borda)", background: "var(--superficie)" }}>
        <div className="flex items-baseline justify-between border-b px-5 py-3" style={{ borderColor: "var(--borda)" }}>
          <h2 className="text-sm font-bold" style={{ color: "var(--tinta)" }}>Últimas conversas</h2>
          <span className="text-xs" style={{ color: "var(--tinta-3)" }}>{m.ultimas.length} mais recentes</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-[11px] uppercase tracking-wide" style={{ background: "var(--trilho)", color: "var(--tinta-3)" }}>
              <tr>
                {["Horário", "Canal", "Mensagem", "Intenção", "Score", "Destino"].map((c) => (
                  <th key={c} className="px-3 py-2 font-semibold">{c}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y" style={{ borderColor: "var(--borda)" }}>
              {m.ultimas.length === 0 ? (
                <tr><td colSpan={6} className="px-3 py-6 text-center" style={{ color: "var(--tinta-3)" }}>
                  nenhuma conversa registrada
                </td></tr>
              ) : (
                m.ultimas.map((i, k) => <Linha key={`${i.ts}-${k}`} interacao={i} />)
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

export default async function AdminPage() {
  const metricas = await buscarMetricas();

  return (
    <div className="min-h-dvh" style={{ background: "var(--fundo)" }}>
      <header className="border-b" style={{ borderColor: "var(--borda)" }}>
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-3 px-6 py-4 lg:px-12">
          <div className="flex items-center gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/logo-claro.svg" alt="Claro" className="h-7 w-auto" />
            <div className="border-l pl-3" style={{ borderColor: "var(--borda)" }}>
              <h1 className="text-base font-bold" style={{ color: "var(--tinta)" }}>
                Painel operacional
              </h1>
              <p className="text-xs" style={{ color: "var(--tinta-3)" }}>
                Guia Inteligente · telemetria real, atualiza a cada carregamento
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <TemaToggle />
            <Link href="/"
                  className="rounded-full border px-4 py-2 text-sm font-medium transition hover:opacity-80"
                  style={{ borderColor: "var(--borda)", color: "var(--tinta-2)" }}>
              ← Voltar ao site
            </Link>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1440px] px-6 py-8 lg:px-12">
        {metricas ? <Painel m={metricas} /> : <NucleoFora />}
      </main>
    </div>
  );
}
