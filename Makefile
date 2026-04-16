.PHONY: up down build restart logs logs-workload logs-mysql \
        trace-query trace-slow trace-slow-10ms trace-stat shell-bcc mysql-cli \
        ps help

COMPOSE := docker compose

## ── Ciclo de vida ─────────────────────────────────────────────────────────────

up: ## Sobe todos os containers em background
	$(COMPOSE) up -d --build
	@echo ""
	@echo "Aguardando MySQL ficar pronto..."
	@$(COMPOSE) exec mysql mysqladmin ping -u root -plabpass --silent --wait=30
	@echo "MySQL pronto. Use 'make trace-query' para iniciar o rastreamento."

down: ## Derruba todos os containers e remove volumes
	$(COMPOSE) down -v

build: ## Reconstrói as imagens sem subir
	$(COMPOSE) build

restart: down up ## Derruba e sobe novamente

## ── Logs ──────────────────────────────────────────────────────────────────────

logs: ## Logs de todos os serviços
	$(COMPOSE) logs -f

logs-workload: ## Logs do gerador de carga
	$(COMPOSE) logs -f workload

logs-mysql: ## Logs do MySQL
	$(COMPOSE) logs -f mysql

ps: ## Status dos containers
	$(COMPOSE) ps

## ── Ferramentas BCC ───────────────────────────────────────────────────────────

trace-query: ## [BCC] mysqld_query — todas as queries em tempo real
	$(COMPOSE) exec bcc bash /scripts/run_mysqld_query.sh

trace-slow: ## [BCC] dbslower — queries > 1ms (padrão)
	$(COMPOSE) exec bcc bash /scripts/run_dbslower.sh

trace-slow-10ms: ## [BCC] dbslower — queries > 10ms
	$(COMPOSE) exec bcc bash /scripts/run_dbslower.sh 10

trace-stat: ## [BCC] dbstat — histograma de latências (intervalo 5s)
	$(COMPOSE) exec bcc bash /scripts/run_dbstat.sh

trace-stat-10s: ## [BCC] dbstat — histograma com intervalo de 10s
	$(COMPOSE) exec bcc bash /scripts/run_dbstat.sh 10

## ── Acesso interativo ─────────────────────────────────────────────────────────

shell-bcc: ## Shell interativo no container BCC
	$(COMPOSE) exec bcc bash

mysql-cli: ## Cliente MySQL interativo
	$(COMPOSE) exec mysql mysql -u labuser -plabpass lab

## ── Ajuda ─────────────────────────────────────────────────────────────────────

help: ## Exibe esta ajuda
	@awk 'BEGIN {FS = ":.*##"; printf "\nUso:\n  make \033[36m<alvo>\033[0m\n\nAlvos disponíveis:\n"} \
	     /^[a-zA-Z_0-9-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } \
	     /^##/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)

.DEFAULT_GOAL := help
