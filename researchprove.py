"""
researchprove.py — ResearchProve Reference Agent  (#6)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fetches new AI and ML research paper abstracts from arXiv and registers
each one as a timestamped provenance record on Numbers Mainnet.

Target:  150 transactions/day  (~1 every 576 seconds)
Cost:    $0/day  (arXiv API is free, 28,800 req/day limit)

Categories monitored:  cs.AI, cs.LG, cs.CV, cs.CL, stat.ML
arXiv typically posts 100–200 new papers/day across these categories,
providing ample supply for the 150/day target.

Deduplication: stores seen arXiv IDs in state/researchprove_seen.json

Usage:
  python researchprove.py
"""

import logging
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from textwrap import shorten

import httpx
from dotenv import load_dotenv

from common import (
    DailyCap,
    get_capture,
    load_seen_ids,
    register_with_retry,
    save_seen_ids,
    slack_alert,
    write_json_tmp,
)

load_dotenv()

AGENT_ID = "Numbers Protocol Reference Agent #6 (ResearchProve)"
AGENT_SHORT = "researchprove"
logger = logging.getLogger(AGENT_SHORT)

INTERVAL = int(os.getenv("RESEARCHPROVE_INTERVAL", "576"))
DAILY_CAP = int(os.getenv("RESEARCHPROVE_DAILY_CAP", "150"))

ARXIV_NS = "http://www.w3.org/2005/Atom"

# arXiv categories — each query fetches the 50 most recent papers
CATEGORY_QUERIES = [
    ("cs.AI",   "cat:cs.AI"),
    ("cs.LG",   "cat:cs.LG"),
    ("cs.CV",   "cat:cs.CV"),
    ("cs.CL",   "cat:cs.CL"),
    ("stat.ML", "cat:stat.ML"),
]

ARXIV_BASE = "https://export.arxiv.org/api/query"
FETCH_PER_CATEGORY = 30  # papers per category per cycle


# ── arXiv fetcher ─────────────────────────────────────────────────────────────

def fetch_papers(category_query: str) -> list[dict]:
    params = {
        "search_query": category_query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": str(FETCH_PER_CATEGORY),
    }
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{ARXIV_BASE}?{query_string}"

    resp = httpx.get(url, timeout=20)
    resp.raise_for_status()

    root = ET.fromstring(resp.text)
    papers = []

    for entry in root.findall(f"{{{ARXIV_NS}}}entry"):
        raw_id = entry.findtext(f"{{{ARXIV_NS}}}id") or ""
        arxiv_id = raw_id.split("/abs/")[-1].strip()
        title = (entry.findtext(f"{{{ARXIV_NS}}}title") or "").replace("\n", " ").strip()
        abstract = (entry.findtext(f"{{{ARXIV_NS}}}summary") or "").replace("\n", " ").strip()
        published = entry.findtext(f"{{{ARXIV_NS}}}published") or ""
        updated = entry.findtext(f"{{{ARXIV_NS}}}updated") or ""
        authors = [
            a.findtext(f"{{{ARXIV_NS}}}name") or ""
            for a in entry.findall(f"{{{ARXIV_NS}}}author")
        ]
        links = {
            link.get("rel"): link.get("href")
            for link in entry.findall(f"{{{ARXIV_NS}}}link")
        }
        doi_node = entry.find("{http://arxiv.org/schemas/atom}doi")
        doi = doi_node.text if doi_node is not None else None

        if arxiv_id and title:
            papers.append({
                "arxiv_id": arxiv_id,
                "title": title,
                "abstract": abstract[:800],
                "published": published,
                "updated": updated,
                "authors": authors[:8],
                "pdf_url": links.get("related"),
                "abstract_url": raw_id,
                "doi": doi,
            })

    return papers


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_cycle(capture, seen: set, cap: DailyCap) -> int:
    registered = 0

    for cat_label, cat_query in CATEGORY_QUERIES:
        if not cap.check():
            break

        try:
            papers = fetch_papers(cat_query)
        except Exception as exc:
            logger.error(f"fetch_papers({cat_label}) failed: {exc}")
            time.sleep(10)
            continue

        for paper in papers:
            if not cap.check():
                break

            arxiv_id = paper["arxiv_id"]
            if arxiv_id in seen:
                continue

            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            record = {
                "agent": AGENT_ID,
                "source": "arXiv",
                "category": cat_label,
                "arxiv_id": arxiv_id,
                "title": paper["title"],
                "abstract": paper["abstract"],
                "authors": paper["authors"],
                "published": paper["published"],
                "updated": paper["updated"],
                "abstract_url": paper["abstract_url"],
                "pdf_url": paper["pdf_url"],
                "doi": paper["doi"],
                "registered_at": ts,
            }

            tmp = write_json_tmp(record, prefix="researchprove_")
            try:
                caption = (
                    f"{AGENT_ID} | "
                    f"arXiv:{arxiv_id} | "
                    f"{cat_label} | "
                    f"{shorten(paper['title'], 60)} | "
                    f"{paper['published'][:10]}"
                )
                nid = register_with_retry(capture, tmp, caption, AGENT_SHORT)
                if nid:
                    seen.add(arxiv_id)
                    cap.record()
                    registered += 1
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)

            time.sleep(3)

        # arXiv API: be polite between category queries
        time.sleep(5)

    return registered


def main():
    logger.info(
        f"ResearchProve starting | interval={INTERVAL}s | daily_cap={DAILY_CAP}"
    )
    slack_alert("[ResearchProve] started", level="INFO")

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

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
