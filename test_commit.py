"""
End-to-end test: screenshot a URL, register it, attach provenance commit,
verify the commit appears in the API response.
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright
from common import get_capture

TEST_URL   = "https://news.ycombinator.com"
AGENT_ID   = "Numbers Protocol Reference Agent #2 (NewsProve)"

def main():
    capture = get_capture()

    # ── Step 1: Screenshot ────────────────────────────────────────────────────
    print(f"Screenshotting {TEST_URL} ...")
    tmp_png = "/tmp/test_commit_screenshot.png"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
        ctx  = browser.new_context(viewport={"width": 1280, "height": 800}, user_agent="Mozilla/5.0 Chrome/120")
        page = ctx.new_page()
        page.goto(TEST_URL, timeout=15000, wait_until="domcontentloaded")
        html = page.content()
        content_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
        raw_text = page.inner_text("body")
        excerpt  = " ".join(raw_text.split())[:500]
        page.screenshot(path=tmp_png, full_page=False)
        ctx.close()
        browser.close()

    size_kb = os.path.getsize(tmp_png) / 1024
    print(f"  screenshot : {size_kb:.1f} KB")
    print(f"  content_hash : sha256:{content_hash[:16]}...")
    print(f"  excerpt : {excerpt[:80]}...")

    # ── Step 2: Register PNG ──────────────────────────────────────────────────
    ts      = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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
    token = os.environ.get("Capture_Token_Admin_Omni") or os.environ.get("CAPTURE_ADMIN_TOKEN")
    resp  = httpx.get(
        f"https://api.numbersprotocol.io/api/v3/assets/{asset.nid}/",
        headers={"Authorization": f"Token {token}"},
        timeout=15,
    )
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
