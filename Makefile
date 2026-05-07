# Numbers Protocol Reference Agents — Makefile
# ------------------------------------------------
# Targets for local dev, Docker deployment, and VPS deployment.

VENV     := venv
PYTHON   := $(VENV)/bin/python
PIP      := $(VENV)/bin/pip
COMPOSE  := docker compose

.PHONY: help setup install test lint run-all docker-build docker-up docker-down \
        docker-logs status deploy-vps

help:
	@echo ""
	@echo "Numbers Protocol Reference Agents"
	@echo ""
	@echo "  make setup          Create .env from .env.example"
	@echo "  make install        Create venv and install dependencies"
	@echo "  make test           Smoke-test all agents (dry-run, no registration)"
	@echo "  make lint           Run ruff linter"
	@echo ""
	@echo "  make run-all        Run all 7 agents in background (local)"
	@echo "  make status         Show agent status via monitor.py"
	@echo ""
	@echo "  make docker-build   Build the Docker image"
	@echo "  make docker-up      Start all agents via docker-compose"
	@echo "  make docker-down    Stop all agents"
	@echo "  make docker-logs    Tail logs from all agents"
	@echo ""
	@echo "  make deploy-vps     Deploy to VPS via systemd (run on VPS)"
	@echo ""

setup:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example — edit it and set CAPTURE_TOKEN"; \
	else \
		echo ".env already exists"; \
	fi

install: setup
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "Install complete. Activate with: source $(VENV)/bin/activate"

test: install
	@echo "--- Smoke testing all agents (import + env check, no SDK calls) ---"
	@$(PYTHON) -c "import common; print('  common.py    OK')"
	@$(PYTHON) -c "import provart; print('  provart.py   OK')"
	@$(PYTHON) -c "import newsprove; print('  newsprove.py OK')"
	@$(PYTHON) -c "import agentlog; print('  agentlog.py  OK')"
	@$(PYTHON) -c "import dataprove; print('  dataprove.py OK')"
	@$(PYTHON) -c "import socialprove; print('  socialprove.py OK')"
	@$(PYTHON) -c "import researchprove; print('  researchprove.py OK')"
	@$(PYTHON) -c "import codeprove; print('  codeprove.py OK')"
	@echo "--- All imports OK ---"

lint: install
	$(PIP) install --quiet ruff
	$(VENV)/bin/ruff check *.py

run-all: install
	@mkdir -p state logs
	@echo "Starting all 7 agents in background..."
	@nohup $(PYTHON) -u provart.py      >> logs/provart.log      2>&1 & echo $$! > state/provart.pid
	@nohup $(PYTHON) -u newsprove.py    >> logs/newsprove.log    2>&1 & echo $$! > state/newsprove.pid
	@nohup $(PYTHON) -u agentlog.py     >> logs/agentlog.log     2>&1 & echo $$! > state/agentlog.pid
	@nohup $(PYTHON) -u dataprove.py    >> logs/dataprove.log    2>&1 & echo $$! > state/dataprove.pid
	@nohup $(PYTHON) -u socialprove.py  >> logs/socialprove.log  2>&1 & echo $$! > state/socialprove.pid
	@nohup $(PYTHON) -u researchprove.py >> logs/researchprove.log 2>&1 & echo $$! > state/researchprove.pid
	@nohup $(PYTHON) -u codeprove.py    >> logs/codeprove.log    2>&1 & echo $$! > state/codeprove.pid
	@echo "All agents started. PIDs stored in state/*.pid"
	@echo "Tail logs with: tail -f logs/*.log"
	@sleep 3 && $(PYTHON) monitor.py

stop-all:
	@echo "Stopping all agents..."
	@for f in state/*.pid; do \
		[ -f "$$f" ] || continue; \
		pid=$$(cat $$f); \
		kill $$pid 2>/dev/null && echo "  killed PID $$pid ($$f)" || echo "  $$f: already stopped"; \
		rm -f $$f; \
	done
	@echo "Done"

status: install
	@$(PYTHON) monitor.py

docker-build:
	$(COMPOSE) build

docker-up:
	$(COMPOSE) up -d
	@echo "All 7 agents running. Check with: make docker-logs"

docker-down:
	$(COMPOSE) down

docker-logs:
	$(COMPOSE) logs -f --tail=50

docker-status:
	$(COMPOSE) ps

# ── VPS / systemd deployment ──────────────────────────────────────────────────
# Run this on the production VPS as root.

INSTALL_DIR := /opt/numbers-agents

deploy-vps:
	@echo "=== Deploying to $(INSTALL_DIR) ==="
	mkdir -p $(INSTALL_DIR)
	cp *.py requirements.txt .env $(INSTALL_DIR)/
	cd $(INSTALL_DIR) && python3 -m venv venv && venv/bin/pip install -r requirements.txt
	mkdir -p $(INSTALL_DIR)/state $(INSTALL_DIR)/logs
	id agent 2>/dev/null || useradd -r -s /bin/false -d $(INSTALL_DIR) agent
	chown -R agent:agent $(INSTALL_DIR)
	cp systemd/*.service /etc/systemd/system/
	systemctl daemon-reload
	systemctl enable numbers-provart numbers-newsprove numbers-agentlog \
	                  numbers-dataprove numbers-socialprove numbers-researchprove numbers-codeprove
	systemctl start  numbers-provart numbers-newsprove numbers-agentlog \
	                 numbers-dataprove numbers-socialprove numbers-researchprove numbers-codeprove
	@echo "=== Deployed. Check status with: systemctl status 'numbers-*' ==="
