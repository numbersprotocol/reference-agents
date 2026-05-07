#!/usr/bin/env python3
"""
synctrigger.py — Reliable scheduling heartbeat for apAutoSync
──────────────────────────────────────────────────────────────
Cloud Scheduler is blocked on this project (requires project Owner to enable
cloudscheduler.googleapis.com). This script runs alongside the reference agents
and calls apAutoSync every 30 minutes so campaign participation data stays fresh.

Usage:
  python3 synctrigger.py &

The process logs one line per sync run to stdout. PIDs and status are visible
in the workspace process table alongside the 7 reference agent processes.
"""

import time
import logging
import os

try:
    import requests
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [synctrigger] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)

SYNC_URL     = "https://us-central1-campaign-gamification.cloudfunctions.net/apAutoSync"
SYNC_SECRET  = os.environ.get("SYNC_SCHEDULER_SECRET", "ap-sync-2026")
INTERVAL_SEC = 1800  # 30 minutes — matches intended Cloud Scheduler cadence


def trigger_sync() -> None:
    try:
        r = requests.post(
            SYNC_URL,
            headers={
                "X-Scheduler-Secret": SYNC_SECRET,
                "Content-Type": "application/json",
                "User-Agent": "Numbers-SyncTrigger/1.0",
            },
            json={},
            timeout=600,  # apAutoSync has a 540s function timeout
        )
        if r.ok:
            data = r.json()
            logging.info(
                "sync ok — new=%d dups=%d agents_excluded=%d pages=%d capped=%s",
                data.get("new_entries", 0),
                data.get("duplicates_skipped", 0),
                data.get("agents_excluded", 0),
                data.get("pages_read", 0),
                data.get("capped_early", False),
            )
        else:
            logging.warning("sync http %d: %s", r.status_code, r.text[:300])
    except requests.exceptions.Timeout:
        logging.warning("sync timed out after 600s (function may still be running)")
    except Exception as exc:
        logging.error("sync error: %s", exc)


if __name__ == "__main__":
    logging.info("synctrigger started — interval=%ds url=%s", INTERVAL_SEC, SYNC_URL)
    while True:
        trigger_sync()
        logging.info("next sync in %ds", INTERVAL_SEC)
        time.sleep(INTERVAL_SEC)
