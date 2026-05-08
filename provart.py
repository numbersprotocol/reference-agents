"""
provart.py — ProvArt Reference Agent  (#1)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Generates AI art images and registers each one on Numbers Mainnet
as a C2PA-style provenance record.

Target:  500 transactions/day  (~1 every 173 seconds)
Cost:    $0/day with Pollinations.ai (default)  |  ~$1/day with Replicate

Modes (PROVART_MODE env var):
  pollinations  — Pollinations.ai free API, no key required (default)
  replicate     — Replicate API, requires REPLICATE_API_TOKEN

Usage:
  python provart.py
"""

import logging
import os
import time
import urllib.parse
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

from common import DailyCap, get_capture, maybe_collect, register_with_retry, setup_rotating_log, slack_alert

load_dotenv()

AGENT_ID = "Numbers Protocol Reference Agent #1 (ProvArt)"
AGENT_SHORT = "provart"
logger = logging.getLogger(AGENT_SHORT)

INTERVAL = int(os.getenv("PROVART_INTERVAL", "173"))
DAILY_CAP = int(os.getenv("PROVART_DAILY_CAP", "500"))
MODE = os.getenv("PROVART_MODE", "pollinations").lower()

# Prompt rotation — themed around AI provenance and digital media authenticity
PROMPTS = [
    "digital art, AI neural network visualization, glowing nodes, dark background",
    "abstract blockchain data streaming through cyberspace, blue and green",
    "provenance chain visualization, connected cryptographic blocks, minimal",
    "AI agent writing code, futuristic workspace, neon light accents",
    "digital fingerprint, unique hash pattern, cryptographic abstract art",
    "data integrity seal, abstract watermark stamp, clean geometric design",
    "AI model training, loss curve visualization, technical illustration",
    "decentralized network of AI agents sharing signed data, web of light",
    "content authenticity badge, glowing shield icon, dark tech aesthetic",
    "numbers protocol trust chain, media provenance abstract, blue palette",
    "autonomous agent deploying on blockchain, mechanical elegance",
    "media origin certificate, digital notary, minimal clean design",
    "invisible watermark revealed, AI-generated content label, technical",
    "web3 creator economy, artist wallet connection, abstract illustration",
    "cryptographic proof of creation, glowing seal, dark background",
    "AI-generated art signed and dated, certificate of authenticity",
    "distributed ledger as a canvas, painted blocks, colorful abstract",
    "prompt-to-image provenance trace, step-by-step visualization",
    "human truth machine proof, dual contrast abstract composition",
    "on-chain media archive, infinite scroll of timestamped images",
]


# ── Image generation ──────────────────────────────────────────────────────────

def _generate_pollinations(prompt: str, seed: int) -> bytes:
    """Call Pollinations.ai — free, no key required."""
    encoded = urllib.parse.quote(prompt)
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width=512&height=512&seed={seed}&nologo=true&model=flux"
    )
    resp = httpx.get(url, timeout=90, follow_redirects=True)
    resp.raise_for_status()
    if len(resp.content) < 1000:
        raise ValueError(f"Pollinations returned suspiciously small payload ({len(resp.content)} bytes)")
    return resp.content


def _generate_replicate(prompt: str) -> bytes:
    """Call Replicate API (~$0.002/image). Requires REPLICATE_API_TOKEN env var."""
    try:
        import replicate  # pip install replicate
    except ImportError:
        raise ImportError("Install replicate: pip install replicate")

    output = replicate.run(
        "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
        input={"prompt": prompt, "width": 512, "height": 512, "num_outputs": 1},
    )
    image_url = output[0]
    resp = httpx.get(image_url, timeout=30)
    resp.raise_for_status()
    return resp.content


def generate_image(prompt: str, counter: int) -> bytes:
    seed = (int(time.time()) + counter) % 2_147_483_647
    if MODE == "replicate":
        return _generate_replicate(prompt)
    return _generate_pollinations(prompt, seed)


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_once(capture, counter: int) -> bool:
    prompt = PROMPTS[counter % len(PROMPTS)]
    tmp_path = f"/tmp/provart_{os.getpid()}_{counter}.jpg"
    try:
        logger.info(f"generating [{counter}] prompt={prompt[:60]!r}")
        image_bytes = generate_image(prompt, counter)
        with open(tmp_path, "wb") as f:
            f.write(image_bytes)

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        caption = (
            f"{AGENT_ID} | "
            f"prompt: {prompt[:100]} | "
            f"mode: {MODE} | "
            f"generated: {ts}"
        )
        nid = register_with_retry(capture, tmp_path, caption, AGENT_SHORT)
        return nid is not None

    except Exception as exc:
        logger.error(f"run_once error (counter={counter}): {exc}")
        slack_alert(f"[ProvArt] error at counter={counter}: {exc}", level="ERROR")
        return False
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def main():
    setup_rotating_log(AGENT_SHORT)
    logger.info(
        f"ProvArt starting | mode={MODE} | interval={INTERVAL}s | daily_cap={DAILY_CAP}"
    )
    slack_alert(f"[ProvArt] started (mode={MODE})", level="INFO")

    capture = get_capture()
    cap = DailyCap(DAILY_CAP)
    counter = 0

    while True:
        if cap.check():
            success = run_once(capture, counter)
            if success:
                cap.record()
            counter += 1
        else:
            sleep_s = cap.seconds_until_reset()
            logger.info(f"daily cap reached ({DAILY_CAP}), sleeping {sleep_s:.0f}s until reset")
            time.sleep(sleep_s + 1)
            continue

        maybe_collect()
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
