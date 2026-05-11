#!/usr/bin/env python3
"""Count registrations ONLY from Session 7 (started 2026-05-11T00:31 UTC)."""
import os

log_dir = "logs"
agents = ["provart", "newsprove", "agentlog", "dataprove", "socialprove", "researchprove", "codeprove"]
SESSION_START = "2026-05-11T00:31"

total = 0
for agent in agents:
    path = os.path.join(log_dir, f"{agent}.log")
    count = 0
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                if ("registered" in line or "201 Created" in line) and line >= SESSION_START:
                    count += 1
    print(f"  {agent:15s}: {count:>5}")
    total += count

print(f"  {'TOTAL':15s}: {total:>5}")
print(f"\n  Session 7 uptime: started 00:31 UTC May 11")
