"""
End-to-end test: screenshot a URL, register it, attach provenance commit,
verify the commit appears in the API response.
"""
import json
import logging
import os
import time
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright
from common import get_capture
from proofsnap_capture import capture_page_screenshot

TEST_URL   = "https://news.ycombinator.com"
AGENT_ID   = "Numbers Protocol Reference Agent #2 (NewsProve)"

def main():
    capture = get_capture()

    # ── Step 1: Screenshot ────────────────────────────────────────────────────
    print(f"Screenshotting {TEST_URL} ...")
    tmp_png = "/tmp/test_commit_screenshot.png"
    screenshot_time = datetime.now(timezone.utc)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
        try:
            result = capture_page_screenshot(
                browser,
                TEST_URL,
                tmp_png,
                timestamp=screenshot_time,
                timeout_ms=15000,
                width=1280,
                height=800,
                user_agent="Mozilla/5.0 Chrome/120",
                logger=logging.getLogger("test_commit"),
            )
        finally:
            browser.close()

    if not result:
        raise SystemExit("screenshot failed")

    content_hash, excerpt = result

    size_kb = os.path.getsize(tmp_png) / 1024
    print(f"  screenshot : {size_kb:.1f} KB")
    print(f"  content_hash : sha256:{content_hash[:16]}...")
    print(f"  excerpt : {excerpt[:80]}...")

    # ── Step 2: Register PNG ──────────────────────────────────────────────────
    ts      = screenshot_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    caption = f"{AGENT_ID} | HN Front Page | test | {ts}"
    print(f"\nRegistering PNG ...")
    asset = capture.register(tmp_png, caption=caption, headline="HN Front Page")
    os.unlink(tmp_png)
    print(f"  NID : {asset.nid}")

    # ── Step 3: Attach provenance commit ──────────────────────────────────────
    provenance = {
        "agent":           AGENT_ID,
        "source":          "Hacker News",
        "url":             TEST_URL,
        "title":           "Hacker News Front Page",
        "screenshot_at":   ts,
        "content_hash":    f"sha256:{content_hash}",
        "content_excerpt": excerpt,
    }

    print(f"\nAttaching provenance commit ...")
    capture.update(
        asset.nid,
        commit_message="NewsProve provenance commit",
        custom_metadata=provenance,
    )
    print("  commit attached")

    # ── Step 4: Verify via API ────────────────────────────────────────────────
    import httpx
    time.sleep(2)
    resp = httpx.get(f"https://api.numbersprotocol.io/api/v3/assets/{asset.nid}/", timeout=15)
    data = resp.json()

    print(f"\n── Verification ─────────────────────────────────────────────")
    print(f"  asset_file   : ...{data.get('asset_file_name', '')}")
    print(f"  caption      : {data.get('caption', '')[:80]}")
    nit = data.get("nit_commit_custom", {})
    print(f"  nit_commit_custom :")
    print(json.dumps(nit, indent=4))
    print(f"\n  NID : {asset.nid}")
    print(f"  mainnet : https://mainnet.num.network/token/{asset.nid}")

if __name__ == "__main__":
    main()
