# Claro Guia Inteligente

Assistente de roteamento conversacional para os canais digitais da Claro.
O cliente escreve o que precisa com as próprias palavras e o sistema o encaminha
ao fluxo de atendimento correto.

> Protótipo acadêmico. Challenge 2026 · FIAP 4SI · Time Adamanto AI.
> Dados e valores fictícios, sem vínculo com a Claro S.A.

**Ele roteia, não resolve.** Não emite boleto, não troca plano, não estorna
cobrança. Ele entende o pedido, decide o destino e explica o próximo passo.

![Arquitetura do Claro Guia Inteligente](docs/arquitetura.svg)

O diagrama acima é gerado a partir de uma especificação versionada em
[`docs/arquitetura.json`](docs/arquitetura.json). A versão interativa, com temas,
modo apresentação e quatro recortes guiados, está em
[`docs/arquitetura.html`](docs/arquitetura.html): abra o arquivo no navegador.

---

## Índice

- [O que já funciona](#o-que-já-funciona)
- [Como rodar](#como-rodar)
  - [1. Pré-requisitos](#1-pré-requisitos)
  - [2. Instalação](#2-instalação)
  - [3. Subir o sistema](#3-subir-o-sistema)
  - [4. Conferir se está no ar](#4-conferir-se-está-no-ar)
- [Outras formas de executar](#outras-formas-de-executar)
  - [Conversar pelo terminal](#conversar-pelo-terminal)
  - [Rodar os testes](#rodar-os-testes)
  - [Avaliar o classificador](#avaliar-o-classificador)
  - [Medir a latência](#medir-a-latência)
  - [Popular o painel](#popular-o-painel)
  - [Regerar o diagrama de arquitetura](#regerar-o-diagrama-de-arquitetura)
  - [Diagnosticar o Gemini](#diagnosticar-o-gemini)
- [Como o sistema decide](#como-o-sistema-decide)
- [Arquitetura](#arquitetura)
- [Configuração](#configuração)
- [A API](#a-api)
- [Estrutura de pastas](#estrutura-de-pastas)
- [Resultados medidos](#resultados-medidos)
- [Limites conhecidos](#limites-conhecidos)

---

## O que já funciona

| | Implementado |
|---|---|
| Classificação de mensagem em linguagem natural | sim, 7 intenções |
| Pergunta de confirmação quando há ambiguidade | sim |
| Roteamento com link e número de protocolo | sim |
| Escalação para atendimento humano | sim |
| Resposta reescrita por IA generativa | sim, Gemini (opcional) |
| Funcionamento sem nenhuma chave de API | sim |
| Registro de todas as interações | sim, SQLite |
| Painel operacional com métricas | sim |
| Interface web com assistente flutuante | sim |
| Modo claro e escuro | sim |
| Avaliação com dataset de referência | sim, `evaluate.py` |

Ainda **não** existe: adaptador de Telegram, empacotamento em Docker,
autenticação e identidade de cliente entre canais.

---

## Como rodar

### 1. Pré-requisitos

**Python 3.11 ou mais novo** e **Node 20 ou mais novo**.

Se o `pip` ou o `venv` não estiverem disponíveis na sua máquina, instale o
gerenciador `uv`, que não precisa de permissão de administrador:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Se não tiver Node, instale no seu usuário:

```bash
curl -fsSL https://nodejs.org/dist/v20.18.1/node-v20.18.1-linux-x64.tar.xz | tar -xJ -C ~/.local/node --strip-components=1
```

E deixe o terminal encontrá-lo:

```bash
echo 'export PATH=$HOME/.local/node/bin:$PATH' >> ~/.bashrc && source ~/.bashrc
```

### 2. Instalação

O núcleo, em Python:

```bash
cd core && uv venv .venv && uv pip install -r requirements.txt --python .venv/bin/python
```

A primeira instalação baixa o PyTorch e leva alguns minutos.

A interface, em Node:

```bash
cd web && npm install
```

### 3. Subir o sistema

São dois processos. Abra **dois terminais**.

No primeiro, o núcleo:

```bash
cd core && .venv/bin/uvicorn app.main:app --port 8000
```

Na primeira execução ele baixa o modelo de embeddings, cerca de 460 MB. Depois
disso o boot leva uns 7 segundos.

No segundo, a interface:

```bash
cd web && npm run dev
```

Abra **http://localhost:3000**.

### 4. Conferir se está no ar

```bash
curl -s localhost:8000/health
```

Resposta esperada:

```json
{"status":"ok","version":"0.1.0","flows_version":"1.0.0","intents_loaded":7,"textos_redigidos":"15/15"}
```

O campo `textos_redigidos` mostra o progresso da redação dos textos pelo Gemini,
que roda em segundo plano assim que o servidor sobe. Enquanto não chega em
`15/15`, algumas respostas saem no texto padrão do `flows.json`. Sem chave de
API configurada, esse campo fica em `0/15` e o sistema usa sempre o texto padrão.

**O sistema funciona sem nenhuma chave.** A chave do Gemini é opcional e só
muda a redação das respostas, nunca o roteamento.

---

## Outras formas de executar

### Conversar pelo terminal

Sem abrir o navegador, útil para testar rápido. Precisa do núcleo no ar.

```bash
cd core && .venv/bin/python scripts/chat.py
```

Mostra a resposta e, embaixo, o estado, a intenção, a confiança e a camada que
decidiu. Comandos: `/nova` recomeça a sessão, `/json` mostra a resposta crua,
`/sair` encerra.

### Rodar os testes

```bash
cd core && .venv/bin/python -m pytest tests/ -q
```

São 243 testes. Eles não acessam a internet nem a API do Gemini: as chamadas de
rede são substituídas por dublês, para a suíte ser rápida, estável e não gastar
cota.

### Avaliar o classificador

Mede a qualidade contra o `golden_dataset.json`, um conjunto de 78 frases que
não repete nenhum exemplo de treino.

```bash
cd core && .venv/bin/python evaluate.py
```

Imprime a acurácia global, por intenção e por dificuldade, a matriz de confusão,
a lista dos casos errados e o tempo médio de classificação. Sai com erro se a
acurácia cair abaixo de 70%.

### Medir a latência

```bash
cd core && .venv/bin/python scripts/bench_classify.py
```

Roda 100 classificações e imprime a mediana e o percentil 95.

### Popular o painel

Cria 200 interações fictícias espalhadas por 14 dias, para o painel ter o que
mostrar antes de existir uso real.

```bash
cd core && .venv/bin/python scripts/seed_telemetry.py
```

Toda linha criada assim fica marcada como sintética, e o painel a distingue
visualmente do dado real. Para limpar depois:

```bash
cd core && .venv/bin/python -c "import sqlite3; c=sqlite3.connect('data/telemetria.db'); print('removidas:', c.execute('DELETE FROM interacoes WHERE simulado=1').rowcount); c.commit()"
```

### Regerar o diagrama de arquitetura

O diagrama é produzido pelo [Archify](https://github.com/tt-a1i/archify), uma
skill de agente que compila uma especificação JSON em HTML interativo e valida a
geometria antes de entregar.

```bash
npx skills add tt-a1i/archify -g
```

Depois de editar `docs/arquitetura.json`:

```bash
node ~/.agents/skills/archify/bin/archify.mjs deliver architecture docs/arquitetura.json docs/arquitetura.html --quality showcase
```

A validação recusa a entrega se alguma linha cruzar um componente, se um rótulo
encostar em outro ou se o texto ficar pequeno demais para ler numa tela de
1440px. São nove checagens automáticas de composição.

### Diagnosticar o Gemini

O sistema esconde falhas do LLM de propósito: se a chamada falha, ele responde
com o texto padrão e ninguém percebe. Isso é bom para o cliente e ruim para
depurar. Este script chama a API sem a proteção, então o erro aparece inteiro.

```bash
cd core && .venv/bin/python scripts/testar_gemini.py
```

---

## Como o sistema decide

Cada mensagem passa por uma cascata. A ordem importa e é obrigatória.

```
mensagem do cliente
      │
      ├─ 0. Estava respondendo a uma pergunta?  ──► resolve a escolha ──► roteia
      │
      ├─ 1. Verificador de sensibilidade
      │     palavras de contestação de cobrança ──► escala para humano, fim
      │
      ├─ 2. Regras de alta precisão
      │     palavra-chave literal (confiança 0,97) ──► intenção definida
      │
      ├─ 3. Similaridade semântica
      │     compara o sentido da frase com 105 exemplos
      │     ├─ confiança baixa    ──► pergunta aberta
      │     ├─ sempre_clarificar  ──► oferece opções
      │     └─ confiança média    ──► pede confirmação
      │
      ├─ 4. Motor de roteamento
      │     destino do flows.json; sem destino, vai para atendimento humano
      │
      ├─ 5. Geração ancorada
      │     Gemini reescreve o roteiro pronto; se falhar, usa o texto padrão
      │
      └─ 6. Telemetria
            grava a interação depois de a resposta já ter partido
```

Duas regras que explicam o desenho:

**A sensibilidade roda antes do classificador.** Uma contestação de cobrança
nunca chega a ser interpretada por IA, porque exige análise de conta e
autorização especial.

**O LLM escreve, mas não decide.** O destino sai de código determinístico. O
Gemini recebe o roteiro pronto e só o reescreve no tom da marca. Uma verificação
automática descarta qualquer resposta em que ele tenha inventado endereço ou
número de protocolo.

---

## Arquitetura

Dois processos separados. O diagrama completo está no
[topo deste arquivo](#claro-guia-inteligente); a versão interativa em
[`docs/arquitetura.html`](docs/arquitetura.html) traz quatro recortes guiados:
o caminho de uma mensagem, a cascata de decisão, a degradação e a telemetria.

**Só o `web` expõe porta ao usuário.** O navegador nunca fala com o núcleo:
todas as chamadas passam pelo servidor do Next.js, que conhece o endereço
interno. Verificamos que nem o endereço do núcleo nem a chave do Gemini
aparecem no código enviado ao navegador.

**O núcleo não sabe qual canal está falando com ele.** O identificador de sessão
é uma string opaca no formato `canal:identificador`. Isso é o que permite o
mesmo cérebro atender site, Telegram ou qualquer canal futuro, e é o que faz uma
conversa iniciada no site poder continuar em outro canal.

### Degradação em três níveis

O usuário nunca vê erro.

| Nível | Quando | O que acontece |
|---|---|---|
| 1 | tudo no ar | classificação completa e texto reescrito pelo Gemini |
| 2 | Gemini falha ou demora | texto padrão do `flows.json`; roteamento intacto |
| 3 | núcleo não responde em 2,5s | o `web` classifica por regras locais e responde |

Para ver o nível 3 funcionando: derrube o núcleo com `Ctrl+C` e continue
conversando no site. As respostas seguem chegando, marcadas como `fallback`.

---

## Configuração

Tudo por variável de ambiente, com valor padrão. **Nada é obrigatório.**

| Variável | Padrão | Para que serve |
|---|---|---|
| `CORE_URL` | `http://localhost:8000` | onde o `web` acha o núcleo |
| `CORE_TIMEOUT_MS` | `2500` | espera do `web` pelo núcleo antes do fallback |
| `GEMINI_API_KEY` | vazio | sem ela, o sistema usa os textos padrão |
| `GEMINI_MODEL` | `gemini-flash-lite-latest` | modelo usado na redação |
| `LLM_TIMEOUT_MS` | `8000` | espera pela resposta do Gemini |
| `EMBEDDING_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | modelo de similaridade |
| `DB_PATH` | `./data/telemetria.db` | banco da telemetria |
| `FLOWS_PATH` | `./data/flows.json` | base de conhecimento |

Para usar o Gemini, crie `core/.env`:

```bash
echo 'GEMINI_API_KEY=sua-chave-aqui' > core/.env
```

O arquivo `.env` está no `.gitignore` e não vai para o repositório.

---

## A API

O núcleo publica documentação interativa em **http://localhost:8000/docs**,
gerada a partir do próprio código.

### `POST /v1/interpret`

Interpreta uma mensagem e devolve o encaminhamento.

```bash
curl -s -X POST localhost:8000/v1/interpret \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"web:abc","channel":"web","text":"quero a 2a via da fatura"}'
```

```json
{
  "session_id": "web:abc",
  "state": "ROTEANDO",
  "intent": "SEGUNDA_VIA",
  "confidence": 0.97,
  "confidence_band": "ALTO",
  "confidence_source": "regra",
  "reply": "Você precisa da segunda via da sua fatura...",
  "reply_source": "generative",
  "options": null,
  "routing": {
    "destination": "FLUXO_SEGUNDA_VIA",
    "label": "Portal de Faturas Claro",
    "url": "https://www.claro.com.br/minha-claro/segunda-via",
    "protocol": null
  },
  "latency_ms": 14
}
```

Os campos `options` e `routing` são sempre devolvidos. Ficam `null` quando não
se aplicam, nunca ausentes.

| Campo | Valores | Significado |
|---|---|---|
| `state` | `AGUARDANDO`, `PROCESSANDO`, `CLARIFICANDO`, `RESPONDENDO`, `ROTEANDO`, `ESCALANDO`, `ENCERRADO` | onde a conversa está |
| `confidence_band` | `ALTO`, `MEDIO`, `BAIXO` | faixa de confiança |
| `confidence_source` | `regra`, `embedding`, `nenhuma` | qual camada decidiu |
| `reply_source` | `generative`, `template`, `fallback` | de onde veio o texto |

Quando o estado é `CLARIFICANDO`, o campo `options` traz as alternativas. O
cliente pode responder com o `id` da opção, com o número dela ou escrevendo
livremente.

### `GET /v1/metrics`

Agregados da telemetria: total, taxa de resolução digital, taxa de escalação,
latência média, distribuição por intenção e por canal, série diária, cascata de
decisão e as 20 últimas conversas. Separa dado real de dado sintético.

### `GET /health`

Estado do serviço, versão da base de conhecimento e progresso da redação.

---

## Estrutura de pastas

```
claro-guia-inteligente/
├── core/                      núcleo em Python
│   ├── app/
│   │   ├── main.py            servidor e orquestração do pipeline
│   │   ├── contract.py        contrato da API (Pydantic)
│   │   ├── flows.py           carga e validação do flows.json
│   │   ├── normalize.py       limpeza do texto
│   │   ├── sensitivity.py     etapa 1: assuntos delicados
│   │   ├── rules.py           etapa 2: palavras-chave
│   │   ├── embeddings.py      etapa 3: similaridade semântica
│   │   ├── classifier.py      orquestra as etapas 1 a 3
│   │   ├── state_machine.py   sessão e fluxo de clarificação
│   │   ├── routing.py         etapa 4: destino e protocolo
│   │   ├── generator.py       etapa 5: Gemini com degradação
│   │   └── telemetry.py       etapa 6: registro em SQLite
│   ├── data/
│   │   ├── flows.json         base de conhecimento
│   │   └── golden_dataset.json  conjunto de avaliação
│   ├── scripts/               ferramentas de linha de comando
│   ├── tests/                 243 testes
│   └── evaluate.py            avaliação do classificador
└── web/                       interface em Next.js
    ├── app/
    │   ├── page.tsx           portal com o assistente flutuante
    │   ├── admin/             painel operacional
    │   ├── api/chat/          BFF do chat, com regras de emergência
    │   └── components/        assistente, cartões, alternador de tema
    └── lib/
        ├── contract.ts        tipos espelhando o Pydantic
        ├── fallback.ts        classificação local de emergência
        └── metrics.ts         leitura da telemetria
```

A pasta `data/` guarda a base de conhecimento. **Todas as intenções, exemplos,
destinos e textos de resposta vivem no `flows.json`**, e nada disso está escrito
dentro do código. Mudar o comportamento do assistente é editar esse arquivo e
reiniciar o núcleo.

---

## Resultados medidos

Números obtidos com os scripts deste repositório, não estimativas.

| Métrica | Valor | Como reproduzir |
|---|---|---|
| Acurácia de intenção | 75,7% | `evaluate.py` |
| Latência de classificação (mediana) | 14 ms | `scripts/bench_classify.py` |
| Latência de classificação (p95) | 15 ms | `scripts/bench_classify.py` |
| Latência com reescrita do Gemini | ~1,2 s na primeira vez, depois instantânea | painel |
| Testes automatizados | 243 passando | `pytest tests/ -q` |

A reescrita fica instantânea depois da primeira vez porque o texto depende só da
intenção, não da mensagem. O núcleo redige cada texto uma vez e o guarda.

---

## Limites conhecidos

Documentados de propósito, não escondidos.

**Um canal só.** A arquitetura suporta vários e a continuidade entre eles
funciona, mas apenas o canal web está construído. O adaptador de Telegram não
existe.

**Sem identidade de cliente.** Duas conversas da mesma pessoa em canais
diferentes só são ligadas se compartilharem o identificador de sessão. Ligar
automaticamente exigiria autenticação, que o Documento de Visão coloca fora do
escopo desta fase.

**Suporte técnico é o ponto fraco do classificador**, com 4 acertos em 10 no
conjunto de avaliação. A causa é vocabulário: expressões como "fora do ar" e
"decodificador" não aparecem nos exemplos de treino. A correção é acrescentar
exemplos ao `flows.json`.

**A telemetria guarda a frase do cliente.** Hoje são dados fictícios, mas num
uso real isso exigiria política de retenção e anonimização.

**Sem empacotamento.** Não há Dockerfile nem docker-compose; a execução é
manual, com os dois processos descritos acima.
