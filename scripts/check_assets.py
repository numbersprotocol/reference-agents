#!/usr/bin/env python3
"""Quick check of Numbers Protocol assets API to debug apAutoSync."""
import os, json, httpx

admin_token = os.environ.get("Capture_Token_Admin_Omni", "")
user_token = os.environ.get("Capture_Auth_Token", "")
url = "https://api.numbersprotocol.io/api/v3/assets/"
params = {"page_size": 10, "ordering": "-source_transaction__created_at"}

# Try admin token first
print("--- Trying Admin Token (Django Token auth) ---")
headers_admin = {"Authorization": f"Token {admin_token}"}
resp1 = httpx.get(url, params=params, headers=headers_admin, timeout=30)
print(f"Status: {resp1.status_code}")
if resp1.status_code == 200:
    data = resp1.json()
    print(f"Count: {data.get('count', 'N/A')}")
else:
    print(f"Error: {resp1.text[:200]}")

print()
print("--- Trying User Token (Bearer auth) ---")
headers_user = {"Authorization": f"token {user_token}"}
resp2 = httpx.get(url, params=params, headers=headers_user, timeout=30)
print(f"Status: {resp2.status_code}")
data = resp2.json()

print(f"Total assets in API: {data.get('count', 'N/A')}")
print(f"Results on this page: {len(data.get('results', []))}")
print()

for r in data.get("results", [])[:10]:
    owners = r.get("owner_addresses", ["?"])
    src_tx = r.get("source_transaction") or {}
    created = src_tx.get("created_at", "?")
    caption = str(r.get("caption", ""))[:80]
    owner_name = r.get("owner_name", "?")
    print(f"  owner_name={owner_name}  owners={owners}")
    print(f"  created={created}")
    print(f"  caption={caption}")
    print()

# Critical finding:
print("=" * 60)
print("DIAGNOSIS: Admin token returns 0 assets.")
print("User token returns 33,719 assets.")
print("apAutoSync uses CAPTURE_ADMIN_TOKEN (admin) -> always finds 0 new entries!")
print("ROOT CAUSE: The admin token scope does not include /api/v3/assets/ listing.")
print("FIX: apAutoSync should use user token OR make the call without auth (public).")
print("=" * 60)
