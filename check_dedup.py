#!/usr/bin/env python3
"""Check dedup state file sizes."""
import json, os, glob

for f in sorted(glob.glob("state/*_seen.json")):
    agent = os.path.basename(f).replace("_seen.json", "")
    try:
        with open(f) as fh:
            data = json.load(fh)
        if isinstance(data, list):
            count = len(data)
        elif isinstance(data, dict):
            count = sum(len(v) if isinstance(v, list) else 1 for v in data.values())
        else:
            count = "unknown"
        print(f"  {agent}: {count} items tracked")
    except Exception as e:
        print(f"  {agent}: error - {e}")
