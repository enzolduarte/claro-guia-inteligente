/**
 * Portal Claro (protótipo acadêmico) — a plataforma hospedeira do Guia.
 *
 * A página é conteúdo estático de portal; toda a inteligência mora no widget
 * flutuante. Os cards e CTAs falam com ele por eventos — nenhum import da
 * lógica de chat aqui. Os textos são escritos para uma pessoa leiga: nada de
 * jargão de produto ou de tecnologia na superfície.
 */

import { AcaoRapida } from "./components/AcaoRapida";
import { BotaoGuia } from "./components/BotaoGuia";
import { ChatWidget } from "./components/ChatWidget";
import { TemaToggle } from "./components/TemaToggle";

const ICONES = {
  fatura: (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path d="M5 2h8l3 3v13H5V2z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M8 9h5M8 12h5M8 15h3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  wifi: (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path d="M2 8a12 12 0 0116 0M5 11.5a8 8 0 0110 0M8 15a4 4 0 014 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="10" cy="17" r="1" fill="currentColor" />
    </svg>
  ),
  plano: (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path d="M3 14l4-4 3 3 7-7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12 6h5v5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  pessoa: (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden>
      <circle cx="10" cy="6.5" r="3.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M3.5 17a6.5 6.5 0 0113 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
};

function Logo() {
  return (
    <a
      href="https://www.claro.com.br"
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Site oficial da Claro (abre em nova aba)"
      className="flex items-center transition hover:opacity-80"
    >
      {/* wordmark oficial com os raios no "o" — dispensa texto ao lado */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/logo-claro.svg" alt="Claro" className="h-9 w-auto" />
    </a>
  );
}

const PLANOS = [
  {
    nome: "Fibra 350 mega",
    preco: "89,90",
    detalhes: ["Wi-Fi grátis para a casa toda", "Instalação sem custo", "Aplicativo para acompanhar tudo"],
    destaque: false,
  },
  {
    nome: "Fibra 500 mega",
    preco: "99,90",
    detalhes: ["Ideal para filmes e jogos online", "Wi-Fi de última geração", "Suporte 24 horas"],
    destaque: true,
  },
  {
    nome: "Fibra 700 mega",
    preco: "129,90",
    detalhes: ["Para casas com muita gente conectada", "Velocidade máxima da região", "Técnico prioritário"],
    destaque: false,
  },
];

const PASSOS = [
  {
    numero: "1",
    titulo: "Você escreve",
    texto: "Do seu jeito, como mandaria mensagem para um amigo: “minha internet caiu”, “a conta veio cara”.",
  },
  {
    numero: "2",
    titulo: "O Guia entende",
    texto: "Ele descobre do que você precisa. Se ficar em dúvida, pergunta antes de decidir. Nunca chuta.",
  },
  {
    numero: "3",
    titulo: "Você resolve",
    texto: "O Guia te leva direto ao lugar certo: a página da fatura, o suporte ou uma pessoa de verdade.",
  },
];

export default function Page() {
  return (
    <div className="min-h-dvh" style={{ background: "var(--fundo)" }}>
      <header className="sticky top-0 z-40 border-b backdrop-blur"
              style={{ borderColor: "var(--borda)", background: "var(--superficie-2)" }}>
        <div className="mx-auto flex max-w-[1440px] items-center justify-between px-6 py-3 lg:px-12">
          <Logo />
          <nav className="hidden items-center gap-8 text-sm font-medium md:flex"
               style={{ color: "var(--tinta-2)" }}>
            <a href="#planos" className="transition hover:text-claro-red">Planos</a>
            <a href="#servicos" className="transition hover:text-claro-red">Fatura</a>
            <a href="#servicos" className="transition hover:text-claro-red">Suporte</a>
            <a href="#como-funciona" className="transition hover:text-claro-red">Como funciona</a>
          </nav>
          <div className="flex items-center gap-2">
            <TemaToggle />
            <BotaoGuia className="rounded-full bg-claro-red px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-claro-dark">
              Falar com o Guia
            </BotaoGuia>
          </div>
        </div>
      </header>

      <section className="bg-gradient-to-br from-claro-red via-[#cf0027] to-claro-dark text-white">
        <div className="mx-auto grid max-w-[1440px] items-center gap-10 px-6 py-14 md:grid-cols-2 md:py-20 lg:px-12">
          <div>
            <p className="mb-3 inline-block rounded-full bg-white/15 px-3 py-1 text-xs font-semibold uppercase tracking-wider">
              Guia Inteligente · seu atendimento sem fila
            </p>
            <h1 className="text-4xl font-extrabold leading-tight lg:text-6xl">
              Fale do seu jeito.
              <br />A gente encontra o caminho.
            </h1>
            <p className="mt-4 max-w-lg text-base leading-relaxed text-white/85 lg:text-lg">
              Escreva o que você precisa: a conta que veio errada, a internet
              que caiu, um plano novo. O Guia te leva até a solução em segundos,
              sem menu, sem espera e sem repetir sua história.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <BotaoGuia className="rounded-full bg-white px-6 py-3 text-sm font-bold text-claro-red transition hover:bg-white/90">
                Começar uma conversa
              </BotaoGuia>
              <BotaoGuia
                pergunta="quero a 2a via da fatura"
                className="rounded-full border border-white/50 px-6 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
              >
                Pegar a 2ª via da fatura
              </BotaoGuia>
            </div>
          </div>
          <div className="hidden justify-center md:flex">
            <div className="w-full max-w-md rounded-3xl bg-white/10 p-6 backdrop-blur">
              <p className="text-xs font-semibold uppercase tracking-wider text-white/70">
                o mesmo assistente, onde você estiver
              </p>
              <ul className="mt-4 space-y-3 text-sm lg:text-base">
                {[
                  "No site, como esta bolinha vermelha aí do lado",
                  "No Telegram, conversando normalmente",
                  "No aplicativo Minha Claro",
                  "E ele lembra de você em todos eles",
                ].map((canal) => (
                  <li key={canal} className="flex items-start gap-3">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/20 text-[10px]">✓</span>
                    {canal}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section id="servicos" className="mx-auto max-w-[1440px] px-6 py-14 lg:px-12">
        <h2 className="text-2xl font-bold" style={{ color: "var(--tinta)" }}>O que você precisa hoje?</h2>
        <p className="mt-1 text-sm lg:text-base" style={{ color: "var(--tinta-2)" }}>
          Toque em um assunto e o Guia já começa a resolver com você.
        </p>
        <div className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <AcaoRapida
            titulo="Minha conta e pagamento"
            descricao="Pegue o boleto de novo, veja o código de barras ou entenda o valor que veio."
            pergunta="quero a 2a via da fatura"
            icone={ICONES.fatura}
          />
          <AcaoRapida
            titulo="Internet ou TV com problema"
            descricao="Caiu, está lenta ou sem sinal? A verificação começa na hora."
            pergunta="minha internet esta caindo toda hora"
            icone={ICONES.wifi}
          />
          <AcaoRapida
            titulo="Mudar meu plano"
            descricao="Aumentar, economizar ou só ver o que existe. Você escolhe com calma."
            pergunta="quero mudar meu plano"
            icone={ICONES.plano}
          />
          <AcaoRapida
            titulo="Falar com uma pessoa"
            descricao="Você vai direto para um atendente, que já recebe tudo o que você contou."
            pergunta="quero falar com um atendente"
            icone={ICONES.pessoa}
          />
        </div>
      </section>

      <section id="como-funciona" className="border-y" style={{ borderColor: "var(--borda)", background: "var(--superficie-2)" }}>
        <div className="mx-auto max-w-[1440px] px-6 py-14 lg:px-12">
          <h2 className="text-2xl font-bold" style={{ color: "var(--tinta)" }}>Como funciona</h2>
          <p className="mt-1 text-sm lg:text-base" style={{ color: "var(--tinta-2)" }}>
            Três passos, nenhum menu de “digite 1 para…”.
          </p>
          <div className="mt-8 grid gap-8 md:grid-cols-3">
            {PASSOS.map((passo) => (
              <div key={passo.numero} className="relative rounded-2xl border p-6" style={{ borderColor: "var(--borda)", background: "var(--fundo)" }}>
                <span className="absolute -top-4 left-6 flex h-9 w-9 items-center justify-center rounded-full bg-claro-red text-sm font-extrabold text-white shadow">
                  {passo.numero}
                </span>
                <h3 className="mt-3 text-base font-bold" style={{ color: "var(--tinta)" }}>{passo.titulo}</h3>
                <p className="mt-2 text-sm leading-relaxed" style={{ color: "var(--tinta-2)" }}>{passo.texto}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="planos" className="mx-auto max-w-[1440px] px-6 py-14 lg:px-12">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 className="text-2xl font-bold" style={{ color: "var(--tinta)" }}>Planos de internet</h2>
            <p className="mt-1 text-sm lg:text-base" style={{ color: "var(--tinta-2)" }}>
              Valores ilustrativos do protótipo. Quer saber o que funciona na sua casa? Pergunte ao Guia.
            </p>
          </div>
          <BotaoGuia
            pergunta="quero contratar internet"
            className="text-sm font-semibold text-claro-red transition hover:text-claro-dark"
          >
            Ver cobertura na minha região →
          </BotaoGuia>
        </div>
        <div className="mt-6 grid gap-5 md:grid-cols-3">
          {PLANOS.map((plano) => (
            <div
              key={plano.nome}
              className={`relative flex flex-col rounded-2xl border p-6 shadow-sm ${
                plano.destaque ? "border-claro-red ring-1 ring-claro-red" : ""
              }`}
              style={{
                background: "var(--superficie-2)",
                borderColor: plano.destaque ? undefined : "var(--borda)",
              }}
            >
              {plano.destaque && (
                <span className="absolute -top-3 left-6 rounded-full bg-claro-red px-3 py-0.5 text-[11px] font-bold uppercase tracking-wide text-white">
                  mais escolhido
                </span>
              )}
              <h3 className="text-base font-bold" style={{ color: "var(--tinta)" }}>{plano.nome}</h3>
              <p className="mt-2 text-3xl font-extrabold" style={{ color: "var(--tinta)" }}>
                <span className="align-top text-sm font-semibold">R$ </span>
                {plano.preco}
                <span className="text-sm font-medium" style={{ color: "var(--tinta-3)" }}>/mês</span>
              </p>
              <ul className="mt-4 flex-1 space-y-2 text-sm" style={{ color: "var(--tinta-2)" }}>
                {plano.detalhes.map((item) => (
                  <li key={item} className="flex items-start gap-2">
                    <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-claro-red" />
                    {item}
                  </li>
                ))}
              </ul>
              <BotaoGuia
                pergunta={`quero contratar o plano ${plano.nome.toLowerCase()}`}
                className={`mt-5 rounded-full px-4 py-2.5 text-sm font-bold transition ${
                  plano.destaque
                    ? "bg-claro-red text-white hover:bg-claro-dark"
                    : "border border-claro-red text-claro-red hover:bg-claro-red hover:text-white"
                }`}
              >
                Quero este plano
              </BotaoGuia>
            </div>
          ))}
        </div>
      </section>

      <section className="bg-gradient-to-r from-claro-red to-claro-dark text-white">
        <div className="mx-auto grid max-w-[1440px] gap-6 px-6 py-10 text-center sm:grid-cols-3 lg:px-12">
          {[
            { numero: "1 frase", texto: "é o que basta para começar a resolver" },
            { numero: "3 canais", texto: "site, aplicativo e Telegram com o mesmo Guia" },
            { numero: "0 repetição", texto: "quem te atende já sabe o que você contou" },
          ].map((item) => (
            <div key={item.numero}>
              <p className="text-3xl font-extrabold lg:text-4xl">{item.numero}</p>
              <p className="mt-1 text-sm text-white/80">{item.texto}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-b" style={{ borderColor: "var(--borda)", background: "var(--superficie-2)" }}>
        <div className="mx-auto grid max-w-[1440px] gap-10 px-6 py-14 md:grid-cols-3 lg:px-12">
          {[
            {
              titulo: "Escreva como você fala",
              texto:
                "Nada de apertar 1, 2 ou 3. Conte o que aconteceu com as suas palavras. Pode ser “minha net caiu” ou “a conta veio um absurdo”, que o Guia entende.",
            },
            {
              titulo: "Ele pergunta antes de decidir",
              texto:
                "Quando a sua mensagem pode significar mais de uma coisa, o Guia confirma com você em vez de te mandar para o lugar errado.",
            },
            {
              titulo: "Gente de verdade quando importa",
              texto:
                "Problema com cobrança é coisa séria: você vai direto para uma pessoa especializada, com número de protocolo e sem contar tudo de novo.",
            },
          ].map((item) => (
            <div key={item.titulo}>
              <h3 className="text-base font-bold" style={{ color: "var(--tinta)" }}>{item.titulo}</h3>
              <p className="mt-2 text-sm leading-relaxed lg:text-base" style={{ color: "var(--tinta-2)" }}>{item.texto}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="bg-claro-ink text-gray-400">
        <div className="mx-auto max-w-[1440px] px-6 py-10 lg:px-12">
          <div className="grid gap-8 sm:grid-cols-3">
            <div>
              <p className="text-sm font-bold text-white">Atendimento</p>
              <ul className="mt-2 space-y-1.5 text-xs">
                <li>Guia Inteligente, a bolinha vermelha no canto</li>
                <li>Telegram: @ClaroGuiaBot (protótipo)</li>
                <li>App Minha Claro</li>
              </ul>
            </div>
            <div>
              <p className="text-sm font-bold text-white">Serviços</p>
              <ul className="mt-2 space-y-1.5 text-xs">
                <li>2ª via de fatura</li>
                <li>Suporte técnico</li>
                <li>Planos e cobertura</li>
              </ul>
            </div>
            <div>
              <p className="text-sm font-bold text-white">Sobre este site</p>
              <p className="mt-2 text-xs leading-relaxed">
                Protótipo acadêmico do Challenge 2026 (FIAP 4SI · Time Adamanto
                AI). Dados e valores fictícios. Sem vínculo com a Claro S.A.
                Endereços de destino ilustrativos.
              </p>
            </div>
          </div>
        </div>
      </footer>

      <ChatWidget />
    </div>
  );
}
