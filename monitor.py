"""
monitor.py — Reference Agent Health Monitor
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Reads each agent's deduplication state file and queries Numbers Mainnet
to report:
  - Registrations per agent today (from state file sizes as proxy)
  - Actual on-chain stats from mainnet.num.network
  - Daily target vs. actual comparison

Run manually:
  python monitor.py

Run as a cron job for daily Slack summary (add to crontab):
  0 9 * * * cd /opt/numbers-agents && /opt/numbers-agents/venv/bin/python monitor.py --slack
"""

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

STATE_DIR = Path(os.getenv("STATE_DIR", "./state"))
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL")

AGENTS = {
    "provart":       {"target": 500,  "label": "ProvArt       (#1)"},
    "newsprove":     {"target": 300,  "label": "NewsProve     (#2)"},
    "agentlog":      {"target": 200,  "label": "AgentLog      (#3)"},
    "dataprove":     {"target": 200,  "label": "DataProve     (#4)"},
    "socialprove":   {"target": 200,  "label": "SocialProve   (#5)"},
    "researchprove": {"target": 150,  "label": "ResearchProve (#6)"},
    "codeprove":     {"target": 50,   "label": "CodeProve     (#7)"},
}
TOTAL_TARGET = sum(a["target"] for a in AGENTS.values())  # 1,600


# ── State file reader ─────────────────────────────────────────────────────────

def read_state_count(agent: str) -> int:
    """
    Return the count of unique IDs registered by an agent.
    This is a cumulative total (all-time), not today-only.
    Use as a proxy for relative activity.
    """
    path = STATE_DIR / f"{agent}_seen.json"
    try:
        with open(path) as f:
            return len(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return 0


# ── Mainnet stats ─────────────────────────────────────────────────────────────

def fetch_mainnet_stats() -> dict | None:
    """
    Query mainnet.num.network for current transaction stats.
    The explorer exposes a basic stats endpoint.
    Returns None on failure.
    """
    urls_to_try = [
        "https://mainnet.num.network/api/v2/stats",
        "https://mainnet.num.network/api/stats",
    ]
    for url in urls_to_try:
        try:
            resp = httpx.get(
                url,
                headers={"Accept": "application/json"},
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            continue
    return None


# ── Reporting ─────────────────────────────────────────────────────────────────

def render_report(mainnet: dict | None) -> str:
    today = date.today().isoformat()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        f"Numbers Protocol Reference Agents — Status Report",
        f"Generated: {ts}",
        f"",
        f"{'Agent':<24} {'State IDs':>10}  {'Target/day':>12}",
        f"{'-'*52}",
    ]

    total_ids = 0
    for agent, info in AGENTS.items():
        count = read_state_count(agent)
        total_ids += count
        indicator = "OK" if count > 0 else "WARN (no state)"
        lines.append(
            f"{info['label']:<24} {count:>10,}  {info['target']:>10}/day  [{indicator}]"
        )

    lines += [
        f"{'-'*52}",
        f"{'Total registered IDs':<24} {total_ids:>10,}  {TOTAL_TARGET:>10}/day (target)",
        f"",
    ]

    # Mainnet stats
    def _fmt(v):
        return f"{int(v):,}" if str(v).isdigit() else str(v)

    if mainnet:
        lines += [
            f"Numbers Mainnet (live)",
            f"  Total transactions:  {_fmt(mainnet.get('total_transactions', 'n/a'))}",
            f"  Transactions today:  {mainnet.get('transactions_today', 'n/a')}",
            f"  Total wallets:       {_fmt(mainnet.get('total_addresses', 'n/a'))}",
        ]
    else:
        lines.append("Numbers Mainnet: could not reach explorer API")

    lines += [
        f"",
        f"State directory: {STATE_DIR.resolve()}",
        f"Note: 'State IDs' is a cumulative all-time count, not today-only.",
        f"      Check agent logs for today's registration counts.",
    ]

    return "\n".join(lines)


def post_slack(text: str) -> None:
    if not SLACK_WEBHOOK:
        print("SLACK_WEBHOOK_URL not set — skipping Slack post", file=sys.stderr)
        return
    try:
        resp = httpx.post(
            SLACK_WEBHOOK,
            json={"text": f"```\n{text}\n```"},
            timeout=10,
        )
        resp.raise_for_status()
        print("Slack report posted.")
    except Exception as exc:
        print(f"Slack post failed: {exc}", file=sys.stderr)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Reference Agent Monitor")
    parser.add_argument(
        "--slack", action="store_true", help="Post report to Slack webhook"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output raw JSON instead of text"
    )
    args = parser.parse_args()

    mainnet = fetch_mainnet_stats()

    if args.json:
        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "agents": {
                agent: {
                    "state_ids": read_state_count(agent),
                    "target_per_day": info["target"],
                }
                for agent, info in AGENTS.items()
            },
            "total_target_per_day": TOTAL_TARGET,
            "mainnet": mainnet,
        }
        print(json.dumps(data, indent=2))
        return

    report = render_report(mainnet)
    print(report)

    if args.slack:
        post_slack(report)


if __name__ == "__main__":
    main()
