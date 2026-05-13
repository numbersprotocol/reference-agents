"""Fetch and display real asset examples from NP API for NewsProve, AgentLog, DataProve."""
import json
import os
import sys
import httpx

TOKEN = os.environ.get("Capture_Token_Admin_Omni") or os.environ.get("CAPTURE_ADMIN_TOKEN")
BASE = "https://api.numbersprotocol.io/api/v3/assets"
HEADERS = {"Authorization": f"Token {TOKEN}", "User-Agent": "Numbers-RefAgents/1.0"}

NIDS = {
    "NewsProve":  "bafkreigu3womudxajgfpsttlehf4d4d3p4u3sjzo5hzd3k3kke725kxwdy",
    "AgentLog":   "bafkreib2pqfhs5ozs6vekn52usxhch4yahmf6mhdl3zw2zmpa73ut34mf4",
    "DataProve":  "bafkreidrlt5v5xb733iw67wfvncuhauso46kdalg27ydjuige2o3mivwiu",
}

FIELDS = ["nid", "caption", "created_at", "owner_name", "asset_file"]

for agent, nid in NIDS.items():
    print(f"\n{'='*60}")
    print(f"  {agent}")
    print(f"{'='*60}")
    resp = httpx.get(f"{BASE}/{nid}/", headers=HEADERS, timeout=20)
    if resp.status_code != 200:
        print(f"  ERROR {resp.status_code}: {resp.text[:200]}")
        continue
    d = resp.json()
    for k in FIELDS:
        v = d.get(k, "—")
        if k == "caption" and v:
            print(f"  {k}:\n    {v}")
        else:
            print(f"  {k}: {v}")
    # Also fetch the raw file content (JSON for AgentLog/DataProve, text for NewsProve)
    file_url = d.get("asset_file")
    if file_url:
        try:
            fr = httpx.get(file_url, timeout=20, follow_redirects=True)
            content_type = fr.headers.get("content-type", "")
            if "json" in content_type:
                payload = fr.json()
                print(f"\n  --- file content (JSON) ---")
                print(json.dumps(payload, indent=2, ensure_ascii=False)[:1200])
            else:
                print(f"\n  --- file content (text) ---")
                print(fr.text[:1200])
        except Exception as e:
            print(f"  (could not fetch file: {e})")
