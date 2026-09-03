"use client";

/**
 * Card do portal que conversa com o widget: o clique dispara o evento
 * "guia:pergunta" e o assistente abre já respondendo. É a demonstração viva
 * da proposta — o Guia se integra a qualquer superfície da plataforma.
 */

interface Props {
  titulo: string;
  descricao: string;
  pergunta: string;
  icone: React.ReactNode;
}

export function AcaoRapida({ titulo, descricao, pergunta, icone }: Props) {
  return (
    <button
      onClick={() =>
        window.dispatchEvent(new CustomEvent("guia:pergunta", { detail: pergunta }))
      }
      className="group flex flex-col items-start gap-3 rounded-2xl border p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-claro-red/40 hover:shadow-md"
      style={{ borderColor: "var(--borda)", background: "var(--superficie-2)" }}
    >
      <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-claro-red/10 text-claro-red transition group-hover:bg-claro-red group-hover:text-white">
        {icone}
      </span>
      <span>
        <span className="block text-sm font-bold" style={{ color: "var(--tinta)" }}>{titulo}</span>
        <span className="mt-0.5 block text-xs leading-relaxed" style={{ color: "var(--tinta-2)" }}>
          {descricao}
        </span>
      </span>
      <span className="mt-auto text-xs font-semibold text-claro-red opacity-0 transition group-hover:opacity-100">
        Resolver com o Guia →
      </span>
    </button>
  );
}
