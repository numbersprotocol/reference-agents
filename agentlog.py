"""
agentlog.py — AgentLog Reference Agent  (#3)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Runs LLM inference tasks and registers each (input, output) pair as an
on-chain AI audit trail — demonstrating that agent reasoning can be
timestamped and made verifiable on Numbers Mainnet.

Target:  200 transactions/day  (~1 every 430 seconds)
Cost:    $0/day in template mode  |  ~$0.05/day with Groq free tier

Modes (AGENTLOG_MODE env var):
  template  — deterministic analysis of public arXiv data, no API key (default)
  groq      — LLM calls via Groq API (free tier), requires GROQ_API_KEY

Usage:
  python agentlog.py
"""

import json
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

AGENT_ID = "Numbers Protocol Reference Agent #3 (AgentLog)"
AGENT_SHORT = "agentlog"
logger = logging.getLogger(AGENT_SHORT)

INTERVAL = int(os.getenv("AGENTLOG_INTERVAL", "430"))
DAILY_CAP = int(os.getenv("AGENTLOG_DAILY_CAP", "200"))
MODE = os.getenv("AGENTLOG_MODE", "template").lower()

ARXIV_FEED = (
    "https://export.arxiv.org/api/query"
    "?search_query=cat:cs.AI+OR+cat:cs.LG"
    "&sortBy=submittedDate&sortOrder=descending&max_results=50"
)
ARXIV_NS = "http://www.w3.org/2005/Atom"


# ── arXiv fetcher ─────────────────────────────────────────────────────────────

def fetch_arxiv_papers() -> list[dict]:
    resp = httpx.get(ARXIV_FEED, timeout=20)
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    papers = []
    for entry in root.findall(f"{{{ARXIV_NS}}}entry"):
        arxiv_id = (entry.findtext(f"{{{ARXIV_NS}}}id") or "").split("/abs/")[-1].strip()
        title = (entry.findtext(f"{{{ARXIV_NS}}}title") or "").replace("\n", " ").strip()
        abstract = (entry.findtext(f"{{{ARXIV_NS}}}summary") or "").replace("\n", " ").strip()
        published = entry.findtext(f"{{{ARXIV_NS}}}published") or ""
        authors = [
            a.findtext(f"{{{ARXIV_NS}}}name") or ""
            for a in entry.findall(f"{{{ARXIV_NS}}}author")
        ]
        if arxiv_id and title:
            papers.append({
                "arxiv_id": arxiv_id,
                "title": title,
                "abstract": abstract[:600],
                "published": published,
                "authors": authors[:5],
            })
    return papers


# ── Template mode analysis ────────────────────────────────────────────────────

def _template_analysis(paper: dict) -> dict:
    """
    Rule-based analysis that extracts key claims from an arXiv abstract.
    Produces a structured audit log without any LLM call.
    """
    abstract = paper["abstract"]
    task = f"Summarise key contributions of: {paper['title']}"

    # Simple keyword extraction
    keywords = []
    for kw in ["transformer", "diffusion", "reinforcement", "graph", "multimodal",
               "zero-shot", "few-shot", "fine-tuning", "RLHF", "alignment",
               "benchmark", "efficiency", "reasoning", "agent", "foundation model"]:
        if kw.lower() in abstract.lower():
            keywords.append(kw)

    sentences = [s.strip() for s in abstract.split(". ") if len(s.strip()) > 40]
    summary = sentences[0] if sentences else abstract[:200]

    return {
        "task": task,
        "response": f"Key contribution: {summary}. Topics: {', '.join(keywords) or 'general ML'}.",
        "method": "template",
        "tokens_in": len(task.split()),
        "tokens_out": len(summary.split()),
    }


# ── Groq mode analysis ────────────────────────────────────────────────────────

def _groq_analysis(paper: dict) -> dict:
    """Call Groq API (free tier). Requires GROQ_API_KEY env var."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY not set")

    task = (
        f"In one sentence, state the main contribution of this AI paper. "
        f"Title: {paper['title']}. Abstract: {paper['abstract'][:400]}"
    )

    resp = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": task}],
            "max_tokens": 120,
            "temperature": 0.3,
        },
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    response_text = data["choices"][0]["message"]["content"].strip()
    usage = data.get("usage", {})

    return {
        "task": task,
        "response": response_text,
        "method": "groq/llama-3.1-8b-instant",
        "tokens_in": usage.get("prompt_tokens", 0),
        "tokens_out": usage.get("completion_tokens", 0),
    }


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_cycle(capture, seen: set, cap: DailyCap) -> int:
    registered = 0
    try:
        papers = fetch_arxiv_papers()
    except Exception as exc:
        logger.error(f"fetch_arxiv_papers failed: {exc}")
        return 0

    for paper in papers:
        if not cap.check():
            break
        arxiv_id = paper["arxiv_id"]
        if arxiv_id in seen:
            continue

        try:
            analysis = _groq_analysis(paper) if MODE == "groq" else _template_analysis(paper)
        except Exception as exc:
            logger.warning(f"analysis failed for {arxiv_id}: {exc}")
            # Fallback to template if Groq fails
            analysis = _template_analysis(paper)

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        record = {
            "agent": AGENT_ID,
            "arxiv_id": arxiv_id,
            "paper_title": paper["title"],
            "paper_authors": paper["authors"],
            "paper_published": paper["published"],
            "analysis_task": analysis["task"],
            "analysis_response": analysis["response"],
            "analysis_method": analysis["method"],
            "tokens_in": analysis["tokens_in"],
            "tokens_out": analysis["tokens_out"],
            "logged_at": ts,
        }

        tmp = write_json_tmp(record, prefix="agentlog_")
        try:
            caption = (
                f"{AGENT_ID} | "
                f"arXiv:{arxiv_id} | "
                f"{shorten(paper['title'], 60)} | "
                f"{ts}"
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

    return registered


def main():
    logger.info(
        f"AgentLog starting | mode={MODE} | interval={INTERVAL}s | daily_cap={DAILY_CAP}"
    )
    slack_alert(f"[AgentLog] started (mode={MODE})", level="INFO")

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
