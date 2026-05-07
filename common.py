"""
common.py — Shared utilities for Numbers Protocol Reference Agents

Provides:
  - Capture SDK client factory
  - File registration with retry + logging
  - Deduplication state management (JSON files)
  - Slack alerting (optional)
  - Daily rate cap enforcement
  - Temp file helpers
"""

import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────────────

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s  %(levelname)-7s  [%(name)s]  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)


# ── Capture client ────────────────────────────────────────────────────────────

def get_capture():
    """Return an initialised Capture client. Raises if no token is found.

    Checks env vars in order:
      1. Capture_Auth_Token  (Omni Cloud Credentials name)
      2. CAPTURE_TOKEN       (generic / .env name)
    """
    from numbersprotocol_capture import Capture  # lazy import for test isolation
    token = os.environ.get("Capture_Auth_Token") or os.environ.get("CAPTURE_TOKEN")
    if not token:
        raise EnvironmentError(
            "No Capture token found. Set Capture_Auth_Token (Omni Cloud Credentials) "
            "or CAPTURE_TOKEN in .env. Free token at https://docs.captureapp.xyz"
        )
    return Capture(token=token)


def get_admin_headers() -> dict:
    """Return HTTP headers with Django admin token authentication.

    Uses Capture_Token_Admin_Omni (Omni Cloud Credentials) for elevated access
    to the Numbers Protocol Django REST Framework backend.

    Checks env vars in order:
      1. Capture_Token_Admin_Omni  (Omni Cloud Credentials name)
      2. CAPTURE_ADMIN_TOKEN       (generic / .env name)

    Returns an empty dict (no Authorization header) if no admin token is found,
    so callers fall back to unauthenticated access gracefully.
    """
    token = os.environ.get("Capture_Token_Admin_Omni") or os.environ.get("CAPTURE_ADMIN_TOKEN")
    if not token:
        return {}
    return {"Authorization": f"Token {token}"}


def admin_api_get(url: str, params: Optional[dict] = None, timeout: float = 30.0) -> dict:
    """Perform a GET request to the Numbers Protocol API with admin auth.

    Includes the Django admin token when available, falls back to
    unauthenticated if the token is not configured.

    Args:
        url:     Full URL to request (e.g. https://api.numbersprotocol.io/api/v3/assets/).
        params:  Optional query parameters dict.
        timeout: Request timeout in seconds.

    Returns:
        Parsed JSON response as a dict.

    Raises:
        httpx.HTTPStatusError: on non-2xx responses.
    """
    headers = {
        "User-Agent": "Numbers-RefAgents/1.0",
        **get_admin_headers(),
    }
    resp = httpx.get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


# ── Registration with retry ──────────────────────────────────────────────────

def register_with_retry(
    capture,
    file_path: str,
    caption: str,
    agent_name: str,
    max_retries: int = 3,
    base_delay: float = 5.0,
) -> Optional[str]:
    """
    Register a file on Numbers Mainnet via Capture SDK.

    Returns the NID (asset identifier) on success, None after exhausting retries.
    Each retry waits base_delay * attempt seconds (exponential-ish back-off).
    """
    logger = logging.getLogger(agent_name)
    for attempt in range(1, max_retries + 1):
        try:
            asset = capture.register(file_path, caption=caption)
            logger.info(f"registered  nid={asset.nid}  caption={caption[:60]!r}")
            return asset.nid
        except Exception as exc:
            logger.warning(f"attempt {attempt}/{max_retries} failed: {exc}")
            if attempt < max_retries:
                time.sleep(base_delay * attempt)

    slack_alert(
        f"[{agent_name}] registration failed after {max_retries} retries — "
        f"caption: {caption[:60]!r}",
        level="ERROR",
    )
    return None


# ── Slack alerting ────────────────────────────────────────────────────────────

def slack_alert(message: str, level: str = "INFO") -> None:
    """
    Post a message to a Slack Incoming Webhook.
    Silently no-ops if SLACK_WEBHOOK_URL is not configured.
    Never raises — agent operation must not be disrupted by alert failures.
    """
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        return
    emoji = {
        "INFO": ":information_source:",
        "WARN": ":warning:",
        "ERROR": ":rotating_light:",
    }.get(level, ":speech_balloon:")
    try:
        httpx.post(
            webhook,
            json={"text": f"{emoji}  *Ref-Agents*  {message}"},
            timeout=5.0,
        )
    except Exception:
        pass


# ── State / deduplication ─────────────────────────────────────────────────────

def _state_path(agent_name: str) -> Path:
    state_dir = Path(os.getenv("STATE_DIR", "./state"))
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / f"{agent_name}_seen.json"


def load_seen_ids(agent_name: str) -> set:
    """Load the set of already-processed IDs for this agent."""
    path = _state_path(agent_name)
    try:
        with open(path) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen_ids(agent_name: str, seen: set, max_size: int = 20_000) -> None:
    """
    Persist seen IDs to disk, trimming to max_size to bound file growth.
    Keeps the most-recently-added IDs (tail of the list).
    """
    ids = list(seen)
    if len(ids) > max_size:
        ids = ids[-max_size:]
    path = _state_path(agent_name)
    with open(path, "w") as f:
        json.dump(ids, f)


# ── Temp file helpers ─────────────────────────────────────────────────────────

def write_json_tmp(data: dict, prefix: str = "agent_") -> str:
    """
    Write a dict to a named temporary JSON file.
    Returns the file path. Caller is responsible for deletion.
    """
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        prefix=prefix,
        delete=False,
        encoding="utf-8",
    ) as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        return f.name


def write_text_tmp(text: str, prefix: str = "agent_", suffix: str = ".txt") -> str:
    """Write a string to a named temporary text file. Returns the file path."""
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=suffix,
        prefix=prefix,
        delete=False,
        encoding="utf-8",
    ) as f:
        f.write(text)
        return f.name


# ── Daily rate-cap helper ─────────────────────────────────────────────────────

class DailyCap:
    """
    Tracks registrations within a rolling 24-hour window.
    Call .check() before registering; call .record() after a successful registration.
    """

    def __init__(self, limit: int):
        self.limit = limit
        self._count = 0
        self._window_start = time.time()

    def _reset_if_needed(self):
        if time.time() - self._window_start >= 86_400:
            self._count = 0
            self._window_start = time.time()

    def check(self) -> bool:
        """Return True if there is capacity remaining in today's window."""
        self._reset_if_needed()
        return self._count < self.limit

    def record(self):
        """Increment the daily counter."""
        self._count += 1

    def remaining(self) -> int:
        self._reset_if_needed()
        return max(0, self.limit - self._count)

    def seconds_until_reset(self) -> float:
        return max(0.0, 86_400 - (time.time() - self._window_start))
