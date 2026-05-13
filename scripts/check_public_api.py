#!/usr/bin/env python3
"""Check if Numbers Protocol assets API works without auth (public)."""
import httpx

url = "https://api.numbersprotocol.io/api/v3/assets/"
params = {"page_size": 3, "ordering": "-source_transaction__created_at"}

# No auth header
resp = httpx.get(url, params=params, timeout=30)
print(f"No auth - Status: {resp.status_code}")
data = resp.json()
print(f"No auth - Count: {data.get('count', 'N/A')}")
print(f"No auth - Results: {len(data.get('results', []))}")
print()

# Check if we can filter by excluding our agent owner
params_filtered = {
    "page_size": 5,
    "ordering": "-source_transaction__created_at",
}
resp2 = httpx.get(url, params=params_filtered, timeout=30)
data2 = resp2.json()
non_agent_count = 0
for r in data2.get("results", [])[:5]:
    owner = r.get("owner_name", "?")
    caption = str(r.get("caption", ""))[:60]
    is_agent = "officialnumbers" in str(owner)
    marker = "[AGENT]" if is_agent else "[USER]"
    print(f"  {marker} owner={owner} | {caption}")
    if not is_agent:
        non_agent_count += 1

print(f"\nNon-agent assets in top 5: {non_agent_count}")
print(f"\nConclusion: Public API works={'YES' if resp.status_code == 200 and data.get('count', 0) > 0 else 'NO'}")
print("Fix: apAutoSync should call the API without auth (or with user token)")
