# syntax=docker/dockerfile:1

# Núcleo do Claro Guia Inteligente.
#
# Três estágios, e o do meio é o que importa: o modelo de embeddings (cerca de
# 470 MB) é BAIXADO NO BUILD e vira camada da imagem. Se ele fosse buscado no
# primeiro atendimento, o container subiria "saudável" e travaria por minutos na
# primeira mensagem, ou falharia de vez numa máquina sem internet. Requisito de
# latência da seção 8 do CLAUDE.md: o modelo carrega uma vez, no boot, do disco.

# 3.13, e não 3.11: o requirements.txt fixa numpy 2.5.2, que exige Python 3.12
# ou mais novo. Numa base 3.11 o pip nem chega a instalar. É também a versão em
# que os 243 testes rodam, então a imagem executa o mesmo interpretador que foi
# testado, não um parecido.
ARG PYTHON_IMAGE=python:3.13-slim

# ---------------------------------------------------------------- 1. dependências
FROM ${PYTHON_IMAGE} AS dependencias

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Ambiente virtual em caminho próprio para o estágio final copiar um diretório
# só, sem arrastar o pip e o cache de build junto.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
# O requirements.txt já aponta o índice de CPU do PyTorch na primeira linha. O
# wheel padrão traz CUDA e passa de 2 GB sem nenhum uso aqui.
RUN pip install -r requirements.txt

# O PyTorch instalado ocupa 722 MB, e 145 MB deles não têm uso aqui:
#   torch/test     83 MB   binários de teste do próprio projeto torch
#   torch/include  62 MB   cabeçalhos C++, para compilar extensões
#
# `torch/bin` (50 MB) FICA. Foi tentado remover e o build quebrou: o import do
# torch procura o `torch_shm_manager` dentro dessa pasta e levanta exceção se
# não achar. É por isso que a poda é seguida de uma verificação de verdade nos
# dois estágios seguintes, em vez de confiar em "isso parece descartável".
RUN set -eux; \
    SP="$(python -c 'import site; print(site.getsitepackages()[0])')"; \
    du -sh "$SP/torch"; \
    rm -rf "$SP/torch/test" "$SP/torch/include"; \
    du -sh "$SP/torch"

# ---------------------------------------------------------------- 2. modelo
FROM dependencias AS modelo

# Mesmo valor do default em app/config.py. Trocar o modelo é trocar aqui e lá.
ARG EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
ENV HF_HOME=/opt/modelos

RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('${EMBEDDING_MODEL}')"

# Prova, ainda no build, de que a imagem carrega o modelo SEM rede. Se o cache
# tiver ficado no lugar errado, o build quebra aqui, e não num atendimento.
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1
# Não basta carregar: um encode de verdade exercita o caminho completo do
# PyTorch, que é justamente o que foi podado no estágio anterior.
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
m = SentenceTransformer('${EMBEDDING_MODEL}'); \
v = m.encode(['minha conta veio mais cara'], normalize_embeddings=True); \
print('modelo carregado e usado offline, vetor', v.shape, 'norma %.3f' % float((v[0]**2).sum()**0.5))"

# ---------------------------------------------------------------- 3. execução
FROM ${PYTHON_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    HF_HOME=/opt/modelos \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    DB_PATH=/data/telemetria.db

COPY --from=dependencias /opt/venv /opt/venv
COPY --from=modelo /opt/modelos /opt/modelos

# Sem privilégio: um processo que interpreta texto de estranho não tem motivo
# para rodar como root dentro do container.
RUN useradd --system --create-home --uid 10001 guia \
 && mkdir -p /data \
 && chown guia:guia /data

WORKDIR /app
COPY --chown=guia:guia app/ ./app/
COPY --chown=guia:guia data/ ./data/
COPY --chown=guia:guia evaluate.py ./
COPY --chown=guia:guia scripts/ ./scripts/

USER guia

# Ensaio do boot, dentro do build. Roda o MESMO caminho do lifespan da
# aplicação: valida o flows.json, carrega o modelo e pré-computa a matriz do
# catálogo. Se a poda do estágio 1 tivesse quebrado alguma coisa, ou se o
# flows.json estivesse inválido, o build para aqui em vez de gerar uma imagem
# que só falha quando alguém abrir o site.
RUN python -c "\
from app.flows import init_flows; \
from app.embeddings import load_model; \
init_flows(); load_model(); \
print('boot ensaiado: flows validado e catalogo de embeddings pronto')"

# Sem `VOLUME ["/data"]` de propósito: essa instrução faz um `docker run` avulso
# criar volume anônimo a cada execução, que ninguém encontra depois. Quem define
# a persistência é o compose, com um volume nomeado.

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
