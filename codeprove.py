"""
codeprove.py — CodeProve Reference Agent  (#7)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Monitors the Numbers Protocol GitHub organisation for push events and
registers each individual changed file within a commit as a provenance
record on Numbers Mainnet.

Target:  50 transactions/day  (~1 every 1728 seconds)
Cost:    $0/day  (GitHub public Events API, no auth needed for 60 req/hr;
                  GITHUB_TOKEN gives 5000 req/hr and is recommended)

What it registers:
  For each new push event → for each commit in the push → for each
  changed file in the commit, register a JSON record containing:
    repo, branch, commit SHA, commit message, author, timestamp, file path

Deduplication: stored as "repo:sha:file" in state/codeprove_seen.json

Fallback: If GITHUB_ORG repos have low commit volume (< 50 files/day),
  extend monitoring to open-source AI repos (listed in EXTRA_REPOS).

Usage:
  python codeprove.py
"""

import logging
import os
import time
from datetime import datetime, timezone

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

AGENT_ID = "Numbers Protocol Reference Agent #7 (CodeProve)"
AGENT_SHORT = "codeprove"
logger = logging.getLogger(AGENT_SHORT)

INTERVAL = int(os.getenv("CODEPROVE_INTERVAL", "1728"))
DAILY_CAP = int(os.getenv("CODEPROVE_DAILY_CAP", "50"))
GITHUB_ORG = os.getenv("GITHUB_ORG", "numbersprotocol")
GITHUB_TOKEN = os.environ.get("Github_PAT") or os.environ.get("GITHUB_TOKEN")

# Additional high-activity public repos to monitor if org volume is low
EXTRA_REPOS = [
    "langchain-ai/langchain",
    "huggingface/transformers",
    "openai/openai-python",
    "anthropics/anthropic-sdk-python",
    "vercel/next.js",
    "facebook/react",
    "microsoft/vscode",
]

# Event types to register (beyond just PushEvent)
REGISTERABLE_EVENTS = {"PushEvent", "PullRequestEvent", "IssuesEvent", "ReleaseEvent"}


# ── GitHub API helpers ────────────────────────────────────────────────────────

def _gh_headers() -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ProvBot/1.0 (Numbers Protocol Reference Agent)",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def fetch_org_repos() -> list[str]:
    """Return list of 'owner/repo' strings for the configured org."""
    repos = []
    page = 1
    while True:
        url = f"https://api.github.com/orgs/{GITHUB_ORG}/repos?per_page=100&page={page}&type=public"
        try:
            resp = httpx.get(url, headers=_gh_headers(), timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            for r in data:
                if not r.get("archived") and not r.get("fork"):
                    repos.append(r["full_name"])
            if len(data) < 100:
                break
            page += 1
        except Exception as exc:
            logger.warning(f"fetch_org_repos page={page} failed: {exc}")
            break
    return repos


def fetch_repo_events(repo: str, since_id: int = 0) -> list[dict]:
    """Fetch recent registerable events for a repo newer than since_id."""
    url = f"https://api.github.com/repos/{repo}/events?per_page=30"
    try:
        resp = httpx.get(url, headers=_gh_headers(), timeout=15)
        resp.raise_for_status()
        events = resp.json()
        return [
            e for e in events
            if e.get("type") in REGISTERABLE_EVENTS and int(e.get("id", 0)) > since_id
        ]
    except Exception as exc:
        logger.debug(f"fetch_repo_events({repo}) failed: {exc}")
        return []


def fetch_commit_files(repo: str, sha: str) -> list[str]:
    """Return list of changed file paths in a commit."""
    url = f"https://api.github.com/repos/{repo}/commits/{sha}"
    try:
        resp = httpx.get(url, headers=_gh_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return [f["filename"] for f in data.get("files", [])]
    except Exception as exc:
        logger.debug(f"fetch_commit_files({repo}, {sha[:8]}) failed: {exc}")
        return []


# ── State helpers ─────────────────────────────────────────────────────────────

def _last_event_id_key(repo: str) -> str:
    return f"last_event:{repo}"


def load_last_event_ids(seen: set) -> dict:
    """Extract last-seen event IDs from the seen set."""
    ids = {}
    for item in seen:
        if item.startswith("last_event:"):
            repo = item.split("last_event:", 1)[1].rsplit(":", 1)[0]
            try:
                event_id = int(item.rsplit(":", 1)[1])
                ids[repo] = event_id
            except ValueError:
                pass
    return ids


# ── Main loop ─────────────────────────────────────────────────────────────────

def _register_non_push_event(event, repo, capture, seen, cap, ts_now) -> int:
    """Register a single PR, Issue, or Release event."""
    event_type = event.get("type", "")
    event_id = event.get("id", "0")
    dedup_key = f"{repo}:event:{event_id}"
    if dedup_key in seen:
        return 0

    payload = event.get("payload", {})
    actor = event.get("actor", {}).get("login", "unknown")
    event_ts = event.get("created_at", ts_now)

    if event_type == "PullRequestEvent":
        pr = payload.get("pull_request", {})
        action = payload.get("action", "")
        # Only register merged or opened PRs
        if action not in ("opened", "closed"):
            return 0
        if action == "closed" and not pr.get("merged"):
            return 0
        record = {
            "agent": AGENT_ID,
            "source": "GitHub",
            "event_type": "pull_request",
            "action": "merged" if pr.get("merged") else action,
            "repo": repo,
            "pr_number": pr.get("number"),
            "title": (pr.get("title") or "")[:200],
            "author": pr.get("user", {}).get("login", actor),
            "url": pr.get("html_url"),
            "event_at": event_ts,
            "registered_at": ts_now,
        }
        label = f"PR #{pr.get('number')} {'merged' if pr.get('merged') else action}"
    elif event_type == "IssuesEvent":
        issue = payload.get("issue", {})
        action = payload.get("action", "")
        if action not in ("opened", "closed"):
            return 0
        record = {
            "agent": AGENT_ID,
            "source": "GitHub",
            "event_type": "issue",
            "action": action,
            "repo": repo,
            "issue_number": issue.get("number"),
            "title": (issue.get("title") or "")[:200],
            "author": issue.get("user", {}).get("login", actor),
            "url": issue.get("html_url"),
            "event_at": event_ts,
            "registered_at": ts_now,
        }
        label = f"Issue #{issue.get('number')} {action}"
    elif event_type == "ReleaseEvent":
        release = payload.get("release", {})
        record = {
            "agent": AGENT_ID,
            "source": "GitHub",
            "event_type": "release",
            "repo": repo,
            "tag": release.get("tag_name"),
            "name": (release.get("name") or "")[:200],
            "author": release.get("author", {}).get("login", actor),
            "url": release.get("html_url"),
            "event_at": event_ts,
            "registered_at": ts_now,
        }
        label = f"Release {release.get('tag_name')}"
    else:
        return 0

    tmp = write_json_tmp(record, prefix="codeprove_ev_")
    try:
        caption = f"{AGENT_ID} | {repo} | {label} | {event_ts[:10]}"
        nid = register_with_retry(capture, tmp, caption, AGENT_SHORT)
        if nid:
            seen.add(dedup_key)
            cap.record()
            return 1
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return 0


def run_cycle(capture, seen: set, cap: DailyCap, repos: list[str]) -> int:
    registered = 0
    last_event_ids = load_last_event_ids(seen)
    ts_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for repo in repos:
        if not cap.check():
            break

        since_id = last_event_ids.get(repo, 0)
        events = fetch_repo_events(repo, since_id)
        if not events:
            continue

        new_last_id = since_id
        for event in events:
            event_id = int(event.get("id", 0))
            new_last_id = max(new_last_id, event_id)
            event_type = event.get("type", "")

            # Handle non-push events (PR, Issue, Release) as single records
            if event_type != "PushEvent":
                r = _register_non_push_event(event, repo, capture, seen, cap, ts_now)
                registered += r
                if r:
                    time.sleep(2)
                continue

            # Handle PushEvent — register individual files
            payload = event.get("payload", {})
            commits = payload.get("commits", [])
            branch = payload.get("ref", "").replace("refs/heads/", "")
            pusher = event.get("actor", {}).get("login", "unknown")
            event_ts = event.get("created_at", ts_now)

            for commit in commits:
                if not cap.check():
                    break
                sha = commit.get("sha", "")
                if not sha:
                    continue

                # Fetch changed files for this commit
                files = fetch_commit_files(repo, sha)
                time.sleep(1)  # rate-limit file fetches

                for file_path in files:
                    if not cap.check():
                        break
                    dedup_key = f"{repo}:{sha[:12]}:{file_path}"
                    if dedup_key in seen:
                        continue

                    record = {
                        "agent": AGENT_ID,
                        "source": "GitHub",
                        "event_type": "push_file_change",
                        "repo": repo,
                        "branch": branch,
                        "commit_sha": sha,
                        "commit_sha_short": sha[:8],
                        "commit_message": commit.get("message", "")[:200],
                        "author": commit.get("author", {}).get("name", pusher),
                        "file_path": file_path,
                        "github_url": f"https://github.com/{repo}/blob/{sha}/{file_path}",
                        "pushed_by": pusher,
                        "pushed_at": event_ts,
                        "registered_at": ts_now,
                    }

                    tmp = write_json_tmp(record, prefix="codeprove_")
                    try:
                        caption = (
                            f"{AGENT_ID} | "
                            f"{repo} | "
                            f"{sha[:8]} | "
                            f"{file_path[-60:]} | "
                            f"{event_ts[:10]}"
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

        # Update last seen event ID for this repo
        old_key = f"last_event:{repo}:{since_id}"
        new_key = f"last_event:{repo}:{new_last_id}"
        seen.discard(old_key)
        seen.add(new_key)

        time.sleep(2)

    return registered


def main():
    logger.info(
        f"CodeProve starting | interval={INTERVAL}s | daily_cap={DAILY_CAP} | org={GITHUB_ORG}"
    )
    slack_alert(f"[CodeProve] started (org={GITHUB_ORG})", level="INFO")

    capture = get_capture()
    cap = DailyCap(DAILY_CAP)
    seen = load_seen_ids(AGENT_SHORT)

    # Discover repos once at startup, refresh every 24h
    repos = fetch_org_repos()
    if not repos:
        logger.warning(f"No repos found for org {GITHUB_ORG!r}; using EXTRA_REPOS fallback")
        repos = EXTRA_REPOS
    else:
        # Append extra repos to boost volume if org is small
        repos += EXTRA_REPOS

    logger.info(f"Monitoring {len(repos)} repos: {repos}")
    last_repo_refresh = time.time()

    while True:
        # Refresh repo list every 24 hours
        if time.time() - last_repo_refresh > 86_400:
            fresh = fetch_org_repos()
            if fresh:
                repos = fresh + EXTRA_REPOS
                last_repo_refresh = time.time()

        if cap.check():
            n = run_cycle(capture, seen, cap, repos)
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
