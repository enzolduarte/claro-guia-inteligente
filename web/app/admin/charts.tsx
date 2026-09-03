/**
 * Gráficos do painel — SVG e CSS puros, sem biblioteca e sem JavaScript no
 * cliente. Todos são componentes de servidor.
 *
 * PALETA — validada com o script da metodologia de dataviz, UMA VEZ POR MODO
 * (modo escuro é escolhido, não um espelho do claro). Os valores vivem em
 * globals.css; aqui só os nomes dos tokens:
 *
 *   claro  (superfície #ffffff): #f6919f → #e4002b → #960020
 *   escuro (superfície #14161b): #fca7b4 → #f4677d → #e4002b
 *
 * Ambas passam nos quatro testes de rampa ordinal: luminosidade monótona,
 * ΔL ≥ 0,06 entre degraus, ponta clara acima de 2:1 na superfície, matiz único.
 *
 * Rampa de UMA cor porque os dados são ORDINAIS, não categóricos: a cascata
 * (regra → embedding → nenhuma) e a degradação (generative → template →
 * fallback) são escadas — trocar a ordem muda o sentido. Cor categórica aqui
 * gastaria o canal de identidade para re-codificar o que a ordem já diz.
 *
 * O vermelho da marca tem 3,73:1 no fundo: serve para marca e número grande,
 * NÃO para texto pequeno — por isso todo rótulo usa tinta clara.
 */

/** Os três degraus da rampa, por token — trocam sozinhos com o tema. */
export const RAMPA = ["var(--rampa-1)", "var(--rampa-2)", "var(--rampa-3)"] as const;
export const MARCA = "var(--marca)";

/** Um número que a pessoa lê antes de qualquer gráfico. */
export function StatTile({
  rotulo,
  valor,
  detalhe,
  heroi,
}: {
  rotulo: string;
  valor: string;
  detalhe: string;
  heroi?: boolean;
}) {
  return (
    <div className="rounded-xl border p-5"
      style={{ borderColor: "var(--borda)", background: "var(--superficie)" }}>
      <p className="text-[11px] font-semibold uppercase tracking-widest"
         style={{ color: "var(--tinta-3)" }}>
        {rotulo}
      </p>
      {/* sem tabular-nums: em tamanho grande, digitos de largura fixa deixam o
          numero solto. Alinhamento vertical so importa em tabela e eixo. */}
      <p
        className="mt-2 text-4xl font-extrabold"
        style={{ color: heroi ? "var(--marca)" : "var(--tinta)" }}
      >
        {valor}
      </p>
      <p className="mt-1 text-xs" style={{ color: "var(--tinta-3)" }}>{detalhe}</p>
    </div>
  );
}

/** Uma razão contra um limite. Não é pizza de duas fatias. */
export function Medidor({
  titulo,
  valor,
  legenda,
}: {
  titulo: string;
  valor: number;
  legenda: string;
}) {
  const raio = 52;
  const volta = 2 * Math.PI * raio;
  const preenchido = Math.max(0, Math.min(1, valor)) * volta;

  return (
    <div className="flex flex-col rounded-xl border p-5"
      style={{ borderColor: "var(--borda)", background: "var(--superficie)" }}>
      <h2 className="text-sm font-bold" style={{ color: "var(--tinta)" }}>{titulo}</h2>
      <div className="flex flex-1 items-center justify-center py-3">
        <svg viewBox="0 0 140 140" className="h-36 w-36" role="img"
             aria-label={`${titulo}: ${(valor * 100).toFixed(1)}%`}>
          {/* trilho: mesma rampa, passo mais claro rebaixado */}
          <circle cx="70" cy="70" r={raio} fill="none" stroke="var(--trilho)"
                  strokeWidth="12" />
          <circle
            cx="70" cy="70" r={raio} fill="none" stroke={MARCA} strokeWidth="12"
            strokeLinecap="round" strokeDasharray={`${preenchido} ${volta}`}
            transform="rotate(-90 70 70)"
          />
          <text x="70" y="70" textAnchor="middle" dominantBaseline="central"
                fill="var(--tinta)" fontSize="26" fontWeight="800">
            {(valor * 100).toFixed(1)}%
          </text>
        </svg>
      </div>
      <p className="text-center text-xs" style={{ color: "var(--tinta-3)" }}>{legenda}</p>
    </div>
  );
}

/** Tendência no tempo, série única — área com linha de 2px. */
export function AreaNoTempo({
  titulo,
  pontos,
}: {
  titulo: string;
  pontos: { dia: string; n: number }[];
}) {
  const L = 720, A = 200, pad = { t: 16, r: 12, b: 26, l: 40 };
  const largura = L - pad.l - pad.r;
  const altura = A - pad.t - pad.b;
  const maior = Math.max(1, ...pontos.map((p) => p.n));
  const x = (i: number) =>
    pad.l + (pontos.length <= 1 ? largura / 2 : (i / (pontos.length - 1)) * largura);
  const y = (n: number) => pad.t + altura - (n / maior) * altura;

  const linha = pontos.map((p, i) => `${x(i)},${y(p.n)}`).join(" ");
  const area = `M ${pad.l},${pad.t + altura} L ${linha.replace(/ /g, " L ")} L ${x(
    pontos.length - 1,
  )},${pad.t + altura} Z`;
  const marcas = [0, Math.round(maior / 2), maior];
  const rotuloDia = (d: string) => d.slice(8) + "/" + d.slice(5, 7);

  return (
    <div className="rounded-xl border p-5"
      style={{ borderColor: "var(--borda)", background: "var(--superficie)" }}>
      <h2 className="text-sm font-bold" style={{ color: "var(--tinta)" }}>{titulo}</h2>
      <p className="mt-0.5 text-xs" style={{ color: "var(--tinta-3)" }}>
        {pontos.length} dias · passe o mouse para ver o valor do dia
      </p>
      <svg viewBox={`0 0 ${L} ${A}`} className="mt-3 w-full" role="img"
           aria-label={titulo}>
        <defs>
          <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={MARCA} stopOpacity="0.38" />
            <stop offset="100%" stopColor={MARCA} stopOpacity="0.02" />
          </linearGradient>
        </defs>
        {/* grade recessiva */}
        {marcas.map((m) => (
          <g key={m}>
            <line x1={pad.l} x2={L - pad.r} y1={y(m)} y2={y(m)} stroke="var(--trilho)" />
            <text x={pad.l - 8} y={y(m)} textAnchor="end" dominantBaseline="central"
                  fill="var(--tinta-3)" fontSize="11">{m}</text>
          </g>
        ))}
        <path d={area} fill="url(#areaGrad)" />
        <polyline points={linha} fill="none" stroke={MARCA} strokeWidth="2"
                  strokeLinejoin="round" strokeLinecap="round" />
        {pontos.map((p, i) => (
          <g key={p.dia}>
            {/* alvo de mouse maior que a marca; tooltip nativo, sem JS */}
            {/* alvo de 24px: a marca visivel tem 6px, o alvo nao */}
            <circle cx={x(i)} cy={y(p.n)} r="12" fill="transparent">
              <title>{`${rotuloDia(p.dia)}: ${p.n} atendimentos`}</title>
            </circle>
            {/* anel de 2px na cor da superfície separa a marca da área */}
            <circle cx={x(i)} cy={y(p.n)} r="3" fill={MARCA} stroke="var(--fundo)"
                    strokeWidth="2" pointerEvents="none" />
          </g>
        ))}
        {pontos.map((p, i) =>
          i % 2 === 0 || i === pontos.length - 1 ? (
            <text key={p.dia} x={x(i)} y={A - 8} textAnchor="middle"
                  fill="var(--tinta-3)" fontSize="10">
              {rotuloDia(p.dia)}
            </text>
          ) : null,
        )}
      </svg>

      {/* Tabela equivalente: o tooltip enriquece, nunca é o único caminho para
          o valor. Recolhida para não competir com o gráfico. */}
      <details className="mt-3">
        <summary className="cursor-pointer text-xs hover:underline" style={{ color: "var(--tinta-3)" }}>
          ver os números do gráfico
        </summary>
        <table className="mt-2 w-full text-left text-xs">
          <thead style={{ color: "var(--tinta-3)" }}>
            <tr>
              <th className="py-1 font-medium">Dia</th>
              <th className="py-1 text-right font-medium">Atendimentos</th>
            </tr>
          </thead>
          <tbody>
            {pontos.map((p) => (
              <tr key={p.dia}>
                <td className="py-1 tabular-nums" style={{ color: "var(--tinta-2)" }}>{rotuloDia(p.dia)}</td>
                <td className="py-1 text-right tabular-nums" style={{ color: "var(--tinta)" }}>{p.n}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}

/** Magnitude por categoria nominal — barras na MESMA cor, nunca por valor. */
export function BarrasDeMagnitude({
  titulo,
  subtitulo,
  dados,
}: {
  titulo: string;
  subtitulo: string;
  dados: Record<string, number>;
}) {
  const linhas = Object.entries(dados).sort((a, b) => b[1] - a[1]);
  const maior = linhas[0]?.[1] ?? 1;
  const total = linhas.reduce((s, [, n]) => s + n, 0);

  return (
    <div className="rounded-xl border p-5"
      style={{ borderColor: "var(--borda)", background: "var(--superficie)" }}>
      <h2 className="text-sm font-bold" style={{ color: "var(--tinta)" }}>{titulo}</h2>
      <p className="mt-0.5 text-xs" style={{ color: "var(--tinta-3)" }}>{subtitulo}</p>
      <ul className="mt-4 space-y-2.5">
        {linhas.map(([chave, n]) => (
          <li key={chave} title={`${chave}: ${n} de ${total}`}>
            <div className="flex items-baseline justify-between gap-3 text-xs">
              <span className="font-medium" style={{ color: "var(--tinta)" }}>{chave}</span>
              <span className="tabular-nums" style={{ color: "var(--tinta-3)" }}>
                {n} · {total ? ((n / total) * 100).toFixed(0) : 0}%
              </span>
            </div>
            <div className="mt-1 h-2.5 rounded-full" style={{ background: "var(--trilho)" }}>
              <div
                className="h-full rounded-full transition-opacity hover:opacity-80"
                style={{ width: `${Math.max(1.5, (n / maior) * 100)}%`, background: MARCA }}
              />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Parte-do-todo ORDINAL: a rampa mostra a ordem da escada. */
export function EscadaEmpilhada({
  titulo,
  subtitulo,
  ordem,
  dados,
  rotulos,
}: {
  titulo: string;
  subtitulo: string;
  /** da etapa mais forte para a mais fraca — a ordem é o dado */
  ordem: readonly string[];
  dados: Record<string, number>;
  rotulos: Record<string, string>;
}) {
  const total = ordem.reduce((s, k) => s + (dados[k] ?? 0), 0) || 1;

  return (
    <div className="rounded-xl border p-5"
      style={{ borderColor: "var(--borda)", background: "var(--superficie)" }}>
      <h2 className="text-sm font-bold" style={{ color: "var(--tinta)" }}>{titulo}</h2>
      <p className="mt-0.5 text-xs" style={{ color: "var(--tinta-3)" }}>{subtitulo}</p>

      {/* gap de 2px entre segmentos, na cor da superfície */}
      <div className="mt-4 flex h-4 gap-[2px] overflow-hidden rounded-full">
        {ordem.map((chave, i) => {
          const n = dados[chave] ?? 0;
          if (!n) return null;
          return (
            <div
              key={chave}
              title={`${rotulos[chave] ?? chave}: ${n} (${((n / total) * 100).toFixed(1)}%)`}
              style={{ width: `${(n / total) * 100}%`, background: RAMPA[i] ?? RAMPA[RAMPA.length - 1] }}
              className="first:rounded-l-full last:rounded-r-full transition-opacity hover:opacity-80"
            />
          );
        })}
      </div>

      {/* legenda sempre presente com >=2 series; identidade nunca so por cor */}
      <ul className="mt-4 space-y-1.5">
        {ordem.map((chave, i) => {
          const n = dados[chave] ?? 0;
          return (
            <li key={chave} className="flex items-center gap-2 text-xs">
              <span className="h-2.5 w-2.5 shrink-0 rounded-sm"
                    style={{ background: RAMPA[i] ?? RAMPA[RAMPA.length - 1] }} />
              <span className="flex-1" style={{ color: "var(--tinta-2)" }}>{rotulos[chave] ?? chave}</span>
              <span className="tabular-nums" style={{ color: "var(--tinta-3)" }}>
                {n} · {((n / total) * 100).toFixed(0)}%
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
