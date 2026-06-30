# Numbers Protocol Reference Agents

Public reference agents for registering provenance records on Numbers Mainnet.

This repository intentionally includes only two public examples:

| Agent | Source | What it proves |
|---|---|---|
| NewsProve | Hacker News + technology RSS feeds | News page provenance with screenshot, content hash, excerpt, and source metadata |
| SocialProve | Reddit, with Mastodon and Dev.to fallback | Social post provenance with source metadata and content hashes for text posts |

The examples show how agents can preserve public digital records with Numbers Protocol provenance infrastructure for humans and AI. Human Truth. Machine Proof.

## How To Join Fork & Build

1. Fork this repository:

   https://github.com/numbersprotocol/reference-agents

2. Clone your fork:

   ```bash
   git clone https://github.com/YOUR_GITHUB_USERNAME/reference-agents
   cd reference-agents
   ```

3. Create your environment file:

   ```bash
   cp .env.example .env
   ```

4. Add your Capture API token to `.env`:

   ```bash
   CAPTURE_TOKEN=your_capture_token_here
   ```

5. Run one or both public agents. Every successful registration creates a provenance record on Numbers Mainnet from the wallet tied to your Capture token.

6. Keep the agents running during the campaign period, then submit your fork URL and Numbers Mainnet wallet address through the official campaign submission channel when announced.

## Prerequisites

| Item | Required | Notes |
|---|---:|---|
| Python 3.11+ | Yes | Needed for local execution |
| Capture API token | Yes | Used to register records on Numbers Mainnet |
| Docker + Compose | Optional | Recommended for always-on local or VPS runs |
| Reddit app credentials | Optional | Improves SocialProve reliability; fallback sources run without Reddit OAuth |
| Slack webhook | Optional | Used only for alerts and monitor summaries |

## Quick Start With Docker

```bash
cp .env.example .env
nano .env

docker compose up -d
docker compose ps
docker compose logs -f newsprove
```

Stop the agents:

```bash
docker compose down
```

## Quick Start Without Docker

```bash
make install
make run-all
make status
```

Stop background agents started by `make run-all`:

```bash
make stop-all
```

## Run A Single Agent

```bash
python newsprove.py
python socialprove.py
```

## Configuration

All configuration lives in `.env`.

| Variable | Required | Default | Description |
|---|---:|---|---|
| `CAPTURE_TOKEN` | Yes | - | Capture API token used for registrations |
| `NEWSPROVE_INTERVAL` | No | `290` | Seconds between NewsProve cycles |
| `NEWSPROVE_DAILY_CAP` | No | `300` | Daily registration cap for NewsProve |
| `NEWSPROVE_SCREENSHOT_TIMEOUT` | No | `15000` | Browser page-load timeout in milliseconds |
| `NEWSPROVE_SCREENSHOT_WIDTH` | No | `1280` | Screenshot viewport width |
| `NEWSPROVE_SCREENSHOT_HEIGHT` | No | `800` | Screenshot viewport height |
| `SOCIALPROVE_INTERVAL` | No | `430` | Seconds between SocialProve cycles |
| `SOCIALPROVE_DAILY_CAP` | No | `200` | Daily registration cap for SocialProve |
| `REDDIT_CLIENT_ID` | No | - | Reddit OAuth client ID for SocialProve |
| `REDDIT_CLIENT_SECRET` | No | - | Reddit OAuth client secret for SocialProve |
| `SLACK_WEBHOOK_URL` | No | - | Optional Slack alert destination |
| `STATE_DIR` | No | `./state` | Deduplication state directory |
| `LOG_LEVEL` | No | `INFO` | Python log level |

## Agent Details

### NewsProve

NewsProve monitors Hacker News and selected technology RSS feeds. For each new story it attempts to:

1. Open the source URL in headless Chromium.
2. Capture a screenshot.
3. Hash the rendered HTML.
4. Extract a short visible-text excerpt.
5. Register the screenshot on Numbers Mainnet.
6. Attach structured source metadata to the registered asset.

If a page blocks screenshots or times out, NewsProve falls back to registering a JSON metadata record.

### SocialProve

SocialProve monitors public AI and machine-learning communities. With Reddit OAuth configured, it reads configured subreddits through Reddit's API. Without Reddit credentials, it falls back to public Mastodon and Dev.to sources.

For Reddit self-posts, SocialProve stores a normalized excerpt and SHA-256 hash of the body text so the record can still be verified if the post is later edited or deleted.

## Monitoring

Print a local status report:

```bash
python monitor.py
```

Output JSON:

```bash
python monitor.py --json
```

Post to Slack:

```bash
python monitor.py --slack
```

Check process and log-derived status:

```bash
python status.py
```

## VPS Deployment

On a VPS, after cloning the repo and creating `.env`:

```bash
sudo make deploy-vps
sudo systemctl status numbers-newsprove numbers-socialprove
sudo journalctl -u numbers-newsprove -f
```

The systemd services are in `systemd/`.

## File Structure

```text
reference-agents/
├── common.py
├── newsprove.py
├── socialprove.py
├── monitor.py
├── status.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── scripts/
│   ├── check_dedup.py
│   ├── check_state.py
│   └── check_syntax.py
├── systemd/
│   ├── numbers-newsprove.service
│   └── numbers-socialprove.service
├── test_commit.py
├── test_screenshot.py
└── test_socialprove_selftext.py
```

## Verification

Run syntax checks:

```bash
python scripts/check_syntax.py
```

Run import smoke tests:

```bash
make test
```

`make test` installs dependencies and Chromium for NewsProve screenshots.

## Notes

- The public repository exposes only NewsProve and SocialProve.
- Deduplication state and logs are local runtime files and are ignored by Git.
- `.env` must never be committed.
- Each registered record is auditable on Numbers Mainnet.

## License

MIT
