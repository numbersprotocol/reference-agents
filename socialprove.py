"""
socialprove.py — SocialProve Reference Agent  (#5)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Monitors AI/ML communities and registers each post as a provenance
record on Numbers Mainnet. For Reddit self-posts the body text is
captured and SHA-256 hashed — preserving content that moderators
may later delete or edit.

Primary source:  Reddit — r/MachineLearning, r/LocalLLaMA, r/artificial
                 via OAuth2 client_credentials (REDDIT_CLIENT_ID +
                 REDDIT_CLIENT_SECRET from Omni Cloud Credentials).
Fallback source: Mastodon (mastodon.social) + Dev.to, used automatically
                 if Reddit credentials are absent or OAuth fails.

Target:  200 transactions/day  (~1 every 430 seconds)
Cost:    $0/day

Usage:
  python socialprove.py
"""

import base64
import hashlib
import logging
import os
import re
import time
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

AGENT_ID = "Numbers Protocol Reference Agent #5 (SocialProve)"
AGENT_SHORT = "socialprove"
logger = logging.getLogger(AGENT_SHORT)

INTERVAL    = int(os.getenv("SOCIALPROVE_INTERVAL", "430"))
DAILY_CAP   = int(os.getenv("SOCIALPROVE_DAILY_CAP", "200"))

USER_AGENT  = "ProvBot/1.0 (Numbers Protocol Reference Agent; +https://numbersprotocol.io)"

SUBREDDITS       = ["MachineLearning", "LocalLLaMA", "artificial", "StableDiffusion", "ChatGPT", "singularity"]
POSTS_PER_SUB    = 25

MASTODON_TAGS    = ["MachineLearning", "LLM", "AIagent", "generativeai", "deeplearning"]
DEVTO_TAGS       = ["machinelearning", "ai", "llm", "deeplearning"]


# ── Reddit OAuth ──────────────────────────────────────────────────────────────

def _reddit_token() -> str | None:
    cid    = os.environ.get("REDDIT_CLIENT_ID")
    secret = os.environ.get("REDDIT_CLIENT_SECRET")
    if not cid or not secret:
        return None
    try:
        creds = base64.b64encode(f"{cid}:{secret}".encode()).decode()
        resp  = httpx.post(
            "https://www.reddit.com/api/v1/access_token",
            headers={"Authorization": f"Basic {creds}", "User-Agent": USER_AGENT},
            data={"grant_type": "client_credentials"},
            timeout=10,
        )
        resp.raise_for_status()
        token = resp.json().get("access_token")
        if token:
            logger.info("Reddit OAuth token obtained")
        return token
    except Exception as exc:
        logger.warning(f"Reddit OAuth failed: {exc}")
        return None


def _reddit_posts(subreddit: str, token: str) -> list[dict]:
    resp = httpx.get(
        f"https://oauth.reddit.com/r/{subreddit}/new.json?limit={POSTS_PER_SUB}",
        headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT},
        timeout=15,
    )
    resp.raise_for_status()
    return [c["data"] for c in resp.json().get("data", {}).get("children", []) if c.get("data")]


def run_reddit(capture, seen: set, cap: DailyCap, token: str) -> int:
    registered = 0
    for subreddit in SUBREDDITS:
        if not cap.check():
            break
        try:
            posts = _reddit_posts(subreddit, token)
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code == 401:
                logger.warning("Reddit token expired — will refresh next cycle")
                return registered   # signal caller to refresh
            logger.error(f"r/{subreddit}: HTTP {code}")
            continue
        except Exception as exc:
            logger.error(f"r/{subreddit}: {exc}")
            continue

        for post in posts:
            if not cap.check():
                break
            post_id   = post.get("id", "")
            dedup_key = f"reddit:{subreddit}:{post_id}"
            if dedup_key in seen or not post_id or not post.get("title"):
                seen.add(dedup_key)
                continue

            ts_post = datetime.fromtimestamp(
                post.get("created_utc", 0), tz=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            ts_now  = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            # Capture body text for self-posts (text content the mod may delete)
            is_self = post.get("is_self", False)
            raw_selftext = post.get("selftext", "") if is_self else ""
            # Normalize whitespace; skip placeholder strings Reddit injects
            if raw_selftext in ("[deleted]", "[removed]", ""):
                raw_selftext = ""
            selftext_content = " ".join(raw_selftext.split())[:1000] if raw_selftext else None
            selftext_hash = (
                "sha256:" + hashlib.sha256(raw_selftext.encode("utf-8")).hexdigest()
                if raw_selftext else None
            )

            record = {
                "agent":           AGENT_ID,
                "source":          "Reddit",
                "subreddit":       subreddit,
                "post_id":         post_id,
                "title":           post.get("title", "")[:200],
                "url":             post.get("url", ""),
                "permalink":       f"https://reddit.com{post.get('permalink', '')}",
                "author":          post.get("author", "[deleted]"),
                "score":           post.get("score", 0),
                "num_comments":    post.get("num_comments", 0),
                "flair":           post.get("link_flair_text"),
                "is_self":         is_self,
                "selftext":        selftext_content,
                "selftext_hash":   selftext_hash,
                "posted_at":       ts_post,
                "registered_at":   ts_now,
            }
            tmp = write_json_tmp(record, prefix="socialprove_reddit_")
            try:
                caption = (
                    f"{AGENT_ID} | r/{subreddit} | "
                    f"{post.get('title','')[:70]} | {ts_post}"
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

        time.sleep(3)
    return registered


# ── Mastodon fallback ─────────────────────────────────────────────────────────

def _mastodon_posts(tag: str) -> list[dict]:
    resp = httpx.get(
        f"https://mastodon.social/api/v1/timelines/tag/{tag}",
        params={"limit": 30},
        headers={"Accept": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _devto_articles(tag: str) -> list[dict]:
    resp = httpx.get(
        "https://dev.to/api/articles",
        params={"tag": tag, "per_page": 20, "state": "rising"},
        headers={"Accept": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def run_fallback(capture, seen: set, cap: DailyCap) -> int:
    registered = 0
    ts_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for tag in MASTODON_TAGS:
        if not cap.check():
            break
        try:
            posts = _mastodon_posts(tag)
        except Exception as exc:
            logger.debug(f"Mastodon tag={tag}: {exc}")
            continue
        for post in posts:
            if not cap.check():
                break
            post_id   = post.get("id", "")
            dedup_key = f"mastodon:{post_id}"
            if dedup_key in seen or not post_id or post.get("reblog"):
                seen.add(dedup_key)
                continue
            content = re.sub(r"<[^>]+>", "", post.get("content", "")).strip()[:400]
            acct    = post.get("account", {})
            record  = {
                "agent":        AGENT_ID,
                "source":       "Mastodon",
                "instance":     "mastodon.social",
                "tag":          tag,
                "post_id":      post_id,
                "url":          post.get("url", ""),
                "author":       f"@{acct.get('acct','')}@mastodon.social",
                "content":      content,
                "posted_at":    post.get("created_at", ""),
                "registered_at": ts_now,
            }
            tmp = write_json_tmp(record, prefix="socialprove_masto_")
            try:
                caption = (
                    f"{AGENT_ID} | Mastodon | #{tag} | "
                    f"@{acct.get('acct','')} | {post.get('created_at','')[:10]}"
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
        time.sleep(3)

    for tag in DEVTO_TAGS:
        if not cap.check():
            break
        try:
            articles = _devto_articles(tag)
        except Exception as exc:
            logger.debug(f"Dev.to tag={tag}: {exc}")
            continue
        for art in articles:
            if not cap.check():
                break
            art_id    = str(art.get("id", ""))
            dedup_key = f"devto:{art_id}"
            if dedup_key in seen or not art_id:
                continue
            record = {
                "agent":         AGENT_ID,
                "source":        "Dev.to",
                "tag":           tag,
                "article_id":    art_id,
                "title":         art.get("title", "")[:200],
                "url":           art.get("url", ""),
                "author":        art.get("user", {}).get("name", ""),
                "description":   (art.get("description") or "")[:300],
                "reactions":     art.get("positive_reactions_count", 0),
                "published_at":  art.get("published_at", ""),
                "registered_at": ts_now,
            }
            tmp = write_json_tmp(record, prefix="socialprove_devto_")
            try:
                caption = (
                    f"{AGENT_ID} | Dev.to | #{tag} | "
                    f"{record['title'][:60]} | {record['published_at'][:10]}"
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
        time.sleep(3)

    return registered


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    setup_rotating_log(AGENT_SHORT)
    reddit_token = _reddit_token()
    source_label = "Reddit OAuth" if reddit_token else "Mastodon+Dev.to (fallback)"
    logger.info(f"SocialProve starting | source={source_label} | interval={INTERVAL}s | daily_cap={DAILY_CAP}")
    slack_alert(f"[SocialProve] started ({source_label})", level="INFO")

    capture = get_capture()
    cap     = DailyCap(DAILY_CAP)
    seen    = load_seen_ids(AGENT_SHORT)

    while True:
        if cap.check():
            if reddit_token:
                n = run_reddit(capture, seen, cap, reddit_token)
                # Refresh token if it expired mid-cycle
                if n == 0 and cap.check():
                    logger.info("Refreshing Reddit OAuth token")
                    reddit_token = _reddit_token()
                    if not reddit_token:
                        logger.warning("Reddit token refresh failed — falling back to Mastodon+Dev.to")
                        n = run_fallback(capture, seen, cap)
            else:
                n = run_fallback(capture, seen, cap)

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
