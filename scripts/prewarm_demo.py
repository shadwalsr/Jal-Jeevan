"""
JalJeev — demo pre-warm script.

Run this ~10-15 minutes before presenting so every demo query hits a warm
Redis cache instead of a cold Copernicus/tide fetch. This is NOT fake data
— every value that ends up cached is a genuine response from a live source,
just fetched slightly before the demo instead of during it. See the
data_freshness timestamps in any response for exactly how old each number
is; nothing here fabricates or hardcodes a value.

Retries each call a few times because a single cold run can hit a source
that's transiently slow (Copernicus especially) — the retry exists to
maximize how much of the response is genuinely populated by demo time, not
to paper over failures. If a source is still failing after retries, that's
real and the demo will honestly show it as "missing," which is itself a
feature worth having ready to explain (graceful degradation).

Usage:
    cd backend && source .venv/Scripts/activate
    python ../scripts/prewarm_demo.py
    # or point at a non-default running server:
    python ../scripts/prewarm_demo.py --base-url http://127.0.0.1:8000
"""
import argparse
import asyncio
import sys
import time

import httpx

# Demo points — chosen because they have verified real (not corrupted)
# GEBCO bathymetry and give a genuinely non-vetoed, realistic MODERATE-risk
# result: real seafloor depth ~40-56m, well within a small boat's draft
# margin, and close enough to a real port (Visakhapatnam) to stay inside a
# typical 40km operational range. See DATA_ACQUISITION.md for how these
# tiles were sourced (small verified regions, not the full India-wide
# GEBCO file — that one silently corrupted on a large OPeNDAP transfer).
DEMO_POINTS = [
    {"label": "15km offshore Visakhapatnam", "lat": 17.65, "lon": 83.35},
    {"label": "25km offshore Visakhapatnam", "lat": 17.6, "lon": 83.45},
    # Odisha set added 27 Aug 2026 — the presenter is based in Bhubaneswar,
    # so the demo should be answerable about water the judges recognise.
    # All four verified non-vetoed against the newly loaded GEBCO tiles
    # (scripts/fetch_gebco_regions.py): real depth, real ports in range.
    {"label": "20km east of Puri", "lat": 19.78, "lon": 86.02},
    {"label": "50km NE of Bhubaneswar (best Odisha result: LOW 10/100)", "lat": 20.61, "lon": 86.16},
    {"label": "20km NE of Paradip", "lat": 20.39, "lon": 86.82},
    {"label": "22km south of Puri", "lat": 19.60, "lon": 85.83},
]

# Route searches to pre-run, as (label, params). Each one warms every point
# its candidate scan touches, which is what actually makes the live query
# fast — warming only the destination would still leave the 16-candidate
# scan cold.
DEMO_ROUTES = [
    ("Vizag, standard 8m boat", {"lat": 17.65, "lon": 83.35, "range_km": 40}),
    ("Puri beach launch, standard 8m boat", {"lat": 19.78, "lon": 85.83, "range_km": 40}),
    (
        "Bhubaneswar, 12m boat with 100km range",
        {
            "lat": 20.2961, "lon": 85.8245, "range_km": 100,
            "vessel_length_m": 12, "vessel_operational_range_km": 100,
        },
    ),
    ("Paradip port launch, standard 8m boat", {"lat": 20.26, "lon": 86.68, "range_km": 40}),
]

RETRIES_PER_CALL = 3
RETRY_DELAY_S = 3


async def _get_with_retry(client: httpx.AsyncClient, path: str, params: dict, label: str) -> bool:
    for attempt in range(1, RETRIES_PER_CALL + 1):
        try:
            t0 = time.time()
            resp = await client.get(path, params=params, timeout=90)
            elapsed = time.time() - t0
            if resp.status_code == 200:
                print(f"  [{label}] OK in {elapsed:.1f}s (attempt {attempt})")
                return True
            print(f"  [{label}] HTTP {resp.status_code} (attempt {attempt}/{RETRIES_PER_CALL})")
        except Exception as exc:
            print(f"  [{label}] {type(exc).__name__}: {exc} (attempt {attempt}/{RETRIES_PER_CALL})")
        if attempt < RETRIES_PER_CALL:
            await asyncio.sleep(RETRY_DELAY_S)
    print(f"  [{label}] FAILED after {RETRIES_PER_CALL} attempts — will show as 'missing' live, which is honest, not broken")
    return False


async def prewarm(base_url: str):
    async with httpx.AsyncClient(base_url=base_url) as client:
        print(f"Pre-warming against {base_url}\n")

        for point in DEMO_POINTS:
            print(f"=== {point['label']} ({point['lat']}, {point['lon']}) ===")
            await _get_with_retry(
                client, "/marine/state", {"lat": point["lat"], "lon": point["lon"]}, "marine/state"
            )

        origin = DEMO_POINTS[0]

        for label, params in DEMO_ROUTES:
            print(f"\n=== Safest-route search: {label} ===")
            await _get_with_retry(client, "/marine/safest-route", params, "safest-route")

        # Simulation scenarios — Demo 3's "what if" moment
        print(f"\n=== Simulation scenarios ===")
        await _get_with_retry(
            client,
            "/marine/simulate/time-shift",
            {"lat": origin["lat"], "lon": origin["lon"], "hours_later": 6},
            "simulate/time-shift",
        )
        await _get_with_retry(
            client,
            "/marine/simulate/wave-perturbation",
            {"lat": origin["lat"], "lon": origin["lon"], "wave_multiplier": 1.6},
            "simulate/wave-perturbation",
        )

        print("\nDone. Re-run this again right before you go on if there's a gap, since some")
        print("cache TTLs are as short as 10 minutes (see app/core/cache.py TTL_SECONDS).")
        print("Tide is the exception — it caches a 12h predicted series, so one pass covers")
        print("a whole day of demos for these points (see app/tools/tide_adapter.py).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    try:
        asyncio.run(prewarm(args.base_url))
    except KeyboardInterrupt:
        sys.exit(1)
