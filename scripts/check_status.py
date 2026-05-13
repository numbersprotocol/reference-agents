"""Quick status check script."""
import httpx

# Mainnet health
try:
    r = httpx.get("https://mainnet.numbersprotocol.io/api/v3/health/", timeout=10)
    print(f"Mainnet health: {r.status_code}")
except Exception as e:
    print(f"Mainnet health: ERROR - {e}")

# Assets count
try:
    r2 = httpx.get("https://mainnet.numbersprotocol.io/api/v3/assets/?limit=1", timeout=10)
    print(f"Assets API: {r2.status_code}")
    d = r2.json()
    print(f"Total assets (count): {d.get('count', 'N/A')}")
except Exception as e:
    print(f"Assets API: ERROR - {e}")
