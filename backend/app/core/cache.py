"""
Redis-backed cache for external-source adapter results. Solves two problems
at once (readiness audit, item 2): repeated point queries were re-fetching
from Copernicus/Open-Meteo every single time (slow for the user), which is
also what was hammering those upstream services into throttling us during
today's testing.

TTLs are matched to how fast each variable actually changes — a Copernicus
SST reading is meaningfully valid for longer than a wind gust reading. This
mirrors the PRD's own "data freshness" design principle: don't cache
everything with one blanket TTL.
"""
import hashlib
import json
from typing import Any

import redis.asyncio as redis

from app.core.config import settings

_client: redis.Redis | None = None

# Seconds. Keyed by adapter "kind" — passed explicitly at each call site so
# the TTL choice is visible in the code, not buried in this file alone.
TTL_SECONDS = {
    "weather": 600,       # 10 min — wind/pressure move fast
    "marine": 900,        # 15 min — wave/swell
    "sst": 3600,          # 1 hr — SST changes slowly through a day
    "copernicus": 3600,   # 1 hr — same reasoning, and it's our slowest source
    "copernicus_bgc": 10800,  # 3 hr — chlorophyll/nutrients are a daily product, changes slower still
    "geocode": 604800,    # 7 days — a place name's coordinates don't change
    # 12 hr — and this one is NOT a snapshot of "now". tide_adapter caches a
    # 28-hour predicted SERIES and interpolates the current height out of it
    # per request, so a long TTL costs no freshness: astronomical tide is
    # deterministic, and a series computed this morning is still exactly
    # right this evening. Before 27 Aug 2026 this key was missing entirely
    # and silently took the 600s default, which (combined with a 20s cap on
    # a 61s computation) meant tide was never cached and never returned.
    "tide": 43200,
    # 7 days — boundaries are static reference geometry, not observations.
    # The PRD's freshness policy lists them as a weekly integrity check.
    "boundaries": 604800,
}


def _get_client() -> redis.Redis | None:
    global _client
    if _client is not None:
        return _client
    if not settings.REDIS_URL:
        return None
    try:
        _client = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        return _client
    except Exception:
        return None


def _key(kind: str, lat: float, lon: float, extra: str = "") -> str:
    # Round to ~1km so nearby queries share a cache entry instead of each
    # being a permanent miss.
    rounded = f"{round(lat, 2)},{round(lon, 2)}"
    raw = f"jaljeev:{kind}:{rounded}:{extra}"
    return raw if len(raw) < 200 else f"jaljeev:{kind}:{hashlib.sha1(raw.encode()).hexdigest()}"


async def cache_get(kind: str, lat: float, lon: float, extra: str = "") -> dict | None:
    client = _get_client()
    if client is None:
        return None
    try:
        raw = await client.get(_key(kind, lat, lon, extra))
        return json.loads(raw) if raw else None
    except Exception:  # pragma: no cover - cache is best-effort, never fatal
        return None


async def cache_set(kind: str, lat: float, lon: float, value: dict[str, Any], extra: str = "") -> None:
    client = _get_client()
    if client is None:
        return
    try:
        ttl = TTL_SECONDS.get(kind, 600)
        await client.set(_key(kind, lat, lon, extra), json.dumps(value, default=str), ex=ttl)
    except Exception:  # pragma: no cover - cache is best-effort, never fatal
        pass
