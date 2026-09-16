"""
Open-Meteo Marine + Forecast API — no registration, no key. Used as a
fallback/consensus source for wave and weather variables (PRD Appendix A.6).

Requests every hazard-relevant variable Open-Meteo actually offers in one
call each (no extra cost to ask for more fields) — wind gusts, swell/wind-
wave separation, pressure (+ trend from the surrounding hourly points),
precipitation intensity (not just probability), and fog-precursor
temperature/dewpoint. See DATA_ACQUISITION.md / the readiness audit for why
each of these matters and what was missing before.
"""
from datetime import datetime, timezone

import asyncio

import httpx

from app.core.cache import cache_get, cache_set
from app.core.config import settings


async def _get_with_retry(client: httpx.AsyncClient, url: str, params: dict, retries: int = 1):
    """
    httpx's own `timeout=` does NOT reliably bound DNS resolution on this
    platform (anyio's getaddrinfo runs via loop.run_in_executor and has
    been observed to hang past httpx's configured timeout entirely — a
    Windows network-stack quirk, not an httpx bug per se). Wrap each
    attempt in an explicit asyncio.wait_for as a hard backstop so a stuck
    DNS lookup can never block the whole request indefinitely.
    """
    last_exc = None
    for attempt in range(retries + 1):
        try:
            resp = await asyncio.wait_for(client.get(url, params=params), timeout=10)
            resp.raise_for_status()
            return resp
        except Exception as exc:  # pragma: no cover - network dependent
            last_exc = exc
            if attempt < retries:
                await asyncio.sleep(0.5)
    raise last_exc


async def get_marine_forecast(lat: float, lon: float, hour_offset: int = 0) -> dict:
    """
    hour_offset: 0 = now (default), +N = N hours into Open-Meteo's own
    forecast — genuinely the same forecast product's future prediction, not
    a fabricated value. Used by the Simulation Agent for "what if I leave
    later" scenarios. Only hour_offset=0 is cached (a future-hour read is
    scenario-specific, not worth caching under the same key as "now").
    """
    if hour_offset == 0:
        cached = await cache_get("marine", lat, lon)
        if cached is not None:
            return cached
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await _get_with_retry(
                client,
                settings.OPEN_METEO_MARINE_URL,
                {
                    "latitude": lat,
                    "longitude": lon,
                    "hourly": (
                        "wave_height,wave_period,wave_direction,"
                        "swell_wave_height,swell_wave_period,swell_wave_direction,"
                        "wind_wave_height,wind_wave_period,wind_wave_direction"
                    ),
                    "timezone": "auto",
                },
            )
            payload = resp.json()
        hourly = payload.get("hourly", {})
        idx = _nearest_now_index(hourly.get("time") or []) + hour_offset
        idx = max(0, min(idx, len(hourly.get("time") or []) - 1))
        result = {
            "source": "Open-Meteo Marine",
            "status": "success",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "wave_height_m": _at(hourly.get("wave_height"), idx),
            "wave_period_s": _at(hourly.get("wave_period"), idx),
            "swell_height_m": _at(hourly.get("swell_wave_height"), idx),
            "swell_period_s": _at(hourly.get("swell_wave_period"), idx),
            "swell_direction_deg": _at(hourly.get("swell_wave_direction"), idx),
            "wind_wave_height_m": _at(hourly.get("wind_wave_height"), idx),
            "wind_wave_direction_deg": _at(hourly.get("wind_wave_direction"), idx),
            "valid_time": _at(hourly.get("time"), idx),
        }
        if hour_offset == 0:
            await cache_set("marine", lat, lon, result)
        return result
    except Exception as exc:  # pragma: no cover - network dependent
        return {"source": "Open-Meteo Marine", "status": "failed", "error": str(exc)}


async def get_weather_forecast(lat: float, lon: float, hour_offset: int = 0) -> dict:
    """See get_marine_forecast's hour_offset docstring — same contract."""
    if hour_offset == 0:
        cached = await cache_get("weather", lat, lon)
        if cached is not None:
            return cached
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await _get_with_retry(
                client,
                "https://api.open-meteo.com/v1/forecast",
                {
                    "latitude": lat,
                    "longitude": lon,
                    "hourly": (
                        "wind_speed_10m,wind_direction_10m,wind_gusts_10m,"
                        "precipitation_probability,precipitation,"
                        "pressure_msl,temperature_2m,dew_point_2m,visibility"
                    ),
                    "timezone": "auto",
                },
            )
            payload = resp.json()
        hourly = payload.get("hourly", {})
        idx = _nearest_now_index(hourly.get("time") or []) + hour_offset
        idx = max(0, min(idx, len(hourly.get("time") or []) - 1))
        pressure_series = hourly.get("pressure_msl") or []
        pressure_trend_hpa_3h = _trend(pressure_series, idx, back=3)

        temp = _at(hourly.get("temperature_2m"), idx)
        dewpoint = _at(hourly.get("dew_point_2m"), idx)
        fog_risk = (temp is not None and dewpoint is not None and (temp - dewpoint) < 2.5)

        result = {
            "source": "Open-Meteo Forecast",
            "status": "success",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "wind_speed_ms": _kmh_to_ms(_at(hourly.get("wind_speed_10m"), idx)),
            "wind_gust_ms": _kmh_to_ms(_at(hourly.get("wind_gusts_10m"), idx)),
            "wind_direction_deg": _at(hourly.get("wind_direction_10m"), idx),
            "precipitation_probability": _at(hourly.get("precipitation_probability"), idx),
            "precipitation_mm_hr": _at(hourly.get("precipitation"), idx),
            "pressure_msl_hpa": _at(pressure_series, idx),
            "pressure_trend_hpa_3h": pressure_trend_hpa_3h,
            "temperature_2m_c": temp,
            "dew_point_2m_c": dewpoint,
            "fog_risk": fog_risk,
            "visibility_m": _at(hourly.get("visibility"), idx),
            "valid_time": _at(hourly.get("time"), idx),
        }
        if hour_offset == 0:
            await cache_set("weather", lat, lon, result)
        return result
    except Exception as exc:  # pragma: no cover - network dependent
        return {"source": "Open-Meteo Forecast", "status": "failed", "error": str(exc)}


def _nearest_now_index(time_strings: list[str]) -> int:
    """
    Open-Meteo's hourly arrays start at local midnight of the request day,
    not "now" — index 0 is NOT the current hour. Find the entry closest to
    the current time so point-in-time reads (and the pressure trend, which
    needs a real "3 hours ago") are actually correct.
    """
    if not time_strings:
        return 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    best_idx, best_diff = 0, None
    for i, ts in enumerate(time_strings):
        try:
            t = datetime.fromisoformat(ts)
        except ValueError:
            continue
        diff = abs((t - now).total_seconds())
        if best_diff is None or diff < best_diff:
            best_idx, best_diff = i, diff
    return best_idx


def _at(values, idx):
    if not values or idx >= len(values):
        return None
    return values[idx]


def _trend(series: list, idx: int, back: int) -> float | None:
    """Change over the last `back` hourly points — positive = rising."""
    if not series or idx - back < 0 or idx >= len(series):
        return None
    now, then = series[idx], series[idx - back]
    if now is None or then is None:
        return None
    return round(now - then, 2)


def _kmh_to_ms(v):
    return round(v / 3.6, 2) if v is not None else None
