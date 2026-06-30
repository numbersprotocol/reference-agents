"""
monitor.py - Public reference agent health monitor.

Reports deduplication state counts for NewsProve and SocialProve, plus live
Numbers Mainnet stats. State counts are cumulative local IDs, not exact daily
on-chain totals.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

STATE_DIR = Path(os.getenv("STATE_DIR", "./state"))
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL")

AGENTS = {
    "newsprove": {"target": 300, "label": "NewsProve"},
    "socialprove": {"target": 200, "label": "SocialProve"},
}
TOTAL_TARGET = sum(agent["target"] for agent in AGENTS.values())


def read_state_count(agent: str) -> int:
    path = STATE_DIR / f"{agent}_seen.json"
    try:
        with open(path, encoding="utf-8") as f:
            return len(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return 0


def fetch_mainnet_stats() -> dict | None:
    for url in (
        "https://mainnet.num.network/api/v2/stats",
        "https://mainnet.num.network/api/stats",
    ):
        try:
            resp = httpx.get(url, headers={"Accept": "application/json"}, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            continue
    return None


def render_report(mainnet: dict | None) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "Numbers Protocol Reference Agents - Status Report",
        f"Generated: {ts}",
        "",
        f"{'Agent':<16} {'State IDs':>10}  {'Target/day':>12}",
        "-" * 42,
    ]

    total_ids = 0
    for agent, info in AGENTS.items():
        count = read_state_count(agent)
        total_ids += count
        indicator = "OK" if count > 0 else "WARN (no state)"
        lines.append(
            f"{info['label']:<16} {count:>10,}  {info['target']:>10}/day  [{indicator}]"
        )

    lines.extend(
        [
            "-" * 42,
            f"{'Total state IDs':<16} {total_ids:>10,}  {TOTAL_TARGET:>10}/day",
            "",
        ]
    )

    def fmt(value):
        return f"{int(value):,}" if str(value).isdigit() else str(value)

    if mainnet:
        lines.extend(
            [
                "Numbers Mainnet (live)",
                f"  Total transactions:  {fmt(mainnet.get('total_transactions', 'n/a'))}",
                f"  Transactions today:  {mainnet.get('transactions_today', 'n/a')}",
                f"  Total wallets:       {fmt(mainnet.get('total_addresses', 'n/a'))}",
            ]
        )
    else:
        lines.append("Numbers Mainnet: could not reach explorer API")

    lines.extend(
        [
            "",
            f"State directory: {STATE_DIR.resolve()}",
            "Note: state IDs are cumulative local deduplication counts.",
        ]
    )
    return "\n".join(lines)


def post_slack(text: str) -> None:
    if not SLACK_WEBHOOK:
        print("SLACK_WEBHOOK_URL not set - skipping Slack post", file=sys.stderr)
        return
    try:
        resp = httpx.post(SLACK_WEBHOOK, json={"text": f"```\n{text}\n```"}, timeout=10)
        resp.raise_for_status()
        print("Slack report posted.")
    except Exception as exc:
        print(f"Slack post failed: {exc}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Reference Agent Monitor")
    parser.add_argument("--slack", action="store_true", help="Post report to Slack")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
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
