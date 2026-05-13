"""Trigger apAutoSync via synctrigger's approach (reads SYNC_SCHEDULER_SECRET from env)."""
import httpx
import os

SYNC_URL = "https://us-central1-campaign-gamification.cloudfunctions.net/apAutoSync"
SECRET   = os.environ.get("SYNC_SCHEDULER_SECRET", "ap-sync-2026")

headers = {
    "X-Scheduler-Secret": SECRET,
    "Content-Type": "application/json",
    "User-Agent": "Numbers-SyncTrigger/1.0",
}

try:
    resp = httpx.post(SYNC_URL, headers=headers, json={}, timeout=90)
    print(f"Status: {resp.status_code}")
    print(resp.text[:600])
except Exception as e:
    print(f"Error: {e}")
