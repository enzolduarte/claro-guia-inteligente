# syntax=docker/dockerfile:1

# Interface e BFF. NENHUM código de aprendizado de máquina entra aqui: este
# container serve HTML e repassa chamadas. Toda a decisão mora no núcleo.

ARG NODE_IMAGE=node:20-alpine

# ---------------------------------------------------------------- 1. dependências
FROM ${NODE_IMAGE} AS dependencias
WORKDIR /app

# Só o manifesto e a trava primeiro: enquanto eles não mudarem, o Docker
# reaproveita esta camada e o `npm ci` não roda de novo.
COPY package.json package-lock.json ./
# `ci` e não `install`: instala exatamente o que está na trava, sem resolver
# versões de novo. É o que faz a imagem ser reproduzível.
RUN npm ci

# A imagem do Node já traz um usuário `node` com id 1000, o mesmo id do usuário
# comum num Linux de mesa. Passar a pasta para ele é o que permite o modo de
# desenvolvimento montar o código sem gerar arquivos com dono root na sua
# máquina, que depois quebram o `npm run build` rodado fora do container.
RUN chown -R node:node /app

# ---------------------------------------------------------------- 2. build
FROM dependencias AS builder
WORKDIR /app

COPY . .

# O endereço do núcleo NÃO entra aqui. Ele é lido em tempo de execução, dentro
# do BFF, que roda no servidor. Se virasse variável de build, ficaria congelado
# na imagem e poderia vazar para o pacote enviado ao navegador.
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ---------------------------------------------------------------- 3. execução
FROM ${NODE_IMAGE} AS runtime
WORKDIR /app

# HOSTNAME=0.0.0.0 não é detalhe: sem ele o servidor do Next escuta só em
# 127.0.0.1, que dentro de um container significa "ninguém de fora alcança". É o
# erro mais comum ao containerizar Next e aparece como conexão recusada na porta
# publicada, com o container parecendo saudável.
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Sem criar usuário: a imagem do Node já traz o `node`, sem privilégio, com id
# 1000. Criar outro à mão exigiria a sintaxe do busybox, que é diferente da do
# Debian usada no Dockerfile do núcleo, e não daria nada em troca.

# O standalone traz o servidor e as dependências que ele usa. Os arquivos
# estáticos e a pasta public ficam de fora e precisam ser copiados à mão.
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
COPY --from=builder --chown=node:node /app/public ./public

USER node

EXPOSE 3000

CMD ["node", "server.js"]
