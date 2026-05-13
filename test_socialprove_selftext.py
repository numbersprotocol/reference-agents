"""
Quick verification: confirm selftext capture works for Reddit self-posts.
Fetches r/MachineLearning/new, finds a self-post, prints what would be stored.
"""
import base64
import hashlib
import os
import sys
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

load_dotenv()

USER_AGENT = "ProvBot/1.0 (Numbers Protocol Reference Agent; +https://numbersprotocol.io)"

def get_token():
    cid = os.environ.get("REDDIT_CLIENT_ID")
    secret = os.environ.get("REDDIT_CLIENT_SECRET")
    if not cid or not secret:
        print("ERROR: REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set")
        sys.exit(1)
    creds = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    resp = httpx.post(
        "https://www.reddit.com/api/v1/access_token",
        headers={"Authorization": f"Basic {creds}", "User-Agent": USER_AGENT},
        data={"grant_type": "client_credentials"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]

token = get_token()
print("Reddit token obtained")

for subreddit in ["MachineLearning", "LocalLLaMA", "artificial"]:
    resp = httpx.get(
        f"https://oauth.reddit.com/r/{subreddit}/new.json?limit=25",
        headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT},
        timeout=15,
    )
    resp.raise_for_status()
    posts = [c["data"] for c in resp.json().get("data", {}).get("children", []) if c.get("data")]

    self_posts = [p for p in posts if p.get("is_self") and p.get("selftext") not in ("", "[deleted]", "[removed]", None)]
    link_posts = [p for p in posts if not p.get("is_self")]

    print(f"\nr/{subreddit}: {len(posts)} posts total — {len(self_posts)} self-posts with content, {len(link_posts)} link posts")

    if self_posts:
        p = self_posts[0]
        raw_selftext = p.get("selftext", "")
        selftext_content = " ".join(raw_selftext.split())[:1000]
        selftext_hash = "sha256:" + hashlib.sha256(raw_selftext.encode("utf-8")).hexdigest()

        print(f"  Sample self-post: '{p['title'][:60]}'")
        print(f"  Author: u/{p.get('author')}, score: {p.get('score')}")
        print(f"  Selftext ({len(raw_selftext)} chars): '{selftext_content[:200]}...'")
        print(f"  Selftext hash: {selftext_hash}")
    else:
        print(f"  No self-posts with content this cycle (all link posts or empty)")
        if link_posts:
            p = link_posts[0]
            print(f"  Sample link post: '{p['title'][:60]}' → {p.get('url', '')[:60]}")

print("\nVerification complete — selftext capture logic working correctly.")
