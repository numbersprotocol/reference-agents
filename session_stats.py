#!/usr/bin/env python3
"""Count registrations in current session (since last restart timestamp in logs)."""
import os

log_dir = "logs"
agents = ["provart", "newsprove", "agentlog", "dataprove", "socialprove", "researchprove", "codeprove"]

total = 0
for agent in agents:
    path = os.path.join(log_dir, f"{agent}.log")
    count = 0
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                if "registered" in line or "201 Created" in line:
                    count += 1
    print(f"  {agent:15s}: {count:>5}")
    total += count

print(f"  {'TOTAL':15s}: {total:>5}")
