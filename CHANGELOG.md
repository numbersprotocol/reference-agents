# Changelog

All notable changes to the Numbers Protocol Reference Agents project.

## [Unreleased] — Campaign in Progress (Day 9+)

### Added
- Campaign Results section in README with live metrics
- This CHANGELOG file

### Planned
- Release tag `v1.0.0-campaign` on Day 14 (campaign conclusion)
- Final campaign statistics in README

---

## [0.3.0] — 2026-05-11

### Fixed
- **ProvArt timeout**: Increased `httpx.Timeout(read=)` from 60s to 120s. Pollinations FLUX image generation requires 60–90s; the previous 60s timeout caused frequent failures and was strongly correlated with the 27–38min session collapse pattern.

### Changed
- **SocialProve**: Upgraded from unauthenticated Reddit JSON API to OAuth-authenticated Reddit API using `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET`. Eliminates rate-limiting and User-Agent blocking issues.

---

## [0.2.0] — 2026-05-08

### Added
- **Log rotation**: `RotatingFileHandler` (1MB max, 2 backups) via `setup_rotating_log()` in `common.py`. Prevents unbounded log growth across long sessions.
- **Memory management**: `maybe_collect()` function in `common.py` — periodic `gc.collect()` every 50 cycles to prevent memory accumulation in long-running sessions.
- **Watchdog**: `watchdog.sh` — bash-based process monitor checking all 7 agents + synctrigger every 5 minutes, auto-restarting any that die.

### Fixed
- State file deduplication now uses LRU trimming (max 20K entries) to prevent unbounded growth.

---

## [0.1.0] — 2026-05-06

### Added
- Initial release of 7 reference agents:
  - **ProvArt** — AI-generated art provenance (Pollinations.ai / Replicate)
  - **NewsProve** — Hacker News story archival with Playwright screenshots
  - **AgentLog** — arXiv paper analysis audit trails (template / Groq LLM)
  - **DataProve** — Open data timestamping (weather, seismic, air quality, crypto)
  - **SocialProve** — Reddit AI community post archival
  - **ResearchProve** — arXiv research paper provenance (5 categories)
  - **CodeProve** — GitHub file-level code change provenance
- Shared utilities in `common.py`: Capture SDK client, retry logic (3 attempts, exponential backoff), deduplication via JSON state files, Slack alerting, daily cap enforcement
- `monitor.py` for health checking and status reporting
- Docker deployment: `Dockerfile` + `docker-compose.yml`
- VPS deployment: 7 systemd unit files in `systemd/`
- Configuration via `.env.example` with 11 documented variables
- `synctrigger.py` daemon for 30-minute apAutoSync heartbeat

### Infrastructure
- All agents share a single Capture API token (single wallet on Numbers Mainnet)
- Each agent prefixes captions with "Numbers Protocol Reference Agent #N" for transparent on-chain attribution
- MIT license — fully open-source for community forking

---

## Campaign Milestones

| Date | Event | Registrations |
|---|---|---|
| May 6 | Repository created, 7 agents built | 0 |
| May 7 | Campaign Day 1 — agents go live | ~1,682 (Session 1) |
| May 8 | First crash-restart cycle established | ~2,964 (Day 3) |
| May 11 | ProvArt timeout fix — session stability improves | ~5,061 (Day 7) |
| May 12 | Day 8 — all-time daily record | 6,227 |
| May 13 | 21,000+ cumulative milestone | Ongoing |

---

*Part of the "Agents Prove It" campaign — [Numbers Protocol](https://numbersprotocol.io)*
