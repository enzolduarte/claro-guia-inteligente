"use client";

/**
 * Alternador de tema. Três estados possíveis no documento:
 *
 *   sem data-theme  → segue o sistema (prefers-color-scheme)
 *   data-theme=dark → escuro, escolhido pela pessoa
 *   data-theme=light→ claro, escolhido pela pessoa
 *
 * A escolha fica no localStorage; o script em layout.tsx a reaplica antes da
 * primeira pintura, para a página não piscar no tema errado.
 */

import { useEffect, useState } from "react";

type Tema = "claro" | "escuro";

function temaAtual(): Tema {
  const marcado = document.documentElement.dataset.theme;
  if (marcado === "dark") return "escuro";
  if (marcado === "light") return "claro";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "escuro" : "claro";
}

export function TemaToggle({ className = "" }: { className?: string }) {
  // Começa nulo para o servidor e o cliente renderizarem igual; o tema real
  // só é conhecido depois da hidratação.
  const [tema, setTema] = useState<Tema | null>(null);

  useEffect(() => setTema(temaAtual()), []);

  function alternar() {
    // Lê do DOCUMENTO, não do estado do React: entre dois cliques rápidos o
    // estado ainda não re-renderizou, e a partir do valor velho o segundo
    // clique repetiria o primeiro. O atributo no <html> é a fonte da verdade.
    const novo: Tema = temaAtual() === "escuro" ? "claro" : "escuro";
    document.documentElement.dataset.theme = novo === "escuro" ? "dark" : "light";
    try {
      localStorage.setItem("cgi-tema", novo);
    } catch {
      // navegação privada bloqueia o storage; o tema vale só nesta aba
    }
    setTema(novo);
  }

  const escuro = tema === "escuro";
  return (
    <button
      onClick={alternar}
      aria-label={escuro ? "Mudar para o tema claro" : "Mudar para o tema escuro"}
      title={escuro ? "Tema claro" : "Tema escuro"}
      className={`flex h-9 w-9 items-center justify-center rounded-full border transition ${className}`}
      style={{ borderColor: "var(--borda)", color: "var(--tinta-2)" }}
    >
      {/* antes da hidratação não sabemos o tema: um traço neutro evita piscar */}
      {tema === null ? (
        <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden className="pointer-events-none">
          <circle cx="8" cy="8" r="5" fill="none" stroke="currentColor" strokeWidth="1.6" />
        </svg>
      ) : escuro ? (
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden className="pointer-events-none">
          <circle cx="8" cy="8" r="3.2" stroke="currentColor" strokeWidth="1.6" />
          {[0, 45, 90, 135, 180, 225, 270, 315].map((g) => (
            <line key={g} x1="8" y1="1.4" x2="8" y2="2.9" stroke="currentColor"
                  strokeWidth="1.6" strokeLinecap="round"
                  transform={`rotate(${g} 8 8)`} />
          ))}
        </svg>
      ) : (
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden className="pointer-events-none">
          <path d="M13.4 9.6A5.8 5.8 0 016.4 2.6a5.8 5.8 0 107 7z"
                stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
        </svg>
      )}
    </button>
  );
}
