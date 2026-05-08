"""Quick smoke-test: screenshot one HN story and print the result (no registration)."""
import hashlib
import os
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

TEST_URL = "https://en.wikipedia.org/wiki/Numbers_protocol"
TMP_PATH = "/tmp/test_screenshot.png"

def screenshot_page(browser, url, tmp_path):
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        ignore_https_errors=True,
    )
    page = context.new_page()
    try:
        page.goto(url, timeout=15000, wait_until="domcontentloaded")
        html = page.content()
        content_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
        page.screenshot(path=tmp_path, full_page=False)
        return content_hash
    finally:
        page.close()
        context.close()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
    print(f"Testing screenshot of: {TEST_URL}")
    content_hash = screenshot_page(browser, TEST_URL, TMP_PATH)
    browser.close()

size_kb = os.path.getsize(TMP_PATH) / 1024
print(f"content_hash : sha256:{content_hash}")
print(f"screenshot   : {TMP_PATH}  ({size_kb:.1f} KB)")
print(f"status       : OK")
os.unlink(TMP_PATH)
