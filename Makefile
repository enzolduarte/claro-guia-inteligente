# Atalhos do dia a dia. Cada alvo é uma linha de docker compose que ninguém
# precisa decorar.
#
#   make up       sobe o sistema (site em http://localhost:3000)
#   make dev      sobe com recarga automática ao salvar arquivo
#   make down     desliga, preservando a telemetria
#   make reset    desliga e APAGA a telemetria
#   make eval     roda a avaliação do classificador
#
# `make` sem argumento mostra esta lista.

COMPOSE     := docker compose
COMPOSE_DEV := $(COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml

.DEFAULT_GOAL := help
.PHONY: help up dev down reset logs eval test telegram build

help:
	@echo ""
	@echo "  make up        sobe o sistema em http://localhost:3000"
	@echo "  make dev       sobe em modo desenvolvimento, com recarga automatica"
	@echo "  make telegram  sobe o sistema mais o canal de Telegram"
	@echo "  make down      desliga tudo, preservando a telemetria"
	@echo "  make reset     desliga e apaga a telemetria gravada"
	@echo "  make logs      acompanha os registros de todos os servicos"
	@echo "  make eval      avalia o classificador contra o golden dataset"
	@echo "  make test      roda a suite de testes do nucleo"
	@echo "  make build     reconstroi as imagens sem subir nada"
	@echo ""

up:
	$(COMPOSE) up --build

dev:
	$(COMPOSE_DEV) up --build

telegram:
	$(COMPOSE) --profile telegram up --build

build:
	$(COMPOSE) --profile telegram build

down:
	$(COMPOSE) --profile telegram down

# `-v` remove o volume nomeado junto. A telemetria some, e o proximo `make up`
# comeca com o painel zerado. E a diferenca inteira entre este alvo e o `down`.
reset:
	$(COMPOSE) --profile telegram down -v

logs:
	$(COMPOSE) logs -f

# `run --rm` cria um container descartavel a partir da imagem do nucleo.
# `--no-deps` evita subir o site so para rodar um script de terminal.
eval:
	$(COMPOSE) run --rm --no-deps core python evaluate.py

# Os testes NAO vao para a imagem (estao no .dockerignore), entao eles rodam
# montados de fora, contra as dependencias que a imagem ja tem instaladas.
test:
	$(COMPOSE) run --rm --no-deps \
		-v $(CURDIR)/core/tests:/app/tests \
		core python -m pytest tests/ -q
