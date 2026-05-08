"""
newsprove.py — NewsProve Reference Agent  (#2)  — Screenshot + Commit Edition
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
For each new story, the agent:

  1. Opens the URL in headless Chromium (Playwright)
  2. Takes a viewport screenshot (PNG) — visual proof of the page
  3. Computes SHA-256 of the fully-rendered HTML — content integrity hash
  4. Extracts the first 500 chars of visible body text — content excerpt
  5. Registers the screenshot on Numbers Mainnet  →  NID
  6. Attaches a structured provenance commit to that NID:

       {
         "agent":          "Numbers Protocol Reference Agent #2 (NewsProve)",
         "source":         "Hacker News",
         "url":            "https://...",
         "title":          "...",
         "author":         "...",
         "score":          42,
         "comments":       17,
         "published_at":   "2026-05-08T04:23:06Z",
         "screenshot_at":  "2026-05-08T04:23:15Z",
         "content_hash":   "sha256:a3f9c2...",
         "content_excerpt": "First 500 characters of visible body text..."
       }

  Fallback: if Playwright fails (paywall, timeout, bot-block), falls back to
  registering a JSON metadata record — no screenshot, no commit.

Target:  250 transactions/day
Cost:    $0/day

Data sources:
  - Hacker News: top + new stories (Firebase API)
  - RSS: TechCrunch, Ars Technica, The Verge, Wired, MIT Tech Review,
    VentureBeat, Product Hunt, HackerNoon, TechMeme, TheNextWeb

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

AGENT_ID    = "Numbers Protocol Reference Agent #2 (NewsProve)"
AGENT_SHORT = "newsprove"
logger      = logging.getLogger(AGENT_SHORT)

INTERVAL           = int(os.getenv("NEWSPROVE_INTERVAL", "290"))
DAILY_CAP          = int(os.getenv("NEWSPROVE_DAILY_CAP", "250"))
SCREENSHOT_TIMEOUT = int(os.getenv("NEWSPROVE_SCREENSHOT_TIMEOUT", "15000"))
SCREENSHOT_WIDTH   = int(os.getenv("NEWSPROVE_SCREENSHOT_WIDTH", "1280"))
SCREENSHOT_HEIGHT  = int(os.getenv("NEWSPROVE_SCREENSHOT_HEIGHT", "800"))

HN_TOP_URL  = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_NEW_URL  = "https://hacker-news.firebaseio.com/v0/newstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"

FETCH_TOP_N = 200

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


# ── Screenshot + content extraction ──────────────────────────────────────────

def screenshot_page(browser, url: str, tmp_path: str) -> tuple[str, str] | None:
    """
    Open *url* in a fresh browser context.

    Returns (content_hash, excerpt) on success where:
      content_hash — SHA-256 hex of the fully-rendered HTML
      excerpt      — first 500 chars of normalised visible body text

    Returns None on any failure (timeout, paywall, bot-block, etc.).

    The caller is responsible for deleting *tmp_path* afterwards.
    Each call uses an isolated context so cookies do not bleed between sites.
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

        # Content hash — SHA-256 of fully-rendered HTML
        html = page.content()
        content_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()

        # Visible text excerpt — normalise whitespace, cap at 500 chars
        try:
            raw_text = page.inner_text("body")
            excerpt = " ".join(raw_text.split())[:500]
        except Exception:
            excerpt = ""

        # Viewport screenshot
        page.screenshot(path=tmp_path, full_page=False)

        logger.debug(f"screenshot ok  hash={content_hash[:12]}  url={url[:70]}")
        return content_hash, excerpt

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


# ── Registration helpers ──────────────────────────────────────────────────────

def _attach_provenance_commit(capture, nid: str, metadata: dict) -> None:
    """
    Attach structured provenance metadata as a second commit on the asset.

    Uses capture.update(nid, custom_metadata=...) which writes to
    nit_commit_custom in the Numbers Protocol asset tree — a proper
    on-chain provenance commit, not just a text caption.

    Never raises — a failed commit does not invalidate the registered asset.
    """
    try:
        capture.update(
            nid,
            commit_message="NewsProve provenance commit",
            custom_metadata=metadata,
        )
        logger.debug(f"provenance commit attached  nid={nid}")
    except Exception as exc:
        logger.warning(f"provenance commit failed  nid={nid}  err={exc}")


def _register_screenshot_with_commit(
    capture,
    browser,
    url: str,
    caption: str,
    headline: str,
    provenance: dict,
) -> str | None:
    """
    Take a screenshot of *url*, register it, then attach *provenance* as a commit.

    Returns the NID on success, None on failure.
    Falls back to JSON metadata registration if Playwright fails.
    """
    tmp_png = f"/tmp/newsprove_{os.getpid()}_{int(time.time())}.png"
    registered_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    result = screenshot_page(browser, url, tmp_png)

    if result is not None and os.path.exists(tmp_png):
        content_hash, excerpt = result

        # Build the provenance commit payload
        commit_payload = {
            **provenance,
            "screenshot_at":   registered_at,
            "content_hash":    f"sha256:{content_hash}",
            "content_excerpt": excerpt,
        }

        # Step 1 — register the PNG
        try:
            nid = register_with_retry(capture, tmp_png, caption, AGENT_SHORT)
        finally:
            if os.path.exists(tmp_png):
                os.unlink(tmp_png)

        if nid is None:
            return None

        # Step 2 — attach structured provenance as a commit
        _attach_provenance_commit(capture, nid, commit_payload)
        logger.info(
            f"registered  nid={nid}  "
            f"sha256={content_hash[:12]}  "
            f"caption={caption[:60]!r}"
        )
        return nid

    else:
        # ── Fallback: JSON metadata only ─────────────────────────────────────
        if os.path.exists(tmp_png):
            os.unlink(tmp_png)

        logger.info(f"screenshot failed, falling back to JSON  url={url[:80]}")
        fallback = {
            **provenance,
            "registered_at":  registered_at,
            "screenshot":     False,
        }
        tmp_json = write_json_tmp(fallback, prefix="newsprove_fallback_")
        fallback_caption = f"{caption} | no-screenshot"
        try:
            nid = register_with_retry(capture, tmp_json, fallback_caption, AGENT_SHORT)
            return nid
        finally:
            if os.path.exists(tmp_json):
                os.unlink(tmp_json)


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
    return re.sub(r"<[^>]+>", "", text).strip()


def _entry_dedup_key(feed_name: str, link: str) -> str:
    h = hashlib.sha256(link.encode()).hexdigest()[:12]
    return f"rss:{feed_name}:{h}"


def _parse_rss_entries(xml_text: str, feed_name: str) -> list[dict]:
    entries = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.debug(f"XML parse error for {feed_name}: {exc}")
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}

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


# ── Main cycles ───────────────────────────────────────────────────────────────

def run_hn_cycle(capture, seen: set, cap: DailyCap, browser) -> int:
    registered = 0
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

        caption  = f"{AGENT_ID} | HN#{item_id} | {title[:80]} | {ts}"
        headline = title[:25]

        provenance = {
            "agent":        AGENT_ID,
            "source":       "Hacker News",
            "hn_id":        item_id,
            "feed":         feed,
            "url":          url,
            "title":        title,
            "author":       item.get("by", ""),
            "score":        item.get("score", 0),
            "comments":     item.get("descendants", 0),
            "published_at": ts,
        }

        nid = _register_screenshot_with_commit(
            capture, browser, url, caption, headline, provenance
        )
        if nid:
            seen.add(str(item_id))
            cap.record()
            registered += 1

        time.sleep(2)

    return registered


def run_rss_cycle(capture, seen: set, cap: DailyCap, browser) -> int:
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

            title     = entry.get("title", "")
            published = entry.get("published", "")

            caption  = f"{AGENT_ID} | {feed_name} | {title[:70]} | {published[:10]}"
            headline = title[:25]

            provenance = {
                "agent":        AGENT_ID,
                "source":       f"RSS/{feed_name}",
                "feed":         feed_name,
                "url":          link,
                "title":        title,
                "author":       entry.get("author", ""),
                "description":  entry.get("description", ""),
                "published_at": published,
                "registered_at": ts_now,
            }

            nid = _register_screenshot_with_commit(
                capture, browser, link, caption, headline, provenance
            )
            if nid:
                seen.add(dedup_key)
                cap.record()
                registered += 1

            time.sleep(2)

        time.sleep(1)

    return registered


def run_cycle(capture, seen: set, cap: DailyCap) -> int:
    """Launch Chromium, run HN + RSS cycles, then close."""
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
        f"NewsProve starting | mode=screenshot+commit | interval={INTERVAL}s | "
        f"daily_cap={DAILY_CAP} | screenshot_timeout={SCREENSHOT_TIMEOUT}ms"
    )
    slack_alert("[NewsProve] started (screenshot + provenance commit mode)", level="INFO")

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
