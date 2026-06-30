# Numbers Protocol Reference Agents - Makefile

VENV     := venv
PYTHON   := $(VENV)/bin/python
PIP      := $(VENV)/bin/pip
COMPOSE  := docker compose

.PHONY: help setup install test lint run-all stop-all status \
        docker-build docker-up docker-down docker-logs docker-status deploy-vps

help:
	@echo ""
	@echo "Numbers Protocol Reference Agents"
	@echo ""
	@echo "  make setup          Create .env from .env.example"
	@echo "  make install        Create venv, install deps, install Chromium"
	@echo "  make test           Smoke-test public agents (imports only)"
	@echo "  make lint           Run ruff linter"
	@echo ""
	@echo "  make run-all        Run NewsProve and SocialProve in background"
	@echo "  make stop-all       Stop background agents started by make run-all"
	@echo "  make status         Show agent status via monitor.py"
	@echo ""
	@echo "  make docker-build   Build the Docker image"
	@echo "  make docker-up      Start public agents via docker-compose"
	@echo "  make docker-down    Stop public agents"
	@echo "  make docker-logs    Tail logs from public agents"
	@echo ""
	@echo "  make deploy-vps     Deploy to VPS via systemd (run on VPS)"
	@echo ""

setup:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example - edit it and set CAPTURE_TOKEN"; \
	else \
		echo ".env already exists"; \
	fi

install: setup
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PYTHON) -m playwright install chromium
	@echo "Install complete. Activate with: source $(VENV)/bin/activate"

test: install
	@echo "--- Smoke testing public agents (import + env check, no registration) ---"
	@$(PYTHON) -c "import common; print('  common.py      OK')"
	@$(PYTHON) -c "import newsprove; print('  newsprove.py   OK')"
	@$(PYTHON) -c "import socialprove; print('  socialprove.py OK')"
	@echo "--- Public agent imports OK ---"

lint: install
	$(PIP) install --quiet ruff
	$(VENV)/bin/ruff check *.py scripts/*.py

run-all: install
	@mkdir -p state logs
	@echo "Starting NewsProve and SocialProve in background..."
	@nohup $(PYTHON) -u newsprove.py    >> logs/newsprove.log    2>&1 & echo $$! > state/newsprove.pid
	@nohup $(PYTHON) -u socialprove.py  >> logs/socialprove.log  2>&1 & echo $$! > state/socialprove.pid
	@echo "Public agents started. PIDs stored in state/*.pid"
	@echo "Tail logs with: tail -f logs/*.log"
	@sleep 3 && $(PYTHON) monitor.py

stop-all:
	@echo "Stopping public agents..."
	@for f in state/newsprove.pid state/socialprove.pid; do \
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
	@echo "Public agents running. Check with: make docker-logs"

docker-down:
	$(COMPOSE) down

docker-logs:
	$(COMPOSE) logs -f --tail=50

docker-status:
	$(COMPOSE) ps

INSTALL_DIR := /opt/numbers-agents

deploy-vps:
	@echo "=== Deploying public agents to $(INSTALL_DIR) ==="
	mkdir -p $(INSTALL_DIR)
	cp common.py proofsnap_capture.py newsprove.py socialprove.py requirements.txt .env $(INSTALL_DIR)/
	cp -R assets $(INSTALL_DIR)/
	cd $(INSTALL_DIR) && python3 -m venv venv && venv/bin/pip install -r requirements.txt
	cd $(INSTALL_DIR) && venv/bin/python -m playwright install chromium
	mkdir -p $(INSTALL_DIR)/state $(INSTALL_DIR)/logs
	id agent 2>/dev/null || useradd -r -s /bin/false -d $(INSTALL_DIR) agent
	chown -R agent:agent $(INSTALL_DIR)
	cp systemd/*.service /etc/systemd/system/
	systemctl daemon-reload
	systemctl enable numbers-newsprove numbers-socialprove
	systemctl restart numbers-newsprove numbers-socialprove
	@echo "=== Deployed. Check status with: systemctl status 'numbers-*' ==="
