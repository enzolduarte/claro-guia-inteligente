# Adaptadores de canal

Um adaptador liga um canal de conversa (site, Telegram, o que vier depois) ao
núcleo do Claro Guia Inteligente. Ele faz uma coisa só: **traduzir formato**.

O que chega do canal vira o corpo de um `POST /v1/interpret`. O que o núcleo
devolve vira mensagem no formato daquele canal. Nada além disso.

```
Telegram ──┐
Web ───────┼──→  POST /v1/interpret  ──→  núcleo decide  ──→  resposta única
(novo) ────┘         (o contrato)
```

---

## A regra que não se quebra

**Nenhuma regra de negócio mora em adaptador.**

Classificação, verificação de assunto sensível, escolha de destino, geração de
texto, protocolo: tudo isso é do núcleo. Se você se pegar escrevendo uma lista
de palavras-chave, um `if` sobre a intenção ou uma URL de destino dentro de um
adaptador, parou de escrever um adaptador e começou a escrever um segundo
sistema que vai divergir do primeiro na semana seguinte.

O teste é simples: **a mesma frase, no mesmo momento, tem que produzir o mesmo
destino em qualquer canal.** Isso só se sustenta se a decisão acontecer num
lugar só.

---

## O contrato

Está congelado na seção 3 do [CLAUDE.md](../CLAUDE.md) e espelhado em
`core/app/contract.py` (Pydantic) e `web/lib/contract.ts` (TypeScript).

### O que você envia

```json
{
  "session_id": "telegram:123456",
  "channel": "telegram",
  "text": "minha conta veio mais cara"
}
```

### O que você recebe

```json
{
  "session_id": "telegram:123456",
  "state": "ROTEANDO",
  "intent": "FATURA",
  "confidence": 0.97,
  "confidence_band": "ALTO",
  "confidence_source": "regra",
  "reply": "texto pronto para mostrar ao cliente",
  "reply_source": "generative",
  "options": null,
  "routing": {
    "destination": "FLUXO_FINANCEIRO",
    "label": "Detalhamento de Fatura",
    "url": "https://www.claro.com.br/minha-claro/faturas",
    "protocol": null
  },
  "latency_ms": 812
}
```

Três campos definem o que desenhar na tela:

| Campo | Quando vem preenchido | O que fazer com ele |
|---|---|---|
| `reply` | sempre | mostrar como está, sem reescrever |
| `options` | quando `state` é `CLARIFICANDO` | virar botões, lista numerada, o que o canal permitir |
| `routing` | quando `state` é `ROTEANDO` ou `ESCALANDO` | mostrar destino, link e protocolo |

`options` e `routing` são sempre **presentes** na resposta. Quando não se
aplicam, valem `null`. Nunca são omitidos, então dá para checar direto sem se
preocupar com chave faltando.

### Como a escolha de uma opção volta

Quando o núcleo abre uma clarificação, ele manda as alternativas em `options`,
cada uma com `id` e `label`. O adaptador mostra os `label`; quando o cliente
escolhe, o adaptador manda o **`id`** como `text` do turno seguinte.

Não existe endpoint especial para isso. É uma mensagem normal, e o núcleo
reconhece a escolha de três formas, nesta ordem: o `id` literal, o número da
posição na lista (`"1"`, `"2"`), e por último a semelhança com o que a pessoa
escreveu por conta própria. Mandar o `id` é o caminho mais direto e o único que
não depende de medição de similaridade.

---

## A convenção do `session_id`

```
{canal}:{identificador do canal}
```

Exemplos reais: `web:8f3a1c2e-...` (um UUID em cookie), `telegram:123456789`
(o `chat_id`).

**O núcleo nunca lê essa string.** Para ele é uma chave opaca de dicionário:
ele não separa o canal do id, não interpreta o prefixo, não muda de
comportamento por causa dele. O prefixo existe para nós, humanos, quando
olhamos a telemetria, e para garantir que dois canais não colidam por acaso.

Duas consequências práticas:

- O identificador precisa ser **estável entre mensagens da mesma pessoa**, ou a
  clarificação nunca fecha: o núcleo abre o menu numa sessão e recebe a resposta
  noutra.
- O identificador precisa ser **diferente entre pessoas**. Usar algo como
  `telegram:bot` faria todos os clientes compartilharem a mesma conversa.

A sessão expira sozinha depois de 30 minutos de silêncio e vive em memória. Um
restart do núcleo apaga as conversas em aberto, e isso é intencional: ninguém
retoma um menu de três opções vinte minutos depois.

---

## As duas formas de adaptador

### Forma 1: requisição e resposta

O canal chama você. Você chama o núcleo e devolve na mesma requisição.

É o caso da **web**: o BFF em `web/app/api/chat/route.ts` recebe o `fetch` do
browser, repassa ao núcleo e responde. Serve para qualquer canal que entregue
por webhook.

Vantagens: não tem processo rodando à toa, escala junto com o canal, e o erro
aparece na hora para quem chamou. Exige URL pública alcançável.

### Forma 2: processo que fica escutando

Você chama o canal, em laço, perguntando se chegou algo.

É o caso do **Telegram** em `telegram/bot.py`: `getUpdates` com espera de 30
segundos, controle de `offset` e reconexão com recuo progressivo.

Vantagens: não precisa de URL pública nem de HTTPS válido, funciona atrás de
qualquer NAT. Foi por isso que este projeto escolheu essa forma: numa
apresentação em sala não existe domínio público. O custo é ter um processo a
mais de pé.

### O que as duas precisam ter

- **Tolerar núcleo fora do ar.** Timeout definido e uma resposta digna quando
  ele estoura. A web cai para regras locais de emergência porque sustenta a
  interface principal da demonstração; o Telegram apenas admite que não
  conseguiu, e essa diferença é deliberada: copiar regra para dentro do
  adaptador seria justamente o que a regra de cima proíbe.
- **Não repetir atendimento.** Canais reentregam mensagens quando a confirmação
  se perde. O Telegram deduplica por `update_id`.
- **Escapar o texto.** O `reply` vem do Gemini ou do `flows.json` e vai para um
  canal com marcação própria. Um `<` solto derruba a mensagem inteira.
- **Nunca colocar segredo em log.** No Telegram o token vai dentro da URL, então
  toda mensagem de erro carrega o segredo junto e precisa ser mascarada.

---

## Adaptador de Telegram

### Subir

```bash
pip install -r adapters/telegram/requirements.txt
python adapters/telegram/bot.py
```

O núcleo precisa estar no ar. Sem `TELEGRAM_BOT_TOKEN` o adaptador avisa e
encerra com código 0, sem erro: é o requisito de que o sistema roda sem chave
nenhuma.

### Criar o bot

Fale com o [@BotFather](https://t.me/BotFather) no Telegram, mande `/newbot`,
escolha um nome, e ele devolve o token. Coloque em `core/.env`:

```
TELEGRAM_BOT_TOKEN=123456789:AA...
```

O `core/.env` é onde os segredos deste projeto já moram, e o adaptador lê de lá
para não haver dois arquivos concorrentes. Variável de ambiente de verdade
sempre vence o arquivo.

### Configuração

| Variável | Padrão | Para que serve |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | vazio | Sem ele o adaptador não sobe |
| `TELEGRAM_ALLOWED_CHATS` | vazio | `chat_id` liberados, separados por vírgula. Vazio libera todos |
| `TELEGRAM_POLL_TIMEOUT_S` | `30` | Quanto tempo cada espera segura a conexão |
| `CORE_URL` | `http://localhost:8000` | Onde está o núcleo |
| `CORE_TIMEOUT_MS` | `2500` | Quanto esperar pelo núcleo |

Sobre a allowlist: um bot de Telegram é público por natureza. Quem descobrir o
nome dele consegue mandar mensagem, e cada mensagem custa uma chamada ao núcleo
e possivelmente uma ao Gemini. Com cota gratuita, isso basta para derrubar a
demonstração. Para descobrir o seu `chat_id`, mande uma mensagem ao bot com a
allowlist vazia e leia o número no log.

### Como a resposta é desenhada

- `reply` vai como está, escapado para HTML.
- `options` viram botões inline, um por linha, com o `id` da opção no
  `callback_data`. Se o `id` passar dos 64 bytes que a API permite, entra o
  número da posição, que o núcleo também aceita.
- Ao clicar, o menu antigo é reescrito marcando a escolha e perde os botões.
  Isso resolve duas coisas: clique em botão não vira mensagem visível no
  Telegram, então sem isso a conversa ficaria com o bot falando sozinho; e
  ninguém responde duas vezes a uma pergunta já encerrada.
- `routing` vira um bloco com o destino, o protocolo e a URL escrita por
  extenso. Por extenso, e não escondida atrás de um link, para o cliente
  conferir para onde está sendo mandado. Numa demonstração é também a forma
  mais rápida de flagrar endereço inventado.

---

## Escrever um adaptador novo

1. Descubra qual identificador estável o canal dá por pessoa e monte o
   `session_id` como `{canal}:{esse identificador}`.
2. Acrescente o nome do canal ao enum `Channel` em `core/app/contract.py` e ao
   espelho em `web/lib/contract.ts`. O núcleo valida esse campo e recusa um
   canal desconhecido.
3. Para cada mensagem, chame `POST /v1/interpret` e desenhe os três campos:
   `reply`, `options`, `routing`.
4. Faça a escolha de uma opção voltar como texto do turno seguinte, mandando o
   `id`.
5. Confira o critério de sempre: a mesma frase, no mesmo momento, tem que dar o
   mesmo destino que a web.

---

## Como um adaptador de e-mail se encaixaria

Vale registrar que este exemplo é **ilustração do contrato, não roteiro de
implementação**. A seção 9 do CLAUDE.md lista adaptador de e-mail entre os
anti-objetivos do projeto, e ele segue fora de escopo. O valor de descrevê-lo
aqui é mostrar que o desenho aguenta um canal com natureza bem diferente dos
dois que existem, sem tocar em nada do núcleo.

**Forma:** processo que fica escutando, igual ao Telegram. IMAP no lugar de
`getUpdates`, SMTP no lugar de `sendMessage`.

**O laço:** conectar por IMAP, usar `IDLE` para ser avisado de mensagem nova
(ou pesquisar por não lidas em intervalo fixo, se o servidor não suportar), ler
o corpo, chamar o núcleo, responder por SMTP e marcar como lida.

**`session_id`:** o endereço de quem escreveu, normalizado em minúsculas, por
exemplo `email:maria.jose@exemplo.com`. Estável entre mensagens e único por
pessoa, que é tudo o que a convenção pede. Um refinamento seria amarrar à
thread pelos cabeçalhos `Message-ID` e `In-Reply-To`, para que dois assuntos
diferentes da mesma pessoa não se misturem numa sessão só.

**Os três campos, num canal sem botões:**

- `reply` vira o corpo do e-mail. Sem tradução, é o único caso confortável.
- `options` é o problema de verdade. E-mail não tem botão. As alternativas
  viram uma lista numerada no corpo, com a instrução de responder com o número.
  O núcleo já aceita `"1"`, `"2"` como escolha, então isso funciona sem mudança
  nenhuma no contrato. A resposta chega com todo o histórico citado embaixo, e
  o adaptador precisa cortar isso antes de mandar ao núcleo, ou o texto vira
  uma parede que atrapalha a classificação.
- `routing` vira um bloco no fim do corpo, com o destino, o protocolo e o link.
  Aqui um link clicável de verdade faz mais sentido que no Telegram, já que o
  cliente vai ler no cliente de e-mail dele.

**O que o e-mail exige e os outros dois não:**

- **Assunto e saudação.** Uma resposta de e-mail sem `Subject` e sem
  fechamento parece spam. Isso é apresentação, então mora no adaptador.
- **Latência de outra ordem.** Ninguém espera resposta instantânea de e-mail,
  então o timeout pode ser bem mais generoso que os 2,5 segundos da web.
- **Laço de resposta automática.** Duas caixas com resposta automática se
  respondem para sempre. É obrigatório mandar `Auto-Submitted: auto-replied` e
  ignorar mensagem que já venha com esse cabeçalho ou com `Precedence: bulk`.
- **Anexo e HTML.** Ler só a parte `text/plain`, e quando não houver, converter
  o HTML para texto antes de mandar ao núcleo.

**O que NÃO mudaria:** o contrato, o núcleo, o `flows.json`, o roteamento, a
telemetria. É esse o ponto. Um canal novo é um arquivo novo nesta pasta e uma
linha a mais no enum `Channel`.
