"""
newsprove.py — NewsProve Reference Agent  (#2)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Monitors Hacker News (top and new stories) **and** RSS feeds from major
tech publications, registering each story's metadata as a provenance
record on Numbers Mainnet.

Target:  500 transactions/day  (~1 every 290 seconds)
Cost:    $0/day  (Hacker News Firebase API + public RSS feeds)

Data sources:
  - Hacker News: top + new stories (Firebase API)
  - RSS feeds: TechCrunch, Ars Technica, The Verge, Wired, MIT Tech
    Review, VentureBeat, Product Hunt (public RSS/Atom)

Deduplication: stores seen IDs in state/newsprove_seen.json.
  HN items use their numeric ID; RSS items use feed_name + entry link hash.

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

INTERVAL = int(os.getenv("NEWSPROVE_INTERVAL", "290"))
DAILY_CAP = int(os.getenv("NEWSPROVE_DAILY_CAP", "500"))

HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_NEW_URL = "https://hacker-news.firebaseio.com/v0/newstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"

FETCH_TOP_N = 200  # consider this many top/new stories per cycle

# ── RSS Feeds ────────────────────────────────────────────────────────────────

RSS_FEEDS = [
    ("TechCrunch",        "https://techcrunch.com/feed/"),
    ("ArsTechnica",       "https://feeds.arstechnica.com/arstechnica/index"),
    ("TheVerge",          "https://www.theverge.com/rss/index.xml"),
    ("Wired",             "https://www.wired.com/feed/rss"),
    ("MITTechReview",     "https://www.technologyreview.com/feed/"),
    ("VentureBeat",       "https://venturebeat.com/feed/"),
    ("ProductHunt",       "https://www.producthunt.com/feed"),
    ("HackerNoon",        "https://hackernoon.com/feed"),
    ("TechMeme",          "https://www.techmeme.com/feed.xml"),
    ("TheNextWeb",        "https://thenextweb.com/feed"),
]

RSS_USER_AGENT = "ProvBot/1.0 (Numbers Protocol Reference Agent; +https://numbersprotocol.io)"


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
            title = (item.findtext("title") or "").strip()[:200]
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            author = (item.findtext("author") or item.findtext("{http://purl.org/dc/elements/1.1/}creator") or "").strip()
            desc = _strip_html(item.findtext("description") or "")[:300]
            if link:
                entries.append({
                    "title": title,
                    "link": link,
                    "published": pub_date,
                    "author": author,
                    "description": desc,
                })
        return entries

    # Try Atom (feed/entry)
    atom_entries = root.findall("atom:entry", ns) or root.findall("entry")
    for entry in atom_entries[:30]:
        title = (entry.findtext("atom:title", "", ns) or entry.findtext("title") or "").strip()[:200]
        link_el = entry.find("atom:link[@rel='alternate']", ns) or entry.find("atom:link", ns) or entry.find("link")
        link = ""
        if link_el is not None:
            link = link_el.get("href", "").strip()
            if not link:
                link = (link_el.text or "").strip()
        published = (entry.findtext("atom:published", "", ns) or entry.findtext("atom:updated", "", ns) or
                     entry.findtext("published") or entry.findtext("updated") or "").strip()
        author_el = entry.find("atom:author", ns) or entry.find("author")
        author = ""
        if author_el is not None:
            author = (author_el.findtext("atom:name", "", ns) or author_el.findtext("name") or author_el.text or "").strip()
        desc = _strip_html(entry.findtext("atom:summary", "", ns) or entry.findtext("summary") or
                          entry.findtext("atom:content", "", ns) or entry.findtext("content") or "")[:300]
        if link:
            entries.append({
                "title": title,
                "link": link,
                "published": published,
                "author": author,
                "description": desc,
            })

    return entries


def fetch_rss_entries(feed_name: str, feed_url: str) -> list[dict]:
    """Fetch and parse an RSS/Atom feed, returning entry dicts."""
    try:
        resp = httpx.get(
            feed_url,
            timeout=15,
            headers={"User-Agent": RSS_USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"},
            follow_redirects=True,
        )
        resp.raise_for_status()
        return _parse_rss_entries(resp.text, feed_name)
    except Exception as exc:
        logger.debug(f"RSS fetch failed for {feed_name}: {exc}")
        return []


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_hn_cycle(capture, seen: set, cap: DailyCap) -> int:
    """Fetch unseen HN stories and register them."""
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

        ts = datetime.fromtimestamp(
            item.get("time", time.time()), tz=timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        record = {
            "agent": AGENT_ID,
            "source": "Hacker News",
            "hn_id": item_id,
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "author": item.get("by", ""),
            "score": item.get("score", 0),
            "comments": item.get("descendants", 0),
            "published_at": ts,
            "registered_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "feed": feed,
        }

        tmp = write_json_tmp(record, prefix="newsprove_hn_")
        try:
            caption = (
                f"{AGENT_ID} | "
                f"HN#{item_id} | "
                f"{item.get('title', '')[:80]} | "
                f"{ts}"
            )
            nid = register_with_retry(capture, tmp, caption, AGENT_SHORT)
            if nid:
                seen.add(str(item_id))
                cap.record()
                registered += 1
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

        time.sleep(2)

    return registered


def run_rss_cycle(capture, seen: set, cap: DailyCap) -> int:
    """Fetch unseen RSS entries and register them."""
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

            record = {
                "agent": AGENT_ID,
                "source": f"RSS/{feed_name}",
                "feed": feed_name,
                "title": entry.get("title", ""),
                "url": link,
                "author": entry.get("author", ""),
                "description": entry.get("description", ""),
                "published_at": entry.get("published", ""),
                "registered_at": ts_now,
            }

            tmp = write_json_tmp(record, prefix="newsprove_rss_")
            try:
                caption = (
                    f"{AGENT_ID} | "
                    f"{feed_name} | "
                    f"{entry.get('title', '')[:70]} | "
                    f"{entry.get('published', '')[:10]}"
                )
                nid = register_with_retry(capture, tmp, caption, AGENT_SHORT)
                if nid:
                    seen.add(dedup_key)
                    cap.record()
                    registered += 1
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)

            time.sleep(2)

        time.sleep(2)

    return registered


def run_cycle(capture, seen: set, cap: DailyCap) -> int:
    """Run both HN and RSS cycles."""
    total = 0
    total += run_hn_cycle(capture, seen, cap)
    total += run_rss_cycle(capture, seen, cap)
    return total


def main():
    setup_rotating_log(AGENT_SHORT)
    logger.info(
        f"NewsProve starting | interval={INTERVAL}s | daily_cap={DAILY_CAP}"
    )
    slack_alert("[NewsProve] started", level="INFO")

    capture = get_capture()
    cap = DailyCap(DAILY_CAP)
    seen = load_seen_ids(AGENT_SHORT)

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
