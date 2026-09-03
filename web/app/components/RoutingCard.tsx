import type { Routing } from "@/lib/contract";

export function RoutingCard({ routing }: { routing: Routing }) {
  return (
    <div className="mt-2 rounded-xl border p-3 shadow-sm"
      style={{ borderColor: "var(--borda)", background: "var(--superficie-2)" }}>
      <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--tinta-3)" }}>
        Encaminhamento
      </p>
      <p className="mt-0.5 text-sm font-semibold" style={{ color: "var(--tinta)" }}>{routing.label}</p>
      {routing.protocol && (
        <p className="mt-0.5 font-mono text-xs" style={{ color: "var(--tinta-2)" }}>
          protocolo {routing.protocol}
        </p>
      )}
      {routing.url && (
        <a
          href={routing.url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 inline-block rounded-lg bg-claro-red px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-claro-dark"
        >
          Acessar agora →
        </a>
      )}
    </div>
  );
}
