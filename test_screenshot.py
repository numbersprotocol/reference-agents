"""Quick smoke-test: screenshot one HN story and print the result (no registration)."""
import logging
import os
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

from proofsnap_capture import capture_page_screenshot

TEST_URL = "https://en.wikipedia.org/wiki/Numbers_protocol"
TMP_PATH = "/tmp/test_screenshot.png"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
    print(f"Testing screenshot of: {TEST_URL}")
    try:
        result = capture_page_screenshot(
            browser,
            TEST_URL,
            TMP_PATH,
            timestamp=datetime.now(timezone.utc),
            timeout_ms=15000,
            width=1280,
            height=800,
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            logger=logging.getLogger("test_screenshot"),
        )
    finally:
        browser.close()

if not result:
    raise SystemExit("screenshot failed")

content_hash, _excerpt = result

size_kb = os.path.getsize(TMP_PATH) / 1024
print(f"content_hash : sha256:{content_hash}")
print(f"screenshot   : {TMP_PATH}  ({size_kb:.1f} KB)")
print(f"status       : OK")
os.unlink(TMP_PATH)
