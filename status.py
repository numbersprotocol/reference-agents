"""status.py — Quick live status for all 7 reference agents."""
import os
import signal
import subprocess
import httpx

BASE = os.path.dirname(os.path.abspath(__file__))
AGENTS = ["provart", "newsprove", "agentlog", "dataprove", "socialprove", "researchprove", "codeprove"]

print("=" * 60)
print("Numbers Protocol Reference Agents — Live Status")
print("=" * 60)

# ── Process status ────────────────────────────────────────────
print("\nPROCESS STATUS")
for agent in AGENTS:
    pid_file = os.path.join(BASE, "state", f"{agent}.pid")
    try:
        pid = int(open(pid_file).read().strip())
        os.kill(pid, 0)          # signal 0 = just check existence
        print(f"  RUNNING  {agent:<14} PID {pid}")
    except (FileNotFoundError, ValueError):
        print(f"  UNKNOWN  {agent:<14} (no PID file)")
    except ProcessLookupError:
        print(f"  DEAD     {agent:<14} PID {pid}")

# ── Registration counts from logs ─────────────────────────────
print("\nON-CHAIN REGISTRATIONS (HTTP 201 from Capture API)")
grand_total = 0
for agent in AGENTS:
    log_path = os.path.join(BASE, "logs", f"{agent}.log")
    try:
        with open(log_path) as f:
            lines = f.readlines()
        count = sum(1 for l in lines if '"HTTP/1.1 201 Created"' in l)
        last_nid = ""
        for l in reversed(lines):
            if "registered  nid=" in l:
                last_nid = l.split("nid=")[1].split()[0]
                break
        grand_total += count
        print(f"  {agent:<14}  {count:>4} txns   last NID: {last_nid or 'none yet'}")
    except FileNotFoundError:
        print(f"  {agent:<14}     0 txns   (no log file)")

print(f"  {'─'*54}")
print(f"  {'TOTAL':<14}  {grand_total:>4} txns")

# ── Mainnet explorer ──────────────────────────────────────────
print("\nNUMBERS MAINNET (live)")
try:
    r = httpx.get("https://mainnet.num.network/api/v2/stats", timeout=8)
    d = r.json()
    total_tx  = d.get("total_transactions", "n/a")
    today_tx  = d.get("transactions_today", "n/a")
    wallets   = d.get("total_addresses", "n/a")
    print(f"  Total transactions : {int(total_tx):,}" if str(total_tx).isdigit() else f"  Total transactions : {total_tx}")
    print(f"  Transactions today : {today_tx}")
    print(f"  Total wallets      : {int(wallets):,}" if str(wallets).isdigit() else f"  Total wallets      : {wallets}")
except Exception as e:
    print(f"  Could not reach explorer: {e}")

print()
