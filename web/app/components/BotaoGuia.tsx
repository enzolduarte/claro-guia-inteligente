"use client";

export function BotaoGuia({
  pergunta,
  children,
  className,
}: {
  pergunta?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <button
      onClick={() =>
        window.dispatchEvent(
          pergunta
            ? new CustomEvent("guia:pergunta", { detail: pergunta })
            : new Event("guia:abrir"),
        )
      }
      className={className}
    >
      {children}
    </button>
  );
}
