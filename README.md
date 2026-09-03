# Claro Guia Inteligente

Assistente de roteamento conversacional para os canais digitais da Claro. O
cliente escreve o que precisa com as próprias palavras e o sistema o encaminha
ao fluxo de atendimento correto, no site ou no Telegram, com a mesma decisão nos
dois. **Ele roteia, não resolve:** entende o pedido, escolhe o destino e explica
o próximo passo, sem emitir boleto, trocar plano nem estornar cobrança.

> Protótipo acadêmico. Challenge 2026 · FIAP 4SI · Time Adamanto AI.
> Dados e valores fictícios, sem vínculo com a Claro S.A.

---

## Índice

1. [O que é](#1-o-que-é)
2. [Arquitetura](#2-arquitetura)
3. [Pré-requisitos](#3-pré-requisitos)
4. [Como rodar](#4-como-rodar)
5. [Modo completo (opcional)](#5-modo-completo-opcional)
6. [Variáveis de ambiente](#6-variáveis-de-ambiente)
7. [Contrato da API](#7-contrato-da-api)
8. [Como testar a classificação](#8-como-testar-a-classificação)
9. [Requisitos atendidos](#9-requisitos-atendidos)
10. [Estrutura do projeto](#10-estrutura-do-projeto)
11. [Desenvolvimento](#11-desenvolvimento)
12. [Problemas comuns](#12-problemas-comuns)
13. [Limitações conhecidas](#13-limitações-conhecidas)
14. [Time](#14-time)

---

## 1. O que é

Uma porta de entrada conversacional para os canais digitais da Claro: recebe uma
mensagem em linguagem natural, descobre a intenção do cliente e o encaminha ao
fluxo certo, com link e número de protocolo.

Resolve a fragmentação em que o cliente sente que fala com "várias empresas"
diferentes ao transitar entre site, aplicativo e atendimento, porque a decisão
acontece **num lugar só** e vale para todos os canais.

Sete intenções cobertas: fatura, segunda via, suporte técnico, troca de plano,
compra, cobrança indevida e atendimento humano.

---

## 2. Arquitetura

```
   CANAIS                    NÚCLEO                      DESTINOS

  Navegador                                          ┌─→ Fluxo financeiro
      │                                              │
      ↓                                              ├─→ Segunda via
  ┌────────┐                ┌──────────────┐         │
  │  web   │───────────────→│              │         ├─→ Suporte técnico
  │  BFF   │  /v1/interpret │    core      │         │
  └────────┘                │              │────────→├─→ Comercial: upgrade,
                            │  1 sensível  │         │   economia, catálogo
  ┌────────┐                │  2 regras    │         │
  │telegram│───────────────→│  3 embedding │         ├─→ Vendas
  │adapter │  /v1/interpret │  4 rota      │         │
  └────────┘                │  5 redação   │         └─→ Escalação humana
      ↑                     │  6 registro  │
      │                     └──────┬───────┘
  Telegram                         │
                            ┌──────┴───────┐
                            │ flows.json   │  base de conhecimento
                            │ telemetria   │  volume `dados`
                            └──────────────┘
```

Três containers. **Só o `web` publica porta.** O navegador nunca fala com o
núcleo: toda chamada passa pelo servidor do Next.js, que conhece o endereço
interno da rede do compose.

| Container | Stack | Papel | Porta | Imagem |
|---|---|---|---|---|
| `core` | Python 3.13 · FastAPI | classificação, estado, roteamento, redação, telemetria | 8000, interna | 2,7 GB |
| `web` | Node 20 · Next.js 14 | portal, painel e BFF | **3000, exposta** | 223 MB |
| `telegram` | Python 3.13 | adaptador por long polling, opcional | nenhuma | 193 MB |

A diferença de tamanho não é acidente: o `core` carrega o PyTorch e o modelo de
similaridade, e os outros dois **não têm uma linha de código de aprendizado de
máquina**. É a separação entre cérebro e canais, visível na balança.

O diagrama completo está em [`docs/arquitetura.svg`](docs/arquitetura.svg). A
versão interativa, com tema claro e escuro, modo apresentação e quatro recortes
guiados, está em [`docs/arquitetura.html`](docs/arquitetura.html): baixe e abra
no navegador.

---

## 3. Pré-requisitos

**Docker 24 ou mais novo, com Docker Compose v2.** Nada além disso.

```bash
docker --version && docker compose version
```

Não é preciso instalar Python, Node, PyTorch nem criar conta em serviço nenhum.
Tudo o que o sistema usa vai dentro das imagens.

---

## 4. Como rodar

```bash
git clone https://github.com/enzolduarte/claro-guia-inteligente.git
cd claro-guia-inteligente
docker compose up --build
```

Quando aparecer que os dois containers estão saudáveis, abra:

- **http://localhost:3000** o portal, com o assistente na bolinha à direita
- **http://localhost:3000/admin** o painel operacional

> ### Roda sem nenhuma chave de API
>
> Os três comandos acima são tudo. **Não crie conta, não copie arquivo, não
> configure nada.** Sem chave do Gemini o assistente responde com os textos
> escritos no `flows.json`, e o roteamento, o destino, o link e o protocolo são
> exatamente os mesmos: o modelo de linguagem é redator, nunca decisor. Sem
> token do Telegram, o canal simplesmente não sobe.

**Tempo esperado.** A primeira construção leva de **4 a 6 minutos**, porque
baixa o PyTorch e o modelo de similaridade de 458 MB. É a única vez. Depois
disso o sistema fica **saudável e atendendo em 17 segundos**, porque o modelo já
está dentro da imagem e não é buscado na rede.

Experimente escrever no assistente:

| Frase | O que acontece |
|---|---|
| `minha conta veio mais cara esse mês` | roteia para o detalhamento de fatura, com link |
| `quero mudar meu plano` | aparecem três alternativas, porque o pedido é ambíguo |
| `tem uma cobrança que eu não reconheço` | escala para especialista, com protocolo |
| `oi` | pergunta aberta, sem chutar destino |

Para desligar: `Ctrl+C`, e depois `docker compose down`.

---

## 5. Modo completo (opcional)

Duas coisas que o sistema **não precisa** para funcionar, e que só valem a pena
se você quiser ver a experiência completa.

### 5.1 Respostas reescritas por IA generativa

Sem isto, as respostas saem com os textos do `flows.json`, que são corretos mas
sempre iguais. Com a chave, o Gemini reescreve o mesmo conteúdo num tom mais
natural, **sem poder mudar o destino**.

**Passo 1.** Pegue uma chave gratuita em
[aistudio.google.com/apikey](https://aistudio.google.com/apikey).

**Passo 2.** Copie o modelo de configuração:

```bash
cp .env.example .env
```

**Passo 3.** Abra o `.env` e cole a chave na linha `GEMINI_API_KEY=`.

**Passo 4.** Suba de novo:

```bash
docker compose up --build
```

Para conferir se pegou, olhe o rodapé de uma resposta no painel: a origem passa
de `template` para `generative`.

### 5.2 Canal de Telegram

**Passo 1.** No Telegram, procure o **@BotFather**, mande `/newbot` e escolha um
nome. Ele devolve um token.

**Passo 2.** Cole o token na linha `TELEGRAM_BOT_TOKEN=` do `.env`.

**Passo 3.** Suba com o perfil do Telegram ligado:

```bash
docker compose --profile telegram up --build
```

**Passo 4.** Procure o seu bot no Telegram e mande uma mensagem.

Um bot de Telegram é público: quem descobrir o nome dele consegue conversar e
gastar sua cota do Gemini. Para fechar só para você, veja o número do seu chat
no registro do container (`chat=123456789`) e coloque em
`TELEGRAM_ALLOWED_CHATS=` no `.env`.

O teste que importa: mande a **mesma frase** no site e no Telegram. O destino, o
link e o rótulo têm que ser idênticos. É a proposta do projeto.

---

## 6. Variáveis de ambiente

Todas opcionais, todas com valor padrão. Ficam num arquivo `.env` na raiz, criado
a partir do `.env.example`.

| Variável | Padrão | Quem lê | Para que serve |
|---|---|---|---|
| `GEMINI_API_KEY` | vazio | núcleo | sem ela, o sistema usa os textos do `flows.json` |
| `GEMINI_MODEL` | `gemini-flash-lite-latest` | núcleo | modelo usado na redação |
| `LLM_TIMEOUT_MS` | `8000` | núcleo | espera pela resposta do Gemini |
| `EMBEDDING_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | núcleo | modelo de similaridade |
| `DB_PATH` | `/data/telemetria.db` no Docker, `./data/telemetria.db` fora | núcleo | banco da telemetria |
| `FLOWS_PATH` | `./data/flows.json` | núcleo | base de conhecimento |
| `TELEGRAM_BOT_TOKEN` | vazio | Telegram | sem ele, o canal não sobe |
| `TELEGRAM_ALLOWED_CHATS` | vazio | Telegram | `chat_id` liberados, separados por vírgula |
| `TELEGRAM_POLL_TIMEOUT_S` | `30` | Telegram | quanto tempo cada espera segura a conexão |
| `CORE_URL` | `http://core:8000` | site e Telegram | onde achar o núcleo |
| `CORE_TIMEOUT_MS` | `2500` | site e Telegram | espera pelo núcleo antes de desistir |
| `WEB_PORT` | `3000` | compose | porta publicada, se a 3000 estiver ocupada |

A coluna "quem lê" existe porque a divisão importa: o núcleo não conhece
`CORE_URL` nem o token do bot, e o adaptador não conhece a chave do Gemini. Cada
processo lê só o que é dele, e é o que mantém os canais finos.

Quem também roda sem Docker pode manter as chaves em `core/.env`. O compose lê
os dois arquivos, e `core/.env` vence, então não é preciso duplicar nada. Os
dois estão no `.gitignore`.

---

## 7. Contrato da API

Documentação interativa em **http://localhost:3000** para o cliente final e, em
desenvolvimento, em `http://localhost:8000/docs` para a API crua.

### Requisição

```jsonc
POST /v1/interpret
{
  // "{canal}:{id}". O núcleo trata como texto opaco: nunca separa o canal
  // do id, nunca muda de comportamento por causa dele. Só precisa ser
  // estável entre mensagens da mesma pessoa.
  "session_id": "web:8f3a1c2e-4b7d-11f0-a1b2",
  "channel": "web",                       // "web" | "telegram"
  "text": "minha conta veio mais cara"
}
```

### Resposta

```jsonc
{
  "session_id": "web:8f3a1c2e-4b7d-11f0-a1b2",

  // AGUARDANDO | PROCESSANDO | CLARIFICANDO | RESPONDENDO
  // ROTEANDO   | ESCALANDO   | ENCERRADO
  "state": "ROTEANDO",

  "intent": "FATURA",                     // null quando não identificada
  "confidence": 0.97,
  "confidence_band": "ALTO",              // ALTO | MEDIO | BAIXO
  "confidence_source": "regra",           // regra | embedding | nenhuma

  // Texto pronto para mostrar. Use como veio, sem reescrever.
  "reply": "Se você tem dúvida sobre o valor da sua fatura...",

  // generative = reescrito pelo Gemini
  // template   = texto do flows.json (o Gemini falhou ou não tem chave)
  // fallback   = o núcleo não respondeu e o site classificou sozinho
  "reply_source": "template",

  // Preenchido quando state = CLARIFICANDO. Vire botões, lista numerada,
  // o que o canal permitir. A escolha volta como `text` do turno seguinte,
  // mandando o `id`.
  "options": null,

  // Preenchido quando state = ROTEANDO ou ESCALANDO.
  "routing": {
    "destination": "FLUXO_FINANCEIRO",
    "label": "Detalhamento de Fatura",
    "url": "https://www.claro.com.br/minha-claro/faturas",
    "protocol": null                      // só em escalação para humano
  },

  "latency_ms": 12
}
```

`options` e `routing` são **sempre presentes**, valendo `null` quando não se
aplicam. Nunca são omitidos, então dá para checar direto sem se preocupar com
chave faltando.

Como escrever um adaptador para um canal novo:
[`adapters/README.md`](adapters/README.md).

---

## 8. Como testar a classificação

O sistema é avaliado contra um conjunto de 78 casos escritos à mão, o
`golden_dataset.json`, com a intenção esperada de cada frase.

```bash
docker compose run --rm --no-deps core python evaluate.py
```

Ou, mais curto, `make eval`.

### Como ler a saída

**Bloco 1, acurácia de intenção.** É o número principal.

```
  global: 53/70 = 75.7%   (meta do dataset: 80% · piso deste script: 70%)

  por dificuldade:
    facil    24/30 =  80.0%
    medio    24/32 =  75.0%
    dificil   5/ 8 =  62.5%

  por intenção:
    FATURA              7/10  ███████···
    SUPORTE_TECNICO     4/10  ████······
    COBRANCA_INDEVIDA  10/10  ██████████
```

A leitura importante é a linha por intenção. **`COBRANCA_INDEVIDA` acerta 10 de
10** porque é o caso sensível, protegido por regras determinísticas em vez de
similaridade. **`SUPORTE_TECNICO` acerta 4 de 10** e é o ponto fraco conhecido:
o `flows.json` tem poucos exemplos de treino para essa intenção.

**Bloco 2, acurácia de rejeição.** Mede o que o sistema faz com frases vagas
como "oi" ou "preciso de ajuda". Aparecem dois números, e a explicação está na
própria saída: o dataset assume duas saídas possíveis, classificar ou rejeitar,
e esta arquitetura tem três, porque pode pedir confirmação. **Nenhum dos 8 casos
vagos é roteado com confiança alta**, que é a garantia que importa.

**Bloco 3 e 4, os erros, um a um**, com a frase, o esperado, o obtido e o score.
É aqui que se vê *por que* errou:

```
  «quero contratar mais dados»
     esperado PLANO · obtido COMPRA · score 0.970 (regra) · dificil
     nota do dataset: O verbo contratar puxa para COMPRA, mas o objeto e o
     plano existente. Par de confusao classico.
```

**Bloco 5, desempenho.** Tempo médio de classificação, hoje em **13,5 ms**.

O script sai com código 1 se a acurácia cair abaixo de 70%, então serve como
portão de qualidade e não só como relatório.

### Outros números medidos

| Métrica | Valor | Como reproduzir |
|---|---|---|
| Acurácia de intenção | 75,7% | `make eval` |
| Latência de classificação (mediana) | 14 ms | `scripts/bench_classify.py` |
| Latência de classificação (p95) | 15 ms | `scripts/bench_classify.py` |
| Testes automatizados | 243 passando | `make test` |
| Construção das imagens | 4m21s | `docker compose build` |
| Sistema saudável e atendendo | 17 s | `docker compose up --wait` |

---

## 9. Requisitos atendidos

Cada requisito do Documento de Visão, com o arquivo e a função onde está
implementado.

### Requisitos funcionais

| Nº | Requisito | Onde está | Função |
|---|---|---|---|
| **RF001** | Identificação de intenção em linguagem natural | `core/app/classifier.py` | `classify()` orquestra as três camadas e devolve intenção, confiança e origem |
| **RF002** | Classificação nas categorias do negócio | `core/app/rules.py`<br>`core/app/embeddings.py` | `match_rules()` para palavra-chave (confiança 0,97) e `score()` para similaridade semântica |
| **RF003** | Roteamento inteligente para o canal ou fluxo | `core/app/routing.py` | `resolve()` busca o destino no catálogo do `flows.json` e gera o protocolo |
| **RF004** | Tratamento de ambiguidade com pergunta de confirmação | `core/app/state_machine.py`<br>`core/app/main.py` | `opcoes_de_clarificacao()` monta as alternativas, `resolver_escolha()` interpreta a resposta, `_abrir_clarificacao()` conduz o turno |
| **RF005** | Resposta inicial contextualizada | `core/app/generator.py` | `generate()` reescreve o roteiro no tom da marca; `render_canonical()` é a queda segura quando o Gemini falha |
| **RF006** | Base de fluxos simulados | `core/data/flows.json`<br>`core/app/flows.py` | `init_flows()` carrega e `_validate()` recusa o boot se a base estiver inconsistente |
| **RF007** | Encaminhamento para atendimento humano | `core/app/sensitivity.py`<br>`core/app/routing.py` | `check_sensitive()` escala assunto delicado antes de qualquer IA; `_resolver_destino()` cai em `ATENDIMENTO_HUMANO` quando não há destino mapeado |
| **RF008** | Registro das intenções para análise | `core/app/telemetry.py` | `registrar()` grava cada atendimento em SQLite; `metricas()` alimenta o painel em `/admin` |

### Requisitos não funcionais

| Nº | Requisito | Onde está | Como é cumprido |
|---|---|---|---|
| **RNF001** | Escalabilidade para novas intenções e canais | `core/data/flows.json`<br>`adapters/README.md` | intenção nova é edição de JSON, sem tocar em Python; canal novo é um arquivo em `adapters/` mais uma linha no enum `Channel` de `core/app/contract.py` |
| **RNF002** | Segurança e privacidade | `docker-compose.yml`<br>`web/app/api/chat/route.ts` | o `core` não publica porta e só existe na rede interna; o navegador fala apenas com o BFF; os containers rodam sem privilégio (`guia`, `node`); segredos por variável de ambiente, nunca na imagem |
| **RNF003** | Baixa latência | `core/app/embeddings.py`<br>`core/scripts/bench_classify.py` | `load_model()` embeda os 105 exemplos uma vez no boot numa matriz normalizada, então cada mensagem custa um encode e um produto de matriz. Medido: **13,5 ms** |
| **RNF004** | Usabilidade em linguagem natural | `web/app/components/ChatWidget.tsx` | assistente flutuante em qualquer página, sem menu; o cliente escreve como falaria |
| **RNF005** | Clareza e tom de voz da marca | `core/app/generator.py`<br>`core/data/flows.json` | `_montar_pedido()` entrega ao modelo o roteiro pronto e pede só reescrita de tom; os roteiros vivem no `flows.json` |
| **RNF006** | Confiabilidade, sem resposta inventada | `core/app/generator.py`<br>`core/app/routing.py` | `_ancorado()` rejeita a resposta do modelo se ela contiver URL ou protocolo, porque esses dados nunca entram no pedido; `resolve()` só devolve destino que exista no catálogo fechado |

### As três regras que sustentam tudo

1. **O modelo de linguagem é redator, não decisor.** O destino sai de código
   determinístico. O Gemini recebe o roteiro pronto e só reescreve o tom. A
   prova é o RNF006: endereço e protocolo nem são mostrados a ele.
2. **O catálogo de destinos é fechado.** Intenção sem destino mapeado vira
   atendimento humano. Nunca se infere um endereço.
3. **O sistema roda sem nenhuma chave de API.** É requisito de avaliação, e o
   [item 4](#4-como-rodar) é a demonstração.

---

## 10. Estrutura do projeto

```
claro-guia-inteligente/
├── core/                        o cérebro, em Python
│   ├── app/
│   │   ├── main.py              servidor e orquestração do pipeline
│   │   ├── contract.py          contrato da API em Pydantic, congelado
│   │   ├── config.py            variáveis de ambiente, com padrões
│   │   ├── flows.py             carga e validação do flows.json
│   │   ├── normalize.py         limpeza do texto
│   │   ├── sensitivity.py       etapa 1: assuntos delicados, antes da IA
│   │   ├── rules.py             etapa 2: palavras-chave de alta precisão
│   │   ├── embeddings.py        etapa 3: similaridade semântica
│   │   ├── classifier.py        orquestra as etapas 1 a 3
│   │   ├── state_machine.py     sessão, ambiguidade e clarificação
│   │   ├── routing.py           etapa 4: destino e protocolo
│   │   ├── generator.py         etapa 5: redação ancorada, com degradação
│   │   └── telemetry.py         etapa 6: registro em SQLite
│   ├── data/
│   │   ├── flows.json           BASE DE CONHECIMENTO: intenções, exemplos,
│   │   │                        destinos e roteiros. Nada disso no código
│   │   └── golden_dataset.json  78 casos de avaliação
│   ├── scripts/                 ferramentas de terminal
│   ├── tests/                   243 testes
│   ├── evaluate.py              avaliação do classificador
│   └── Dockerfile               imagem com o modelo embutido no build
├── adapters/                    canais que conversam com o núcleo
│   ├── README.md                o contrato e como escrever um canal novo
│   └── telegram/bot.py          segundo canal, por long polling
├── web/                         interface e BFF, em Next.js
│   ├── app/
│   │   ├── page.tsx             portal com o assistente flutuante
│   │   ├── admin/               painel operacional
│   │   ├── api/chat/            BFF, com regras locais de emergência
│   │   └── components/          assistente, cartões, alternador de tema
│   └── lib/
│       ├── contract.ts          tipos espelhando o Pydantic
│       ├── fallback.ts          classificação local de emergência
│       └── metrics.ts           leitura da telemetria
├── docs/                        diagrama de arquitetura, fonte e saídas
├── docker-compose.yml           orquestração para uso
├── docker-compose.dev.yml       sobreposição com recarga automática
├── Makefile                     atalhos dos comandos do dia a dia
└── .env.example                 todas as variáveis, explicadas
```

**Todo o comportamento do assistente vive no `flows.json`:** as intenções, os
exemplos de treino, as palavras-chave, os destinos e os textos de resposta.
Mudar o que ele faz é editar esse arquivo e reiniciar, sem tocar em Python.

---

## 11. Desenvolvimento

`make` sozinho lista tudo.

| Comando | O que faz |
|---|---|
| `make up` | sobe o sistema |
| `make dev` | sobe com **recarga automática**: editar um arquivo recarrega o processo, sem reconstruir |
| `make telegram` | sobe o sistema mais o canal de Telegram |
| `make down` | desliga, **preservando** a telemetria gravada |
| `make reset` | desliga e **apaga** a telemetria, para começar com o painel zerado |
| `make eval` | avalia o classificador |
| `make test` | roda os 243 testes |
| `make logs` | acompanha os registros de todos os serviços |

A telemetria fica num volume nomeado, fora dos containers. Por isso `make down`
seguido de `make up` não perde o histórico, e é preciso pedir `make reset`
explicitamente para zerar.

Em `make dev` o núcleo também publica a porta 8000, para bater nele com `curl`
sem passar pelo site. Em uso normal essa porta não existe.

Para trabalhar sem Docker, o [`adapters/README.md`](adapters/README.md) e os
comentários no topo de cada módulo explicam as decisões de desenho. O resumo:
`cd core && python -m venv .venv && .venv/bin/pip install -r requirements.txt`,
depois `.venv/bin/uvicorn app.main:app --port 8000`, e `cd web && npm install &&
npm run dev` noutro terminal. Exige Python 3.12 ou mais novo, porque o numpy
fixado no `requirements.txt` não roda em 3.11.

---

## 12. Problemas comuns

### A porta 3000 já está ocupada

```
Error starting userland proxy: listen tcp4 0.0.0.0:3000: bind: address already in use
```

Escolha outra porta no `.env`:

```bash
echo 'WEB_PORT=3001' >> .env
```

E acesse `http://localhost:3001`.

### A construção está demorando muito

É esperado na primeira vez: **4 a 6 minutos**, dos quais a maior parte é baixar
o PyTorch e os 458 MB do modelo de similaridade. As construções seguintes
aproveitam o que já foi baixado e levam segundos.

Se passar muito disso, provavelmente é a rede. Acompanhe o progresso real com:

```bash
docker compose build --progress=plain
```

### O bot do Telegram não responde

Olhe o registro do container:

```bash
docker compose logs telegram
```

| O que aparece | O que significa |
|---|---|
| `TELEGRAM_BOT_TOKEN não definido` | falta o token no `.env`, ou você não subiu com `--profile telegram` |
| `o Telegram recusou o token` | token colado errado, ou com espaço sobrando |
| `chat 123456 fora da allowlist` | o `TELEGRAM_ALLOWED_CHATS` está com o número errado |
| `núcleo não respondeu` | o container do `core` caiu ou ainda está subindo |
| nada, silêncio | é normal: ele fica até 30 segundos parado em cada rodada de espera |

### Não tenho internet na máquina

Depois da primeira construção, **o sistema funciona sem rede nenhuma**. O modelo
de similaridade está dentro da imagem, e a única saída para a internet é a
chamada opcional ao Gemini, que degrada sozinha para os textos do `flows.json`.

Para a **primeira** construção a internet é obrigatória, porque é quando as
dependências e o modelo são baixados. Se precisar levar o projeto para uma
máquina sem rede, construa numa máquina com internet e leve a imagem pronta:

```bash
docker save claro-guia-inteligente-core claro-guia-inteligente-web | gzip > imagens.tar.gz
# na outra máquina:
gunzip -c imagens.tar.gz | docker load
```

### O assistente responde, mas sempre com o mesmo texto

Está funcionando como projetado, sem chave do Gemini. Veja o
[item 5.1](#51-respostas-reescritas-por-ia-generativa) para ligar a reescrita.

### O painel está vazio

Ele mostra o que foi conversado. Converse algumas vezes no assistente e recarregue.

---

## 13. Limitações conhecidas

Documentadas de propósito, não escondidas.

**Todos os dados são fictícios.** Nenhuma integração com sistema real da Claro.
Os links apontam para páginas públicas, os protocolos são gerados por sorteio e
não existem em lugar nenhum. É o que o Documento de Visão define como escopo:
protótipo com dados simulados.

**A sessão vive em memória e expira em 30 minutos.** Reiniciar o núcleo apaga as
conversas em aberto. É escolha, não limitação: banco gerenciado está entre os
anti-objetivos do projeto, e ninguém retoma um menu de três opções vinte minutos
depois.

**Não existe identidade de cliente.** Duas conversas da mesma pessoa em canais
diferentes não são ligadas. Fazer isso exigiria autenticação, que o Documento de
Visão coloca fora desta fase.

**Suporte técnico é o ponto fraco do classificador**, com 4 acertos em 10. A
causa é conhecida: poucos exemplos de treino no `flows.json` para essa intenção.

**A imagem do núcleo tem 2,7 GB.** É o preço de embarcar o PyTorch e o modelo.
Reduzir de verdade exigiria exportar o modelo para ONNX, o que obrigaria a
refazer a calibração dos limiares de confiança.

**O canal de Telegram depende de um processo de pé.** Usa long polling, que
dispensa URL pública mas exige o adaptador rodando. Mensagens enviadas com ele
desligado ficam guardadas no Telegram por cerca de 24 horas e chegam quando ele
voltar.

**O diagrama de arquitetura ainda não mostra o canal de Telegram nem os
containers.** O `docs/arquitetura.json` foi desenhado antes deles existirem.

---

## 14. Time

**Adamanto AI** · FIAP 4SI · Challenge 2026 · Claro

| Integrante | RM |
|---|---|
| Enzo Luciano Duarte | 552486 |
| Ronaldo Kozan Júnior | 98865 |
| Rafael Lima de Oliveira | 88755 |
| Henrique Vieira de Oliveira | 558777 |
