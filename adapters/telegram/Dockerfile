# syntax=docker/dockerfile:1

# Adaptador de Telegram. Não importa nada de core/, então não herda torch nem
# sentence-transformers: a imagem inteira é Python + httpx. É a prova prática de
# que adaptador é fino, como manda a seção 2 do CLAUDE.md.

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

RUN useradd --system --create-home --uid 10002 guia
COPY --chown=guia:guia bot.py .
USER guia

# Sem porta exposta: o adaptador só faz conexões de saída. Ele pergunta ao
# Telegram se chegou mensagem, em vez de esperar o Telegram bater na porta.
CMD ["python", "bot.py"]
