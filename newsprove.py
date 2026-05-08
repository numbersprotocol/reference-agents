"""
newsprove.py — NewsProve Reference Agent  (#2)  — Screenshot Edition
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Monitors Hacker News (top and new stories) **and** RSS feeds from major
tech publications.  For each new story it:

  1. Opens the URL in a headless Chromium browser (Playwright)
  2. Takes a viewport screenshot (PNG)
  3. Computes SHA-256 of the fully-rendered HTML (content integrity hash)
  4. Registers the screenshot + hash + metadata on Numbers Mainnet

This produces a **content provenance record**: the screenshot is the
visual proof of what the page looked like; the hash lets anyone verify
whether the content changed after registration.

Fallback: if Playwright fails (paywall, timeout, bot-block), the agent
falls back to registering a JSON metadata record (original behaviour).

Target:  250 transactions/day  (~1 every 290 seconds; slower due to
         Playwright page load time per story)
Cost:    $0/day  (Hacker News Firebase API + public RSS + free Playwright)

Data sources:
  - Hacker News: top + new stories (Firebase API)
  - RSS feeds: TechCrunch, Ars Technica, The Verge, Wired, MIT Tech
    Review, VentureBeat, Product Hunt, HackerNoon, TechMeme, TheNextWeb

Deduplication: stores seen IDs in state/newsprove_seen.json.
  HN items use their numeric ID; RSS items use feed_name + entry link hash.

Env vars:
  NEWSPROVE_INTERVAL             Cycle sleep seconds (default 290)
  NEWSPROVE_DAILY_CAP            Max registrations/day (default 250)
  NEWSPROVE_SCREENSHOT_TIMEOUT   Page load timeout ms (default 15000)
  NEWSPROVE_SCREENSHOT_WIDTH     Viewport width px (default 1280)
  NEWSPROVE_SCREENSHOT_HEIGHT    Viewport height px (default 800)

Usage:
  python newsprove.py
"""

import hashlib
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from common import (
    DailyCap,
    get_capture,
    load_seen_ids,
    maybe_collect,
    register_with_retry,
    save_seen_ids,
    setup_rotating_log,
    slack_alert,
    write_json_tmp,
)

load_dotenv()

AGENT_ID = "Numbers Protocol Reference Agent #2 (NewsProve)"
AGENT_SHORT = "newsprove"
logger = logging.getLogger(AGENT_SHORT)

INTERVAL            = int(os.getenv("NEWSPROVE_INTERVAL", "290"))
DAILY_CAP           = int(os.getenv("NEWSPROVE_DAILY_CAP", "250"))
SCREENSHOT_TIMEOUT  = int(os.getenv("NEWSPROVE_SCREENSHOT_TIMEOUT", "15000"))
SCREENSHOT_WIDTH    = int(os.getenv("NEWSPROVE_SCREENSHOT_WIDTH", "1280"))
SCREENSHOT_HEIGHT   = int(os.getenv("NEWSPROVE_SCREENSHOT_HEIGHT", "800"))

HN_TOP_URL  = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_NEW_URL  = "https://hacker-news.firebaseio.com/v0/newstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"

FETCH_TOP_N = 200  # consider this many top/new stories per cycle

# Realistic browser UA — reduces bot-detection rejections
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# ── RSS Feeds ────────────────────────────────────────────────────────────────

RSS_FEEDS = [
    ("TechCrunch",    "https://techcrunch.com/feed/"),
    ("ArsTechnica",   "https://feeds.arstechnica.com/arstechnica/index"),
    ("TheVerge",      "https://www.theverge.com/rss/index.xml"),
    ("Wired",         "https://www.wired.com/feed/rss"),
    ("MITTechReview", "https://www.technologyreview.com/feed/"),
    ("VentureBeat",   "https://venturebeat.com/feed/"),
    ("ProductHunt",   "https://www.producthunt.com/feed"),
    ("HackerNoon",    "https://hackernoon.com/feed"),
    ("TechMeme",      "https://www.techmeme.com/feed.xml"),
    ("TheNextWeb",    "https://thenextweb.com/feed"),
]

RSS_USER_AGENT = "ProvBot/1.0 (Numbers Protocol Reference Agent; +https://numbersprotocol.io)"


# ── Screenshot + hash ────────────────────────────────────────────────────────

def screenshot_page(browser, url: str, tmp_path: str) -> str | None:
    """
    Open *url* in a fresh browser context, take a viewport screenshot,
    and compute SHA-256 of the fully-rendered HTML.

    Returns the hex content hash on success, None on any failure.
    The caller is responsible for deleting *tmp_path* afterwards.

    Each call uses an isolated browser context so cookies and storage
    do not bleed between different sites within the same cycle.
    """
    context = None
    page = None
    try:
        context = browser.new_context(
            viewport={"width": SCREENSHOT_WIDTH, "height": SCREENSHOT_HEIGHT},
            user_agent=BROWSER_UA,
            java_script_enabled=True,
            ignore_https_errors=True,
        )
        page = context.new_page()
        page.goto(url, timeout=SCREENSHOT_TIMEOUT, wait_until="domcontentloaded")

        # Hash the fully-rendered HTML (post-JS execution) for content integrity
        html = page.content()
        content_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()

        # Viewport screenshot (faster + smaller than full_page=True)
        page.screenshot(path=tmp_path, full_page=False)

        logger.debug(f"screenshot ok  url={url[:60]}  hash={content_hash[:12]}...")
        return content_hash

    except PlaywrightTimeout:
        logger.warning(f"screenshot timeout ({SCREENSHOT_TIMEOUT}ms)  url={url[:80]}")
        return None
    except Exception as exc:
        logger.warning(f"screenshot failed  url={url[:80]}  err={exc}")
        return None
    finally:
        if page:
            try:
                page.close()
            except Exception:
                pass
        if context:
            try:
                context.close()
            except Exception:
                pass


# ── HN API helpers ────────────────────────────────────────────────────────────

def fetch_story_ids(feed: str = "top") -> list[int]:
    url = HN_TOP_URL if feed == "top" else HN_NEW_URL
    resp = httpx.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()[:FETCH_TOP_N]


def fetch_item(item_id: int) -> dict | None:
    try:
        resp = httpx.get(HN_ITEM_URL.format(id=item_id), timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.debug(f"fetch_item({item_id}) failed: {exc}")
        return None


# ── RSS helpers ──────────────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", text).strip()


def _entry_dedup_key(feed_name: str, link: str) -> str:
    """Create a short dedup key from feed name + link hash."""
    h = hashlib.sha256(link.encode()).hexdigest()[:12]
    return f"rss:{feed_name}:{h}"


def _parse_rss_entries(xml_text: str, feed_name: str) -> list[dict]:
    """Parse RSS 2.0 or Atom feed XML into a list of entry dicts."""
    entries = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.debug(f"XML parse error for {feed_name}: {exc}")
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}

    # Try RSS 2.0 first (channel/item)
    items = root.findall(".//item")
    if items:
        for item in items[:30]:
            title    = (item.findtext("title") or "").strip()[:200]
            link     = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            author   = (
                item.findtext("author")
                or item.findtext("{http://purl.org/dc/elements/1.1/}creator")
                or ""
            ).strip()
            desc = _strip_html(item.findtext("description") or "")[:300]
            if link:
                entries.append({
                    "title": title, "link": link, "published": pub_date,
                    "author": author, "description": desc,
                })
        return entries

    # Try Atom (feed/entry)
    atom_entries = root.findall("atom:entry", ns) or root.findall("entry")
    for entry in atom_entries[:30]:
        title   = (entry.findtext("atom:title", "", ns) or entry.findtext("title") or "").strip()[:200]
        link_el = (
            entry.find("atom:link[@rel='alternate']", ns)
            or entry.find("atom:link", ns)
            or entry.find("link")
        )
        link = ""
        if link_el is not None:
            link = link_el.get("href", "").strip() or (link_el.text or "").strip()
        published = (
            entry.findtext("atom:published", "", ns)
            or entry.findtext("atom:updated", "", ns)
            or entry.findtext("published")
            or entry.findtext("updated")
            or ""
        ).strip()
        author_el = entry.find("atom:author", ns) or entry.find("author")
        author = ""
        if author_el is not None:
            author = (
                author_el.findtext("atom:name", "", ns)
                or author_el.findtext("name")
                or author_el.text
                or ""
            ).strip()
        desc = _strip_html(
            entry.findtext("atom:summary", "", ns)
            or entry.findtext("summary")
            or entry.findtext("atom:content", "", ns)
            or entry.findtext("content")
            or ""
        )[:300]
        if link:
            entries.append({
                "title": title, "link": link, "published": published,
                "author": author, "description": desc,
            })

    return entries


def fetch_rss_entries(feed_name: str, feed_url: str) -> list[dict]:
    """Fetch and parse an RSS/Atom feed, returning entry dicts."""
    try:
        resp = httpx.get(
            feed_url,
            timeout=15,
            headers={
                "User-Agent": RSS_USER_AGENT,
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
            },
            follow_redirects=True,
        )
        resp.raise_for_status()
        return _parse_rss_entries(resp.text, feed_name)
    except Exception as exc:
        logger.debug(f"RSS fetch failed for {feed_name}: {exc}")
        return []


# ── Registration helpers ──────────────────────────────────────────────────────

def _register_screenshot(
    capture, browser, url: str, caption_prefix: str, fallback_record: dict, agent_short: str
) -> bool:
    """
    Attempt to screenshot *url* and register the PNG on-chain.
    Falls back to registering *fallback_record* as JSON if screenshot fails.

    Returns True if any registration succeeded.
    """
    tmp_png = f"/tmp/newsprove_{os.getpid()}_{int(time.time())}.png"
    content_hash = screenshot_page(browser, url, tmp_png)
    registered_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if content_hash and os.path.exists(tmp_png):
        # ── Screenshot path ───────────────────────────────────────────────────
        caption = (
            f"{caption_prefix} | "
            f"sha256:{content_hash} | "
            f"screenshot:{registered_at}"
        )
        try:
            nid = register_with_retry(capture, tmp_png, caption, agent_short)
            return nid is not None
        finally:
            if os.path.exists(tmp_png):
                os.unlink(tmp_png)
    else:
        # ── Fallback: JSON metadata ───────────────────────────────────────────
        if os.path.exists(tmp_png):
            os.unlink(tmp_png)
        fallback_record["screenshot"] = False
        fallback_record["screenshot_failed_at"] = registered_at
        tmp_json = write_json_tmp(fallback_record, prefix="newsprove_fallback_")
        caption = f"{caption_prefix} | no-screenshot | {registered_at}"
        try:
            nid = register_with_retry(capture, tmp_json, caption, agent_short)
            return nid is not None
        finally:
            if os.path.exists(tmp_json):
                os.unlink(tmp_json)


# ── Main cycles ───────────────────────────────────────────────────────────────

def run_hn_cycle(capture, seen: set, cap: DailyCap, browser) -> int:
    """Fetch unseen HN stories, screenshot each, and register on-chain."""
    registered = 0

    # Alternate between top and new feeds for variety
    feed = "new" if (int(time.time()) // 3600) % 2 == 0 else "top"
    try:
        ids = fetch_story_ids(feed)
    except Exception as exc:
        logger.error(f"fetch_story_ids failed: {exc}")
        return 0

    for item_id in ids:
        if not cap.check():
            break
        if str(item_id) in seen:
            continue

        item = fetch_item(item_id)
        if not item or item.get("type") != "story" or not item.get("url"):
            seen.add(str(item_id))
            continue

        ts    = datetime.fromtimestamp(item.get("time", time.time()), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        url   = item.get("url", "")
        title = item.get("title", "")

        caption_prefix = (
            f"{AGENT_ID} | "
            f"HN#{item_id} | "
            f"{title[:60]} | "
            f"score:{item.get('score', 0)} comments:{item.get('descendants', 0)} | "
            f"published:{ts}"
        )
        fallback_record = {
            "agent":        AGENT_ID,
            "source":       "Hacker News",
            "hn_id":        item_id,
            "title":        title,
            "url":          url,
            "author":       item.get("by", ""),
            "score":        item.get("score", 0),
            "comments":     item.get("descendants", 0),
            "published_at": ts,
            "feed":         feed,
        }

        ok = _register_screenshot(capture, browser, url, caption_prefix, fallback_record, AGENT_SHORT)
        if ok:
            seen.add(str(item_id))
            cap.record()
            registered += 1

        time.sleep(2)

    return registered


def run_rss_cycle(capture, seen: set, cap: DailyCap, browser) -> int:
    """Fetch unseen RSS entries, screenshot each, and register on-chain."""
    registered = 0
    ts_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for feed_name, feed_url in RSS_FEEDS:
        if not cap.check():
            break

        entries = fetch_rss_entries(feed_name, feed_url)
        logger.debug(f"RSS {feed_name}: {len(entries)} entries fetched")

        for entry in entries:
            if not cap.check():
                break

            link = entry.get("link", "")
            if not link:
                continue

            dedup_key = _entry_dedup_key(feed_name, link)
            if dedup_key in seen:
                continue

            title = entry.get("title", "")
            caption_prefix = (
                f"{AGENT_ID} | "
                f"{feed_name} | "
                f"{title[:60]} | "
                f"published:{entry.get('published', '')[:10]}"
            )
            fallback_record = {
                "agent":        AGENT_ID,
                "source":       f"RSS/{feed_name}",
                "feed":         feed_name,
                "title":        title,
                "url":          link,
                "author":       entry.get("author", ""),
                "description":  entry.get("description", ""),
                "published_at": entry.get("published", ""),
                "registered_at": ts_now,
            }

            ok = _register_screenshot(capture, browser, link, caption_prefix, fallback_record, AGENT_SHORT)
            if ok:
                seen.add(dedup_key)
                cap.record()
                registered += 1

            time.sleep(2)

        time.sleep(1)

    return registered


def run_cycle(capture, seen: set, cap: DailyCap) -> int:
    """Launch a Chromium browser, run HN + RSS cycles, then close it."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions",
            ],
        )
        logger.debug("Chromium launched")
        try:
            total  = run_hn_cycle(capture, seen, cap, browser)
            total += run_rss_cycle(capture, seen, cap, browser)
        finally:
            browser.close()
            logger.debug("Chromium closed")
    return total


def main():
    setup_rotating_log(AGENT_SHORT)
    logger.info(
        f"NewsProve starting | mode=screenshot | interval={INTERVAL}s | "
        f"daily_cap={DAILY_CAP} | screenshot_timeout={SCREENSHOT_TIMEOUT}ms"
    )
    slack_alert("[NewsProve] started (screenshot mode)", level="INFO")

    capture = get_capture()
    cap     = DailyCap(DAILY_CAP)
    seen    = load_seen_ids(AGENT_SHORT)

    while True:
        if cap.check():
            n = run_cycle(capture, seen, cap)
            logger.info(f"cycle complete: registered={n} remaining={cap.remaining()}")
            save_seen_ids(AGENT_SHORT, seen)
        else:
            sleep_s = cap.seconds_until_reset()
            logger.info(f"daily cap reached, sleeping {sleep_s:.0f}s")
            time.sleep(sleep_s + 1)
            continue

        maybe_collect()
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
