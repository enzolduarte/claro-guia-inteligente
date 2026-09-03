import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Claro · Guia Inteligente",
  description:
    "Assistente de roteamento conversacional. Protótipo acadêmico do Challenge 2026, FIAP.",
};

/**
 * Reaplica o tema salvo ANTES da primeira pintura. Sem isto, quem escolheu o
 * escuro vê um lampejo branco a cada carregamento. Precisa ser síncrono e
 * inline, por isso não dá para ser um componente.
 */
const SEM_PISCADA = `
try {
  var t = localStorage.getItem('cgi-tema');
  if (t === 'escuro') document.documentElement.dataset.theme = 'dark';
  else if (t === 'claro') document.documentElement.dataset.theme = 'light';
} catch (e) {}
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: SEM_PISCADA }} />
      </head>
      <body
        className="antialiased"
        style={{ background: "var(--fundo)", color: "var(--tinta)" }}
      >
        {children}
      </body>
    </html>
  );
}
