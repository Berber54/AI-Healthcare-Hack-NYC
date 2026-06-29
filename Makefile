SHELL := /bin/bash
PYTHON := python3
BACKEND := backend
PORT := 8888
TEST_USER := 00000000-0000-0000-0000-000000000001

.DEFAULT_GOAL := help

# ─── Help ──────────────────────────────────────────────────────────────────────
.PHONY: help
help:
	@echo ""
	@echo "  DailyOps AI"
	@echo ""
	@echo "  make setup      First-time setup: install deps, run migrations, seed DB"
	@echo "  make run        Start the backend server on port $(PORT)"
	@echo "  make test       Run the full test suite"
	@echo "  make trigger    Fire a test planning run (server must be running)"
	@echo "  make logs       Tail the server log"
	@echo "  make clean      Remove __pycache__ and .pyc files"
	@echo ""

# ─── Setup ─────────────────────────────────────────────────────────────────────
.PHONY: setup
setup: check-env install-deps run-migrations
	@echo ""
	@echo "✅  Setup complete. Start the server with: make run"
	@echo ""

.PHONY: check-env
check-env:
	@if [ ! -f $(BACKEND)/.env ]; then \
		echo ""; \
		echo "❌  $(BACKEND)/.env not found."; \
		echo "   Copy the template and fill in your keys:"; \
		echo "   cp .env.template $(BACKEND)/.env"; \
		echo ""; \
		exit 1; \
	fi
	@bash scripts/check_env.sh

.PHONY: install-deps
install-deps:
	@echo "▶  Installing Python dependencies …"
	@cd $(BACKEND) && $(PYTHON) -m pip install -r requirements.txt -q
	@echo "✓  Dependencies installed"

.PHONY: run-migrations
run-migrations:
	@echo "▶  Running database migrations …"
	@$(PYTHON) scripts/setup_db.py

# ─── Run ───────────────────────────────────────────────────────────────────────
.PHONY: run
run:
	@echo "▶  Starting backend on http://localhost:$(PORT) …"
	@cd $(BACKEND) && $(PYTHON) -m uvicorn app.main:app --port $(PORT) --reload

# ─── Test ──────────────────────────────────────────────────────────────────────
.PHONY: test
test:
	@echo "▶  Running test suite …"
	@cd $(BACKEND) && $(PYTHON) -m pytest app/tests/ -q --tb=short

# ─── Trigger ───────────────────────────────────────────────────────────────────
.PHONY: trigger
trigger:
	@echo "▶  Triggering test planning run …"
	@curl -s -X POST "http://localhost:$(PORT)/api/test-run?user_id=$(TEST_USER)" \
		| $(PYTHON) -m json.tool

# ─── Logs ──────────────────────────────────────────────────────────────────────
.PHONY: logs
logs:
	@tail -f /tmp/voiceai_server.log

# ─── Clean ─────────────────────────────────────────────────────────────────────
.PHONY: clean
clean:
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	@find . -name "*.pyc" -delete 2>/dev/null; true
	@echo "✓  Cleaned"
