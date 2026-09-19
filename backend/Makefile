.PHONY: help test test-cli test-rest test-cache test-workflow test-logging test-statistics test-templates test-concurrent test-local test-cli-tool clean check-env health \
        hydra-up hydra-down hydra-restart hydra-logs hydra-ps hydra-pull hydra-build \
        hydra-dev hydra-dev-down hydra-dev-logs hydra-dev-restart hydra-dev-attach \
        hydra-prod hydra-prod-down hydra-prod-logs \
        hydra-garak-shell hydra-garak-logs hydra-garak-health \
        scan scan-dry scan-validate scan-nexus scan-nexus-dry scan-nexus-validate scan-health

# Default target
.DEFAULT_GOAL := help

# Docker Compose (V2 preferred, fallback to V1)
DOCKER_COMPOSE := $(shell docker compose version > /dev/null 2>&1 && echo "docker compose" || echo "docker-compose")

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)Hydra - Available Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-25s$(NC) %s\n", $$1, $$2}'

test: ## Run all tests inside backend container (requires dev mode: make hydra-dev)
	@echo "$(BLUE)Running backend tests in container...$(NC)"
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml exec backend python -m pytest tests/test_cli_flags.py tests/test_rest_target.py tests/test_report_cache.py tests/test_workflow_analyzer.py tests/test_logging_config.py tests/test_scan_statistics.py tests/test_config_templates.py tests/test_concurrent_scans.py -v
	@echo "$(GREEN)✓ All backend container tests passed$(NC)"

test-cli: ## Run CLI flag tests locally (no container needed)
	@echo "$(BLUE)Running CLI flag tests...$(NC)"
	python3 -m pytest tests/test_cli_flags.py -v
	@echo "$(GREEN)✓ CLI flag tests passed$(NC)"

test-rest: ## Run REST target tests locally (no container needed)
	@echo "$(BLUE)Running REST target tests...$(NC)"
	python3 -m pytest tests/test_rest_target.py -v
	@echo "$(GREEN)✓ REST target tests passed$(NC)"

test-cli-tool: ## Run CLI tool tests inside CLI container (requires dev mode)
	@echo "$(BLUE)Running CLI tool tests in container...$(NC)"
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml run --rm --entrypoint python cli -m pytest tests/ -v
	@echo "$(GREEN)✓ CLI tool tests passed$(NC)"

test-cache: ## Run report cache tests locally (no container needed)
	@echo "$(BLUE)Running report cache tests...$(NC)"
	python3 -m pytest tests/test_report_cache.py -v
	@echo "$(GREEN)✓ Report cache tests passed$(NC)"

test-workflow: ## Run workflow analyzer tests locally (no container needed)
	@echo "$(BLUE)Running workflow analyzer tests...$(NC)"
	python3 -m pytest tests/test_workflow_analyzer.py -v
	@echo "$(GREEN)✓ Workflow analyzer tests passed$(NC)"

test-logging: ## Run logging config tests locally (no container needed)
	@echo "$(BLUE)Running logging config tests...$(NC)"
	python3 -m pytest tests/test_logging_config.py -v
	@echo "$(GREEN)✓ Logging config tests passed$(NC)"

test-statistics: ## Run scan statistics tests locally (no container needed)
	@echo "$(BLUE)Running scan statistics tests...$(NC)"
	python3 -m pytest tests/test_scan_statistics.py -v
	@echo "$(GREEN)✓ Scan statistics tests passed$(NC)"

test-templates: ## Run config template tests locally (no container needed)
	@echo "$(BLUE)Running config template tests...$(NC)"
	python3 -m pytest tests/test_config_templates.py -v
	@echo "$(GREEN)✓ Config template tests passed$(NC)"

test-concurrent: ## Run concurrent scan tests locally (no container needed)
	@echo "$(BLUE)Running concurrent scan tests...$(NC)"
	python3 -m pytest tests/test_concurrent_scans.py -v
	@echo "$(GREEN)✓ Concurrent scan tests passed$(NC)"

test-local: ## Run all local tests (no container needed)
	@echo "$(BLUE)Running all local tests...$(NC)"
	python3 -m pytest tests/test_cli_flags.py tests/test_rest_target.py tests/test_report_cache.py tests/test_workflow_analyzer.py tests/test_logging_config.py tests/test_scan_statistics.py tests/test_config_templates.py tests/test_concurrent_scans.py -v
	@echo "$(GREEN)✓ All local tests passed$(NC)"

test-all: ## Run all tests (backend + CLI) in containers
	@echo "$(BLUE)Running all backend tests...$(NC)"
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml exec backend python -m pytest tests/test_cli_flags.py tests/test_rest_target.py tests/test_report_cache.py tests/test_workflow_analyzer.py tests/test_logging_config.py tests/test_scan_statistics.py tests/test_config_templates.py tests/test_concurrent_scans.py -v
	@echo "$(GREEN)✓ Backend tests passed$(NC)"
	@echo "$(BLUE)Running CLI tool tests...$(NC)"
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml run --rm --entrypoint python cli -m pytest tests/ -v
	@echo "$(GREEN)✓ CLI tests passed$(NC)"
	@echo "$(GREEN)✓ All tests passed$(NC)"

clean: ## Clean up Python cache files
	@echo "$(BLUE)Cleaning up...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

check-env: ## Check if .env file exists
	@if [ ! -f .env ]; then \
		echo "$(YELLOW)Warning: .env file not found. Creating from .env.example...$(NC)"; \
		if [ -f .env.example ]; then \
			cp .env.example .env; \
			echo "$(GREEN)✓ .env file created. Please review and update as needed.$(NC)"; \
		else \
			echo "$(RED)Error: .env.example not found$(NC)"; \
		fi \
	fi

health: ## Check backend health
	@echo "$(BLUE)Checking backend health...$(NC)"
	@curl -s http://localhost:8888/health | python -m json.tool || echo "$(RED)Backend is not running$(NC)"

# =============================================================================
# Docker Compose Commands
# =============================================================================

hydra-build: check-env ## Build images with docker compose
	@echo "$(BLUE)Building with docker compose...$(NC)"
	@mkdir -p garak_reports
	$(DOCKER_COMPOSE) build --no-cache
	@echo "$(GREEN)✓ Build complete$(NC)"

hydra-up: check-env ## Start services (detached)
	@echo "$(BLUE)Starting services...$(NC)"
	@mkdir -p garak_reports
	$(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo "$(YELLOW)  API: http://localhost:8888$(NC)"

hydra-up-build: check-env ## Build and start services
	@echo "$(BLUE)Building and starting services...$(NC)"
	@mkdir -p garak_reports
	$(DOCKER_COMPOSE) up -d --build
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo "$(YELLOW)  API: http://localhost:8888$(NC)"

hydra-up-attach: check-env ## Start services (attached, see logs)
	@echo "$(BLUE)Starting services (attached)...$(NC)"
	@mkdir -p garak_reports
	$(DOCKER_COMPOSE) up --build

hydra-down: ## Stop and remove services
	@echo "$(BLUE)Stopping services...$(NC)"
	$(DOCKER_COMPOSE) down
	@echo "$(GREEN)✓ Services stopped$(NC)"

hydra-down-v: ## Stop services and remove volumes
	@echo "$(BLUE)Stopping services and removing volumes...$(NC)"
	$(DOCKER_COMPOSE) down -v
	@echo "$(GREEN)✓ Services and volumes removed$(NC)"

hydra-restart: ## Restart services
	@echo "$(BLUE)Restarting services...$(NC)"
	$(DOCKER_COMPOSE) restart
	@echo "$(GREEN)✓ Services restarted$(NC)"

hydra-logs: ## Show service logs (follow)
	$(DOCKER_COMPOSE) logs -f

hydra-logs-tail: ## Show last 100 lines of logs
	$(DOCKER_COMPOSE) logs --tail=100

hydra-ps: ## List running services
	@echo "$(BLUE)Running services:$(NC)"
	$(DOCKER_COMPOSE) ps

hydra-exec: ## Open shell in backend container
	$(DOCKER_COMPOSE) exec backend /bin/bash

hydra-pull: ## Pull latest images
	@echo "$(BLUE)Pulling images...$(NC)"
	$(DOCKER_COMPOSE) pull
	@echo "$(GREEN)✓ Images pulled$(NC)"

hydra-config: ## Validate and view compose config
	@echo "$(BLUE)Docker Compose Configuration:$(NC)"
	$(DOCKER_COMPOSE) config

# =============================================================================
# Docker Compose Development Mode (with hot reload)
# =============================================================================

hydra-dev: check-env ## Start in dev mode (mounts local code, hot reload)
	@echo "$(BLUE)Starting in development mode with hot reload...$(NC)"
	@mkdir -p garak_reports
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml up -d --build
	@echo "$(GREEN)✓ Development server started$(NC)"
	@echo "$(YELLOW)  API: http://localhost:8888$(NC)"
	@echo "$(YELLOW)  Local code is mounted - changes apply automatically$(NC)"
	@echo "$(YELLOW)  Logs: make hydra-dev-logs$(NC)"

hydra-dev-attach: check-env ## Start in dev mode (attached, see logs)
	@echo "$(BLUE)Starting in development mode (attached)...$(NC)"
	@mkdir -p garak_reports
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml up --build

hydra-dev-down: ## Stop dev mode services
	@echo "$(BLUE)Stopping development services...$(NC)"
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml down
	@echo "$(GREEN)✓ Development services stopped$(NC)"

hydra-dev-logs: ## Show dev mode logs
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml logs -f

hydra-dev-restart: ## Restart dev mode services
	@echo "$(BLUE)Restarting development services...$(NC)"
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml restart
	@echo "$(GREEN)✓ Development services restarted$(NC)"

# =============================================================================
# Docker Compose Production Mode (with Ollama container)
# =============================================================================

hydra-prod: check-env ## Start in prod mode (backend + garak + ollama)
	@echo "$(BLUE)Starting production stack (backend + garak + ollama)...$(NC)"
	@mkdir -p garak_reports
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml up -d --build
	@echo "$(GREEN)✓ Production stack started$(NC)"
	@echo "$(YELLOW)  API: http://localhost:8888$(NC)"
	@echo "$(YELLOW)  Ollama: http://localhost:11434$(NC)"

hydra-prod-down: ## Stop production stack
	@echo "$(BLUE)Stopping production stack...$(NC)"
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml down
	@echo "$(GREEN)✓ Production stack stopped$(NC)"

hydra-prod-logs: ## Show production stack logs
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml logs -f

# =============================================================================
# Garak Service Commands
# =============================================================================

hydra-garak-shell: ## Open shell in garak service container
	$(DOCKER_COMPOSE) exec garak /bin/bash

hydra-garak-logs: ## Show garak service logs
	$(DOCKER_COMPOSE) logs -f garak

hydra-garak-health: ## Check garak service health
	@echo "$(BLUE)Checking garak service health...$(NC)"
	@$(DOCKER_COMPOSE) exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://garak:9090/health').read().decode())" 2>/dev/null \
		&& echo "$(GREEN)✓ Garak service is healthy$(NC)" \
		|| echo "$(RED)✗ Garak service is not responding$(NC)"

# =============================================================================
# CLI Scanning Commands
# =============================================================================
# Usage:
#   make scan PLAN=scan_plans/nexus-test.yaml          Run a scan plan
#   make scan-dry PLAN=scan_plans/nexus-test.yaml      Dry run (preview)
#   make scan-validate PLAN=scan_plans/nexus-test.yaml Validate only
#   make scan-nexus                                     Run Nexus scan (shortcut)
#   make scan-nexus-dry                                 Dry run Nexus scan
#
# For Okta-protected targets, set the token first:
#   export OKTA_TOKEN="eyJ..."
#   make scan-nexus

# Default plan file (override with: make scan PLAN=path/to/plan.yaml)
PLAN ?= scan_plans/nexus-test.yaml

# CLI runner (passes env vars into the container)
CLI_RUN = $(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml run --rm \
	-e OKTA_TOKEN \
	-e NEXUS_COOKIE \
	--entrypoint python cli hydra_scan.py

scan: ## Run a scan plan (PLAN=path/to/plan.yaml)
	@if [ -z "$(PLAN)" ]; then echo "$(RED)Error: PLAN is required. Usage: make scan PLAN=scan_plans/my-plan.yaml$(NC)"; exit 1; fi
	@echo "$(BLUE)Running scan plan: $(PLAN)$(NC)"
	$(CLI_RUN) run --plan $(PLAN)
	@echo "$(GREEN)✓ Scan complete$(NC)"

scan-bg: ## Run a scan plan in background (PLAN=path/to/plan.yaml) — survives terminal disconnect
	@if [ -z "$(PLAN)" ]; then echo "$(RED)Error: PLAN is required. Usage: make scan-bg PLAN=scan_plans/my-plan.yaml$(NC)"; exit 1; fi
	@echo "$(BLUE)Starting scan in background: $(PLAN)$(NC)"
	@nohup $(CLI_RUN) run --plan $(PLAN) \
		> scan-bg-$(shell date +%Y%m%d-%H%M%S).log 2>&1 &
	@echo "$(GREEN)✓ Scan running in background (PID $$!)$(NC)"
	@echo "$(YELLOW)  Log: tail -f $$(ls -t scan-bg-*.log | head -1)$(NC)"

scan-dry: ## Dry run a scan plan — preview without scanning (PLAN=path/to/plan.yaml)
	@if [ -z "$(PLAN)" ]; then echo "$(RED)Error: PLAN is required.$(NC)"; exit 1; fi
	@echo "$(BLUE)Dry run: $(PLAN)$(NC)"
	$(CLI_RUN) run --plan $(PLAN) --dry-run

scan-validate: ## Validate a scan plan (PLAN=path/to/plan.yaml)
	@if [ -z "$(PLAN)" ]; then echo "$(RED)Error: PLAN is required.$(NC)"; exit 1; fi
	@echo "$(BLUE)Validating: $(PLAN)$(NC)"
	$(CLI_RUN) validate --plan $(PLAN)

NEXUS_LOG = nexus-scan-$(shell date +%Y%m%d-%H%M%S).log

scan-nexus-quick: ## Quick Nexus smoke test (~5 min, 3 probes) — verify pipeline works
	@if [ -z "$$OKTA_TOKEN" ]; then \
		echo "$(RED)Error: OKTA_TOKEN is not set.$(NC)"; \
		echo "$(YELLOW)  1. Log in to Nexus via Okta in your browser$(NC)"; \
		echo "$(YELLOW)  2. Open DevTools > Network > copy Authorization token$(NC)"; \
		echo "$(YELLOW)  3. Copy ARRAffinity cookie from response headers$(NC)"; \
		echo "$(YELLOW)  4. export OKTA_TOKEN=\"eyJ...\"$(NC)"; \
		echo "$(YELLOW)  5. export NEXUS_COOKIE=\"ARRAffinity=...\"$(NC)"; \
		echo "$(YELLOW)  6. make scan-nexus-quick$(NC)"; \
		exit 1; \
	fi
	@echo "$(BLUE)Running Nexus quick smoke test (3 probes, ~5 min)...$(NC)"
	$(CLI_RUN) run --plan scan_plans/nexus-quick.yaml
	@echo "$(GREEN)✓ Quick scan complete. Reports in hydra_reports/nexus/$(NC)"

scan-nexus: ## Run Nexus full scan (~30-60 min, requires OKTA_TOKEN + NEXUS_COOKIE)
	@if [ -z "$$OKTA_TOKEN" ]; then \
		echo "$(RED)Error: OKTA_TOKEN is not set.$(NC)"; \
		echo "$(YELLOW)  1. Log in to Nexus via Okta in your browser$(NC)"; \
		echo "$(YELLOW)  2. Open DevTools > Network > copy Authorization token$(NC)"; \
		echo "$(YELLOW)  3. Copy ARRAffinity cookie from response headers$(NC)"; \
		echo "$(YELLOW)  4. export OKTA_TOKEN=\"eyJ...\"$(NC)"; \
		echo "$(YELLOW)  5. export NEXUS_COOKIE=\"ARRAffinity=...\"$(NC)"; \
		echo "$(YELLOW)  6. make scan-nexus$(NC)"; \
		exit 1; \
	fi
	@echo "$(BLUE)Running Nexus scan (Okta auth)...$(NC)"
	$(CLI_RUN) run --plan scan_plans/nexus-test.yaml
	@echo "$(GREEN)✓ Nexus scan complete. Reports in cli_reports/nexus/$(NC)"

scan-nexus-bg: ## Run Nexus scan in background (survives terminal disconnect)
	@if [ -z "$$OKTA_TOKEN" ]; then \
		echo "$(RED)Error: OKTA_TOKEN is not set.$(NC)"; \
		echo "$(YELLOW)  1. Log in to Nexus via Okta in your browser$(NC)"; \
		echo "$(YELLOW)  2. Open DevTools > Network > copy Authorization token$(NC)"; \
		echo "$(YELLOW)  3. Copy ARRAffinity cookie from response headers$(NC)"; \
		echo "$(YELLOW)  4. export OKTA_TOKEN=\"eyJ...\"$(NC)"; \
		echo "$(YELLOW)  5. export NEXUS_COOKIE=\"ARRAffinity=...\"$(NC)"; \
		echo "$(YELLOW)  6. make scan-nexus-bg$(NC)"; \
		exit 1; \
	fi
	@echo "$(BLUE)Starting Nexus scan in background...$(NC)"
	@nohup $(CLI_RUN) run --plan scan_plans/nexus-test.yaml \
		> $(NEXUS_LOG) 2>&1 &
	@echo "$(GREEN)✓ Scan running in background (PID $$!)$(NC)"
	@echo "$(YELLOW)  Log:    tail -f $(NEXUS_LOG)$(NC)"
	@echo "$(YELLOW)  Status: make scan-nexus-status$(NC)"
	@echo "$(YELLOW)  Stop:   make scan-nexus-stop$(NC)"

scan-nexus-status: ## Check if a background Nexus scan is still running
	@if pgrep -f "hydra_scan.py run --plan scan_plans/nexus-test" > /dev/null 2>&1; then \
		echo "$(GREEN)Nexus scan is running (PID $$(pgrep -f 'hydra_scan.py run --plan scan_plans/nexus-test'))$(NC)"; \
		echo "$(YELLOW)  Latest log lines:$(NC)"; \
		tail -5 $$(ls -t nexus-scan-*.log 2>/dev/null | head -1) 2>/dev/null || echo "  (no log file found)"; \
	else \
		echo "$(YELLOW)No Nexus scan running.$(NC)"; \
		LATEST=$$(ls -t nexus-scan-*.log 2>/dev/null | head -1); \
		if [ -n "$$LATEST" ]; then \
			echo "$(BLUE)Last log: $$LATEST$(NC)"; \
			echo "$(YELLOW)  Last lines:$(NC)"; \
			tail -10 "$$LATEST"; \
		fi; \
	fi

scan-nexus-stop: ## Stop a running background Nexus scan
	@if pgrep -f "hydra_scan.py run --plan scan_plans/nexus-test" > /dev/null 2>&1; then \
		pkill -f "hydra_scan.py run --plan scan_plans/nexus-test"; \
		echo "$(YELLOW)Nexus scan stopped.$(NC)"; \
	else \
		echo "$(YELLOW)No Nexus scan running.$(NC)"; \
	fi

scan-nexus-dry: ## Dry run Nexus scan — preview targets and auth status
	@echo "$(BLUE)Dry run: Nexus scan$(NC)"
	$(CLI_RUN) run --plan scan_plans/nexus-test.yaml --dry-run

scan-nexus-validate: ## Validate Nexus scan plan
	@echo "$(BLUE)Validating Nexus scan plan...$(NC)"
	$(CLI_RUN) validate --plan scan_plans/nexus-test.yaml

scan-health: ## Check backend health before scanning
	@echo "$(BLUE)Checking scan prerequisites...$(NC)"
	@$(CLI_RUN) health
	@echo ""
	@if [ -n "$$OKTA_TOKEN" ]; then \
		echo "$(GREEN)  OKTA_TOKEN: set$(NC)"; \
	else \
		echo "$(YELLOW)  OKTA_TOKEN: not set (needed for Okta-protected targets)$(NC)"; \
	fi
