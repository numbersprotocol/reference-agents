# Numbers Protocol Reference Agents

**"Agents Prove It" Campaign — Lever 1**

Seven autonomous Python agents that register provenance records on Numbers Mainnet
via the Capture SDK. Together they target **~1,600 on-chain transactions per day**
as the campaign's anchor lever, at a running cost of **~$0–1/day**.

---

## Agents at a glance

| # | Agent | What it registers | Target |
|---|---|---|---|
| 1 | **ProvArt** | AI-generated images (Pollinations.ai free / Replicate paid) | 500/day |
| 2 | **NewsProve** | Hacker News story metadata (title, URL, score, author) | 300/day |
| 3 | **AgentLog** | arXiv paper analysis logs (LLM audit trail, template or Groq) | 200/day |
| 4 | **DataProve** | Weather, crypto prices, air quality (Open-Meteo, CoinGecko, OpenAQ) | 200/day |
| 5 | **SocialProve** | Reddit AI community posts (r/ML, r/LocalLLaMA, r/artificial) | 200/day |
| 6 | **ResearchProve** | arXiv paper abstracts (cs.AI, cs.LG, cs.CV, cs.CL, stat.ML) | 150/day |
| 7 | **CodeProve** | GitHub file-level changes in commits (numbersprotocol org + top AI repos) | 50/day |
| | **Total** | | **1,600/day** |

All agents are **publicly identified** on-chain as "Numbers Protocol Reference Agent #N".
All wallets are auditable on [mainnet.num.network](https://mainnet.num.network).

---

## Prerequisites

| Item | How | Time |
|---|---|---|
| **Capture API token** | Free at [docs.captureapp.xyz](https://docs.captureapp.xyz) — sign up, create a project, copy token | 5 min |
| **Python 3.11+** | `python3 --version` | — |
| **Docker + Compose** (recommended) | [docs.docker.com/get-docker](https://docs.docker.com/get-docker/) | — |
| **GitHub PAT** (optional, for CodeProve) | [github.com/settings/tokens](https://github.com/settings/tokens) — `read:public_repo` scope | 2 min |
| **Groq API key** (optional, for AgentLog LLM mode) | Free at [console.groq.com](https://console.groq.com) | 2 min |

---

## Quick start (Docker — recommended)

```bash
# 1. Clone the repo
git clone https://github.com/numbersprotocol/reference-agents
cd reference-agents

# 2. Create your .env file
cp .env.example .env
nano .env          # Set CAPTURE_TOKEN at minimum

# 3. Build and start all 7 agents
docker compose up -d

# 4. Verify agents are running
docker compose ps
docker compose logs -f provart   # tail one agent

# 5. Check status
python monitor.py
```

---

## Quick start (local, no Docker)

```bash
# 1. Set up virtualenv and install
make install

# 2. Configure
cp .env.example .env && nano .env   # set CAPTURE_TOKEN

# 3. Start all agents in background
make run-all

# 4. Check status
make status

# 5. Stop all agents
make stop-all
```

---

## VPS deployment (systemd, production)

```bash
# On the VPS, as root:
git clone https://github.com/numbersprotocol/reference-agents /tmp/ref-agents
cd /tmp/ref-agents
cp .env.example /opt/numbers-agents/.env
nano /opt/numbers-agents/.env    # set CAPTURE_TOKEN and optionally SLACK_WEBHOOK_URL

make deploy-vps

# Verify all 7 services are active:
systemctl status 'numbers-*'

# Tail logs:
journalctl -u numbers-provart -f
```

---

## Configuration reference

All settings are environment variables. See [`.env.example`](.env.example) for the full list.

| Variable | Required | Default | Description |
|---|---|---|---|
| `CAPTURE_TOKEN` | **Yes** | — | Capture API token |
| `PROVART_MODE` | No | `pollinations` | `pollinations` (free) or `replicate` ($0.002/image) |
| `REPLICATE_API_TOKEN` | If replicate mode | — | Replicate API key |
| `AGENTLOG_MODE` | No | `template` | `template` (no key) or `groq` (LLM calls) |
| `GROQ_API_KEY` | If groq mode | — | Groq API key (free tier) |
| `GITHUB_TOKEN` | No | — | GitHub PAT (5000 req/hr vs 60 without) |
| `GITHUB_ORG` | No | `numbersprotocol` | GitHub org to monitor |
| `SLACK_WEBHOOK_URL` | No | — | Slack Incoming Webhook for alerts |
| `STATE_DIR` | No | `./state` | Directory for deduplication state files |
| `LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

---

## How it works

Each agent runs an infinite loop:

```
fetch data from public API
  → check dedup state (state/{agent}_seen.json)
    → write metadata to temp JSON file
      → capture.register(tmp_file, caption=...)  ← one on-chain txn
        → update dedup state
          → sleep(interval)
```

The `DailyCap` class enforces a per-agent daily transaction ceiling. When the cap is
reached, the agent sleeps until the next 24-hour window opens.

**Deduplication** uses a per-agent JSON file (e.g. `state/provart_seen.json`) to track
IDs already registered. This survives container restarts.

**Retry logic** (in `common.py`): up to 3 attempts per registration, with 5s / 10s / 15s
back-off. After 3 failures, a Slack alert fires and the item is skipped.

---

## Monitoring

```bash
# Print status report to stdout
python monitor.py

# Post report to Slack
python monitor.py --slack

# JSON output (for dashboards)
python monitor.py --json

# Add daily 9am Slack report to crontab:
# 0 9 * * * cd /opt/numbers-agents && venv/bin/python monitor.py --slack
```

---

## Scaling

If Week 1 tracking shows daily total below ~2,400 target:

1. **Lower agent intervals** — e.g. `PROVART_INTERVAL=120` (from 173) raises ProvArt from 500→720/day
2. **Raise daily caps** — e.g. `PROVART_DAILY_CAP=700`
3. **Add a new agent** — duplicate any agent script, rename, and add a new service to `docker-compose.yml`
4. **Deploy additional Capture tokens** — give each agent its own token for wallet-level attribution

All free-tier data sources (HN, arXiv, Reddit, Open-Meteo, CoinGecko public API) have
sufficient volume to support 2–3× the default daily caps.

---

## Transparency / anti-Sybil note

- All 7 agents are identified by their wallet addresses (public on mainnet.num.network)
- Source code is open in this repo — anyone can verify what each agent registers
- Each registration is a **distinct, legitimate provenance record** with a real external source
- The campaign report will disaggregate: reference agents / human creators / community agents

---

## Cost summary

| Item | Monthly cost |
|---|---|
| AI image generation (ProvArt, Pollinations.ai mode) | **$0** |
| AI image generation (ProvArt, Replicate mode) | ~$30 |
| Capture API storage (47K files × 0.1 NUM) | ~$20/mo |
| On-chain gas (~47K txns × 0.004 NUM) | ~$1/mo |
| VPS / hosting | $5–10/mo (smallest DigitalOcean or Hetzner instance) |
| All external APIs | $0 (all free tiers) |

---

## File structure

```
reference-agents/
├── common.py          # Shared utilities (Capture client, retry, dedup, Slack)
├── provart.py         # Agent #1 — AI image provenance
├── newsprove.py       # Agent #2 — News archival
├── agentlog.py        # Agent #3 — LLM audit trails
├── dataprove.py       # Agent #4 — Open data timestamping
├── socialprove.py     # Agent #5 — Reddit AI community archival
├── researchprove.py   # Agent #6 — arXiv research provenance
├── codeprove.py       # Agent #7 — Code change provenance
├── monitor.py         # Health check and status reporter
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── state/             # Deduplication state (auto-created)
└── systemd/           # systemd unit files for VPS deployment
    ├── numbers-provart.service
    ├── numbers-newsprove.service
    ├── numbers-agentlog.service
    ├── numbers-dataprove.service
    ├── numbers-socialprove.service
    ├── numbers-researchprove.service
    └── numbers-codeprove.service
```

---

## Pre-launch checklist (from proposal Section 11)

Before running in production, confirm with the Numbers Protocol team:

- [ ] **Keke AI** supports 7+ concurrent agents at 200+ txns/day each — or use this VPS path
- [ ] **Capture API gas rate**: 0.004 NUM or 0.016 NUM per txn (affects budget by ~$2)
- [ ] **Reddit .json stability**: if blocked, set `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET`
      for OAuth mode (agent auto-upgrades)
- [ ] **CAPTURE_TOKEN** created and funded (NUM for storage + gas)
- [ ] **SLACK_WEBHOOK_URL** configured for failure alerts

---

*Part of the "Agents Prove It" campaign — [Numbers Protocol](https://numbersprotocol.io)*
*Human Truth. Machine Proof.*
