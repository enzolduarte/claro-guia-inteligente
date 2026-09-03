"use client";

/**
 * O Guia Inteligente como widget flutuante — a tese do produto em forma de
 * componente: ele não é uma página, é um assistente que se acopla a QUALQUER
 * plataforma da Claro (site, app, portal de faturas).
 *
 * Integração com a página hospedeira: qualquer elemento pode disparar
 *   window.dispatchEvent(new CustomEvent("guia:pergunta", { detail: "texto" }))
 * e o widget abre e pergunta. É assim que os cards do portal falam com ele.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import type { InterpretResponse, Option } from "@/lib/contract";
import { Badge } from "./Badge";
import { RoutingCard } from "./RoutingCard";

interface Turno {
  autor: "cliente" | "assistente";
  texto: string;
  resposta?: InterpretResponse;
}

const SAUDACAO =
  "Oi! Sou o Guia Inteligente da Claro. Me conta com suas palavras o que você precisa: fatura, internet, plano ou outro assunto.";

export function ChatWidget() {
  const [aberto, setAberto] = useState(false);
  const [turnos, setTurnos] = useState<Turno[]>([
    { autor: "assistente", texto: SAUDACAO },
  ]);
  const [texto, setTexto] = useState("");
  const [aguardando, setAguardando] = useState(false);
  const [naoLidas, setNaoLidas] = useState(0);
  const fimRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const abertoRef = useRef(aberto);
  abertoRef.current = aberto;

  useEffect(() => {
    fimRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turnos, aguardando, aberto]);

  const enviar = useCallback(async (conteudo: string, rotulo?: string) => {
    const limpo = conteudo.trim();
    if (!limpo) return;
    setTexto("");
    setTurnos((atual) => [...atual, { autor: "cliente", texto: rotulo ?? limpo }]);
    setAguardando(true);
    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: limpo }),
      });
      const resposta = (await r.json()) as InterpretResponse;
      setTurnos((atual) => [
        ...atual,
        { autor: "assistente", texto: resposta.reply, resposta },
      ]);
      if (!abertoRef.current) setNaoLidas((n) => n + 1);
    } catch {
      setTurnos((atual) => [
        ...atual,
        { autor: "assistente", texto: "Tive um problema para responder. Pode tentar de novo?" },
      ]);
    } finally {
      setAguardando(false);
      inputRef.current?.focus();
    }
  }, []);

  // A ponte com a plataforma hospedeira.
  useEffect(() => {
    function aoPedir(evento: Event) {
      const detalhe = (evento as CustomEvent<string>).detail;
      if (typeof detalhe === "string" && detalhe.trim()) {
        setAberto(true);
        void enviar(detalhe);
      }
    }
    const aoAbrir = () => setAberto(true);
    window.addEventListener("guia:pergunta", aoPedir);
    window.addEventListener("guia:abrir", aoAbrir);
    return () => {
      window.removeEventListener("guia:pergunta", aoPedir);
      window.removeEventListener("guia:abrir", aoAbrir);
    };
  }, [enviar]);

  useEffect(() => {
    if (aberto) {
      setNaoLidas(0);
      inputRef.current?.focus();
    }
  }, [aberto]);

  const ultima = turnos[turnos.length - 1]?.resposta;
  const opcoesAtivas: Option[] =
    ultima?.state === "CLARIFICANDO" && ultima.options ? ultima.options : [];

  return (
    <>
      {/* painel */}
      {aberto && (
        <div className="fixed inset-x-3 bottom-24 z-50 flex max-h-[75dvh] flex-col overflow-hidden rounded-2xl border shadow-2xl sm:inset-x-auto sm:right-6 sm:w-[380px]"
          style={{ borderColor: "var(--borda)", background: "var(--superficie-2)" }}>
          <header className="flex items-center gap-3 bg-gradient-to-r from-claro-red to-claro-dark px-4 py-3 text-white">
            <div className="flex h-8 items-center rounded-lg bg-white px-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/logo-claro.svg" alt="" className="h-5 w-auto" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-bold leading-tight">Guia Inteligente</p>
              <p className="flex items-center gap-1.5 text-[11px] text-white/80">
                <span className="h-1.5 w-1.5 rounded-full bg-green-300" /> online agora
              </p>
            </div>
            <button
              onClick={() => setAberto(false)}
              aria-label="Fechar assistente"
              className="rounded-full p-1.5 transition hover:bg-white/15"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
                <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
            </button>
          </header>

          <div className="flex-1 space-y-3 overflow-y-auto px-3 py-3" style={{ background: "var(--fundo)" }}>
            {turnos.map((turno, i) => (
              <div
                key={i}
                className={turno.autor === "cliente" ? "flex justify-end" : "flex justify-start"}
              >
                <div className="max-w-[88%]">
                  <div
                    className={
                      turno.autor === "cliente"
                        ? "rounded-2xl rounded-br-sm bg-claro-red px-3.5 py-2 text-sm text-white"
                        : "rounded-2xl rounded-bl-sm border px-3.5 py-2 text-sm shadow-sm"
                    }
                    style={
                      turno.autor === "cliente"
                        ? undefined
                        : { borderColor: "var(--borda)", background: "var(--superficie-2)", color: "var(--tinta)" }
                    }
                  >
                    <p className="whitespace-pre-wrap">{turno.texto}</p>
                  </div>
                  {turno.resposta?.routing && <RoutingCard routing={turno.resposta.routing} />}
                  {turno.resposta && <Badge resposta={turno.resposta} />}
                </div>
              </div>
            ))}
            {aguardando && (
              <div className="flex justify-start">
                <div className="rounded-2xl rounded-bl-sm border px-4 py-2.5 shadow-sm"
                     style={{ borderColor: "var(--borda)", background: "var(--superficie-2)" }}>
                  <span className="flex gap-1">
                    {[0, 150, 300].map((atraso) => (
                      <span
                        key={atraso}
                        className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400"
                        style={{ animationDelay: `${atraso}ms` }}
                      />
                    ))}
                  </span>
                </div>
              </div>
            )}
            <div ref={fimRef} />
          </div>

          {opcoesAtivas.length > 0 && !aguardando && (
            <div className="flex flex-wrap gap-1.5 border-t px-3 py-2"
              style={{ borderColor: "var(--borda)", background: "var(--superficie-2)" }}>
              {opcoesAtivas.map((opcao) => (
                <button
                  key={opcao.id}
                  onClick={() => void enviar(opcao.id, opcao.label)}
                  className="rounded-full border border-claro-red px-3 py-1.5 text-xs font-medium text-claro-red transition hover:bg-claro-red hover:text-white"
                >
                  {opcao.label}
                </button>
              ))}
            </div>
          )}

          <form
            onSubmit={(e) => {
              e.preventDefault();
              void enviar(texto);
            }}
            className="flex gap-2 border-t px-3 py-2.5"
            style={{ borderColor: "var(--borda)", background: "var(--superficie-2)" }}
          >
            <input
              ref={inputRef}
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              placeholder="Escreva sua mensagem…"
              className="flex-1 rounded-full border px-4 py-2 text-sm outline-none transition focus:border-claro-red"
              style={{ borderColor: "var(--borda)", background: "var(--fundo)", color: "var(--tinta)" }}
            />
            <button
              type="submit"
              disabled={aguardando || !texto.trim()}
              aria-label="Enviar"
              className="flex h-9 w-9 items-center justify-center rounded-full bg-claro-red text-white transition enabled:hover:bg-claro-dark disabled:opacity-40"
            >
              <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden>
                <path d="M2 8h11M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </form>
        </div>
      )}

      {/* bolinha */}
      <button
        onClick={() => setAberto((v) => !v)}
        aria-label={aberto ? "Fechar assistente" : "Abrir assistente"}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-claro-red text-white shadow-lg shadow-claro-red/40 transition hover:scale-105 hover:bg-claro-dark"
      >
        {aberto ? (
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden>
            <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        ) : (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path
              d="M12 3C7 3 3 6.6 3 11c0 2 .9 3.9 2.4 5.3-.2 1-.7 2.2-1.7 3.2 1.8.1 3.4-.4 4.6-1.1 1.1.4 2.4.6 3.7.6 5 0 9-3.6 9-8S17 3 12 3z"
              fill="currentColor"
            />
          </svg>
        )}
        {!aberto && naoLidas > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-white text-[10px] font-bold text-claro-red shadow">
            {naoLidas}
          </span>
        )}
      </button>
    </>
  );
}
