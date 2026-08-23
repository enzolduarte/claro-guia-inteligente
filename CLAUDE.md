# CLAUDE.md — Claro Guia Inteligente

> Contexto permanente do projeto. Leia antes de qualquer tarefa.
> Challenge 2026 · FIAP 4SI · Time Adamanto AI · entrega 04/09/2026

---

## 1. O que é este projeto

Um **assistente de roteamento conversacional**. Recebe uma mensagem em linguagem natural,
de qualquer canal, descobre a intenção do cliente e o encaminha ao fluxo de atendimento correto.

**Ele roteia — não resolve.** Não emite boleto, não troca plano, não estorna cobrança.
Ele entende, decide o destino e explica o próximo passo. Qualquer implementação que
tente "resolver" o pedido do cliente está errada.

```
ENTRADA (canais)              NÚCLEO                 SAÍDA (fluxos)
Web ──────────┐                                 ┌──→ Financeiro (fatura, 2ª via)
Telegram ─────┼──→ POST /v1/interpret ──────────┼──→ Suporte técnico
(futuro) ─────┘    classifica e decide          ├──→ Comercial (plano, compra)
                                                 └──→ Atendimento humano
```

---

## 2. Arquitetura

Dois deployables, três containers.

| Serviço | Stack | Papel | Porta |
|---|---|---|---|
| `core` | FastAPI · Python 3.11 | Cérebro: classificação, estado, roteamento, geração | 8000 (interna) |
| `web` | Next.js 14 App Router · TS | UI conversacional + BFF | 3000 (exposta) |
| `telegram` | Python | Adaptador por long polling | nenhuma |

**Somente `web` publica porta.** O `core` vive na rede interna do compose.

**Adaptadores são finos.** Traduzem o formato do canal para o contrato e devolvem.
Nenhuma regra de negócio mora em adaptador.

---

## 3. Contrato — CONGELADO, não alterar

```jsonc
// POST /v1/interpret
{
  "session_id": "web:uuid | telegram:123456",
  "channel": "web" | "telegram",
  "text": "minha conta veio mais cara"
}

// 200 OK
{
  "session_id": "web:uuid",
  "state": "ROTEANDO",              // AGUARDANDO|PROCESSANDO|CLARIFICANDO|
                                    // RESPONDENDO|ROTEANDO|ESCALANDO|ENCERRADO
  "intent": "FATURA",               // null quando não identificada
  "confidence": 0.94,
  "confidence_band": "ALTO",        // ALTO | MEDIO | BAIXO
  "confidence_source": "embedding", // regra | embedding | nenhuma
  "reply": "texto para o usuário",
  "reply_source": "generative",     // generative | template | fallback
  "options": [                      // preenchido quando state = CLARIFICANDO
    { "id": "upgrade", "label": "Fazer upgrade do plano" }
  ],
  "routing": {                      // preenchido quando ROTEANDO | ESCALANDO
    "destination": "FLUXO_FINANCEIRO",
    "label": "Portal de Faturas Claro",
    "url": "https://…",
    "protocol": "CLR-2026-48291"
  },
  "latency_ms": 812
}
```

`options` e `routing` são `null` quando não se aplicam. Nunca omita as chaves.

---

## 4. Pipeline de decisão — a ordem é obrigatória

```
0. Se o estado anterior era CLARIFICANDO → resolve a opção escolhida → pula para 4
1. VERIFICADOR DE SENSIBILIDADE   regras determinísticas → ESCALANDO, fim
2. REGRAS DE ALTA PRECISÃO        palavra-chave → confidence 0.97, source "regra"
3. EMBEDDINGS                     cosseno → confidence real, source "embedding"
   3a. BAIXO (<0,60)              → pergunta aberta, AGUARDANDO, fim
   3b. sempre_clarificar          → CLARIFICANDO com opções, fim
   3c. MÉDIO (0,60–0,79)          → CLARIFICANDO confirmação, fim
4. MOTOR DE ROTEAMENTO            destino do flows.json; sem destino → ATENDIMENTO_HUMANO
5. GERAÇÃO ANCORADA               Gemini reescreve o roteiro; timeout 3s → texto canônico
6. TELEMETRIA                     grava o evento
```

**A sensibilidade roda antes do classificador.** Cobrança indevida nunca chega à IA.
**`sempre_clarificar` é avaliado antes da banda.** PLANO com score 0,95 ainda clarifica —
a ambiguidade é semântica, não de confiança.

---

## 5. Regras invioláveis

1. **O LLM é redator, não decisor.** O destino sai de código determinístico. O Gemini
   recebe o roteiro pronto do `flows.json` e só reescreve no tom de voz. Ele nunca
   escolhe para onde rotear e nunca inventa URL, protocolo ou passo.
2. **Catálogo de destinos é fechado.** Se a intenção não tem destino mapeado,
   o resultado é `ATENDIMENTO_HUMANO`. Nunca inferir.
3. **O sistema roda sem nenhuma chave de API.** Sem `GEMINI_API_KEY` responde com os
   roteiros canônicos. Sem `TELEGRAM_BOT_TOKEN` o adaptador não sobe. Isso não é
   opcional — é requisito de avaliação.
4. **Nenhum dado real de cliente.** Tudo fictício.
5. **`flows.json` é a única fonte de verdade** para intenções, exemplos, destinos e roteiros.
   Nenhuma dessas coisas hardcoded em Python.

---

## 6. Configuração — nunca hardcode

Tudo por variável de ambiente, com default sensato:

| Variável | Default | Uso |
|---|---|---|
| `CORE_URL` | `http://localhost:8000` | Onde web e telegram acham o núcleo |
| `GEMINI_API_KEY` | vazio | Sem ela → modo determinístico |
| `TELEGRAM_BOT_TOKEN` | vazio | Sem ele → adaptador não sobe |
| `DB_PATH` | `./data/telemetria.db` | SQLite |
| `FLOWS_PATH` | `./data/flows.json` | Base de conhecimento |
| `EMBEDDING_MODEL` | (definir no M2) | Modelo de embeddings |
| `LLM_TIMEOUT_MS` | `3000` | Timeout do Gemini |
| `CORE_TIMEOUT_MS` | `2500` | Timeout do BFF ao chamar o núcleo |

Nenhum caminho absoluto. Nenhuma URL literal no código.

---

## 7. Padrões de código

**Python**

- Type hints em toda função pública. `from __future__ import annotations`.
- Pydantic v2 para o contrato. Os modelos são a especificação — nada de dict solto.
- Lógica de classificação em **funções puras**, sem I/O. Facilita teste e é o que
  permite reusar as regras no fallback.
- Erros de negócio previstos retornam resposta válida, não exceção. Só bug levanta exceção.
- `ruff` e `black` com defaults. Sem discussão de estilo.

**TypeScript**

- `strict: true`. Sem `any`.
- Tipos do contrato em **um único arquivo** `web/lib/contract.ts`, espelhando o Pydantic.
- Toda chamada ao núcleo é **server-side**. O browser nunca fala com o `core`.

---

## 8. Performance — os pontos que realmente importam

Este projeto tem um requisito de baixa latência (RNF003) e cinco decisões definem se ele
é cumprido. Elas não são microotimização; são diferença entre 20ms e 2s.

1. **Modelo carregado uma vez no lifespan da aplicação**, nunca por requisição.
   Use o `lifespan` do FastAPI.
2. **Embeddings do catálogo pré-computados no boot** e guardados como uma única
   matriz numpy `(n_exemplos, dim)`. Por requisição você faz **um** encode da mensagem
   e **um** produto de matriz. Nunca itere exemplo por exemplo em Python.
3. **Normalize os vetores uma vez** no boot. Com vetores normalizados, cosseno vira
   produto escalar puro — sem divisão por norma a cada chamada.
4. **Regex compilados no import**, nunca dentro da função.
5. **Escolha certa entre `def` e `async def`.** Handler que faz trabalho CPU-bound
   (encode de embedding) deve ser `def` — o FastAPI roda em threadpool e não bloqueia
   o event loop. `async def` só para I/O de rede (chamada ao Gemini). Trocar isso é o
   erro de performance mais comum em FastAPI e derruba a latência sob concorrência.

Também: `lru_cache` na normalização de texto; SQLite com `check_same_thread=False`
e conexão reaproveitada; nenhuma escrita síncrona de telemetria no caminho da resposta
se puder ser feita depois.

**Não otimize nada além disso.** O resto é ruído nesta escala.

---

## 9. Anti-objetivos

Não construa, nem sugira construir:

- Autenticação, login, sessão de usuário real
- Integração com qualquer sistema real da Claro
- Banco gerenciado, ORM, migrations
- WebSocket, streaming de resposta
- Fine-tuning de modelo
- Cache distribuído, fila, worker
- Testes E2E com browser
- CI/CD
- Adaptador de e-mail ou WhatsApp

Escopo é MVP acadêmico com prazo curto. Cada item acima já foi avaliado e rejeitado.

---

## 10. Estrutura de pastas

```
claro-guia-inteligente/
├── CLAUDE.md · README.md · Makefile
├── docker-compose.yml · docker-compose.dev.yml · .env.example
├── core/
│   ├── Dockerfile · requirements.txt
│   ├── app/
│   │   ├── main.py           # FastAPI, lifespan, rotas
│   │   ├── contract.py       # modelos Pydantic
│   │   ├── flows.py          # loader + validação do flows.json
│   │   ├── normalize.py      # normalização de texto
│   │   ├── sensitivity.py    # etapa 1
│   │   ├── rules.py          # etapa 2
│   │   ├── embeddings.py     # etapa 3
│   │   ├── classifier.py     # orquestra 1→2→3
│   │   ├── state_machine.py  # 7 estados + sessão
│   │   ├── routing.py        # etapa 4 + protocolos
│   │   ├── generator.py      # etapa 5 (Gemini + fallback)
│   │   └── telemetry.py      # etapa 6 (SQLite)
│   ├── data/flows.json · data/golden_dataset.json
│   ├── evaluate.py
│   └── tests/
├── web/
│   ├── Dockerfile · next.config.js
│   ├── lib/contract.ts
│   └── app/
│       ├── page.tsx · admin/page.tsx
│       └── api/chat/route.ts
└── adapters/
    ├── README.md
    └── telegram/Dockerfile · bot.py
```

---

## 11. Como trabalhar aqui

- **Um módulo por vez.** Não antecipe trabalho de módulos futuros.
- **Todo módulo termina com seu critério de aceite rodando.** Se não roda, não terminou.
- **Commit ao fim de cada módulo**, mensagem curta em português.
- Se algo no `flows.json` parecer errado, **avise — não conserte sozinho**.
  Ele foi revisado e tem decisões deliberadas.
- Se uma escolha técnica não estiver especificada aqui, escolha a mais simples que
  atenda o critério de aceite e registre em uma linha no commit.
