"""
dataprove.py — DataProve Reference Agent  (#4)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Registers open data feeds — weather, cryptocurrency prices, and air quality
— as timestamped provenance records on Numbers Mainnet.

Target:  500 transactions/day  (~1 every 300 seconds)
Cost:    $0/day  (all free public APIs, no keys required)

Data sources:
  - Open-Meteo: current weather + UV index for 30 world cities
  - CoinGecko: crypto prices for 5 assets
  - AQICN/WAQI: air quality index for major cities
  - USGS: earthquake events (last hour, global)
  - ExchangeRate-API (ECB): currency exchange rates (15 pairs)

Deduplication: time-bucketed IDs (source + city + hour) prevent duplicates
within a registration window while still capturing hourly updates.

Usage:
  python dataprove.py
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

AGENT_ID = "Numbers Protocol Reference Agent #4 (DataProve)"
AGENT_SHORT = "dataprove"
logger = logging.getLogger(AGENT_SHORT)

INTERVAL = int(os.getenv("DATAPROVE_INTERVAL", "430"))
DAILY_CAP = int(os.getenv("DATAPROVE_DAILY_CAP", "200"))

# ── Data sources ──────────────────────────────────────────────────────────────

CITIES = [
    # Original 10
    ("New York",     40.7128,  -74.0060),
    ("London",       51.5074,   -0.1278),
    ("Tokyo",        35.6762,  139.6503),
    ("Singapore",     1.3521,  103.8198),
    ("Sydney",      -33.8688,  151.2093),
    ("São Paulo",   -23.5505,  -46.6333),
    ("Mumbai",       19.0760,   72.8777),
    ("Berlin",       52.5200,   13.4050),
    ("Dubai",        25.2048,   55.2708),
    ("Toronto",      43.6532,  -79.3832),
    # Added 20 cities for T2
    ("Paris",        48.8566,    2.3522),
    ("Seoul",        37.5665,  126.9780),
    ("Mexico City",  19.4326,  -99.1332),
    ("Cairo",        30.0444,   31.2357),
    ("Jakarta",      -6.2088,  106.8456),
    ("Moscow",       55.7558,   37.6173),
    ("Lagos",         6.5244,    3.3792),
    ("Buenos Aires",-34.6037,  -58.3816),
    ("Istanbul",     41.0082,   28.9784),
    ("Bangkok",      13.7563,  100.5018),
    ("Taipei",       25.0330,  121.5654),
    ("Nairobi",      -1.2921,   36.8219),
    ("Amsterdam",    52.3676,    4.9041),
    ("Stockholm",    59.3293,   18.0686),
    ("Johannesburg",-26.2041,   28.0473),
    ("Lima",        -12.0464,  -77.0428),
    ("Manila",       14.5995,  120.9842),
    ("Riyadh",       24.7136,   46.6753),
    ("Zurich",       47.3769,    8.5417),
    ("Auckland",    -36.8485,  174.7633),
]

CRYPTO_IDS = "bitcoin,ethereum,numbers-protocol,solana,avalanche-2"


def fetch_weather(city: str, lat: float, lon: float) -> dict | None:
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current_weather=true"
        f"&wind_speed_unit=ms"
        f"&hourly=uv_index"
        f"&forecast_days=1"
    )
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        cw = data.get("current_weather", {})
        # Get current UV index from hourly data (closest hour)
        uv_index = None
        hourly = data.get("hourly", {})
        uv_vals = hourly.get("uv_index", [])
        if uv_vals:
            now_hour = datetime.now(timezone.utc).hour
            uv_index = uv_vals[min(now_hour, len(uv_vals) - 1)]
        return {
            "city": city,
            "latitude": lat,
            "longitude": lon,
            "temperature_c": cw.get("temperature"),
            "wind_speed_ms": cw.get("windspeed"),
            "weather_code": cw.get("weathercode"),
            "is_day": cw.get("is_day"),
            "uv_index": uv_index,
            "observation_time": cw.get("time"),
        }
    except Exception as exc:
        logger.debug(f"weather fetch failed for {city}: {exc}")
        return None


def fetch_crypto_prices() -> dict | None:
    url = (
        f"https://api.coingecko.com/api/v3/simple/price"
        f"?ids={CRYPTO_IDS}&vs_currencies=usd&include_24hr_change=true"
    )
    try:
        resp = httpx.get(url, timeout=10, headers={"Accept": "application/json"})
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.debug(f"crypto fetch failed: {exc}")
        return None


def fetch_air_quality(city: str, lat: float, lon: float) -> dict | None:
    """AQICN air quality (replaces broken OpenAQ v3 which returns 401)."""
    # Use WAQI/AQICN public feed (no API key for geo feed)
    url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token=demo"
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "ok":
            return None
        d = data.get("data", {})
        return {
            "city": city,
            "station": d.get("city", {}).get("name"),
            "aqi": d.get("aqi"),
            "dominant_pollutant": d.get("dominentpol"),
            "time": d.get("time", {}).get("iso"),
        }
    except Exception as exc:
        logger.debug(f"air quality fetch failed for {city}: {exc}")
        return None


def fetch_earthquakes() -> list[dict]:
    """USGS earthquake events in the last hour (free, no key)."""
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
    try:
        resp = httpx.get(url, timeout=15)
        resp.raise_for_status()
        features = resp.json().get("features", [])
        results = []
        for f in features[:10]:  # cap at 10 per cycle
            props = f.get("properties", {})
            coords = f.get("geometry", {}).get("coordinates", [])
            results.append({
                "id": f.get("id"),
                "magnitude": props.get("mag"),
                "place": props.get("place"),
                "time_ms": props.get("time"),
                "longitude": coords[0] if len(coords) > 0 else None,
                "latitude": coords[1] if len(coords) > 1 else None,
                "depth_km": coords[2] if len(coords) > 2 else None,
            })
        return results
    except Exception as exc:
        logger.debug(f"earthquake fetch failed: {exc}")
        return []


def fetch_exchange_rates() -> dict | None:
    """ECB-sourced exchange rates via open API (free, no key)."""
    url = "https://open.er-api.com/v6/latest/USD"
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # Keep a subset of key currencies
        keep = ["EUR", "GBP", "JPY", "CNY", "KRW", "TWD", "SGD", "AUD",
                "CAD", "CHF", "INR", "BRL", "MXN", "ZAR", "THB"]
        rates = {k: v for k, v in data.get("rates", {}).items() if k in keep}
        return {
            "base": "USD",
            "rates": rates,
            "time_last_update_utc": data.get("time_last_update_utc"),
        }
    except Exception as exc:
        logger.debug(f"exchange rate fetch failed: {exc}")
        return None


# ── Main loop ─────────────────────────────────────────────────────────────────

def _hour_bucket() -> str:
    """Returns a string like '2026-05-06T14' to bucket dedup by hour."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")


def run_cycle(capture, seen: set, cap: DailyCap) -> int:
    registered = 0
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    bucket = _hour_bucket()

    # --- Crypto prices (one record per cycle) ---
    if cap.check():
        dedup_key = f"crypto:{bucket}"
        if dedup_key not in seen:
            prices = fetch_crypto_prices()
            if prices:
                record = {
                    "agent": AGENT_ID,
                    "source": "CoinGecko",
                    "data_type": "cryptocurrency_prices",
                    "assets": prices,
                    "recorded_at": ts,
                }
                tmp = write_json_tmp(record, prefix="dataprove_crypto_")
                try:
                    caption = f"{AGENT_ID} | crypto prices | {ts}"
                    nid = register_with_retry(capture, tmp, caption, AGENT_SHORT)
                    if nid:
                        seen.add(dedup_key)
                        cap.record()
                        registered += 1
                finally:
                    if os.path.exists(tmp):
                        os.unlink(tmp)
                time.sleep(2)

    # --- Weather per city ---
    for city, lat, lon in CITIES:
        if not cap.check():
            break
        dedup_key = f"weather:{city}:{bucket}"
        if dedup_key in seen:
            continue

        data = fetch_weather(city, lat, lon)
        if not data:
            continue

        record = {
            "agent": AGENT_ID,
            "source": "Open-Meteo",
            "data_type": "weather",
            **data,
            "recorded_at": ts,
        }
        tmp = write_json_tmp(record, prefix="dataprove_wx_")
        try:
            caption = (
                f"{AGENT_ID} | weather | "
                f"{city} | {data.get('temperature_c')}°C | {ts}"
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

    # --- Air quality (sample 10 cities per cycle) ---
    for city, lat, lon in CITIES[:10]:
        if not cap.check():
            break
        dedup_key = f"aq:{city}:{bucket}"
        if dedup_key in seen:
            continue

        data = fetch_air_quality(city, lat, lon)
        if not data:
            seen.add(dedup_key)  # mark as seen to avoid repeated failed calls
            continue

        record = {
            "agent": AGENT_ID,
            "source": "AQICN/WAQI",
            "data_type": "air_quality",
            **data,
            "recorded_at": ts,
        }
        tmp = write_json_tmp(record, prefix="dataprove_aq_")
        try:
            caption = f"{AGENT_ID} | air quality | {city} | AQI={data.get('aqi')} | {ts}"
            nid = register_with_retry(capture, tmp, caption, AGENT_SHORT)
            if nid:
                seen.add(dedup_key)
                cap.record()
                registered += 1
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        time.sleep(2)

    # --- Earthquake events ---
    quakes = fetch_earthquakes()
    for eq in quakes:
        if not cap.check():
            break
        eq_id = eq.get("id", "unknown")
        dedup_key = f"earthquake:{eq_id}"
        if dedup_key in seen:
            continue

        record = {
            "agent": AGENT_ID,
            "source": "USGS",
            "data_type": "earthquake",
            **eq,
            "recorded_at": ts,
        }
        tmp = write_json_tmp(record, prefix="dataprove_eq_")
        try:
            caption = (
                f"{AGENT_ID} | earthquake | "
                f"M{eq.get('magnitude')} | {eq.get('place')} | {ts}"
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

    # --- Exchange rates (one record per cycle) ---
    if cap.check():
        dedup_key = f"forex:{bucket}"
        if dedup_key not in seen:
            rates = fetch_exchange_rates()
            if rates:
                record = {
                    "agent": AGENT_ID,
                    "source": "ExchangeRate-API/ECB",
                    "data_type": "exchange_rates",
                    **rates,
                    "recorded_at": ts,
                }
                tmp = write_json_tmp(record, prefix="dataprove_fx_")
                try:
                    caption = f"{AGENT_ID} | exchange rates | USD base | {ts}"
                    nid = register_with_retry(capture, tmp, caption, AGENT_SHORT)
                    if nid:
                        seen.add(dedup_key)
                        cap.record()
                        registered += 1
                finally:
                    if os.path.exists(tmp):
                        os.unlink(tmp)
                time.sleep(2)

    return registered


def main():
    logger.info(
        f"DataProve starting | interval={INTERVAL}s | daily_cap={DAILY_CAP}"
    )
    slack_alert("[DataProve] started", level="INFO")

    capture = get_capture()
    cap = DailyCap(DAILY_CAP)
    seen = load_seen_ids(AGENT_SHORT)

    while True:
        if cap.check():
            n = run_cycle(capture, seen, cap)
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
