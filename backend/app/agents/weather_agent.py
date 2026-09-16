"""
Weather Agent — deterministic (no LLM). Priority chain per PRD Section 7.3:
IMD (primary) -> Open-Meteo Forecast (fallback, live now) -> ERA5 (historical baseline, later).

When IMD_API_KEY lands in .env, this agent automatically starts using IMD as
primary with zero code changes elsewhere — the adapter itself reports
'unavailable' until then, and this agent moves on to the next source.

Carries gusts, pressure + trend, and fog precursor (temp/dewpoint spread) in
addition to sustained wind — added per the readiness-audit finding that
these were sitting available in Open-Meteo's response and simply unread.
"""
from app.models.schemas import WeatherState
from app.tools import imd_adapter, open_meteo_adapter


async def run_weather_agent(lat: float, lon: float) -> WeatherState:
    sources_used: list[str] = []
    freshness: dict[str, str] = {}
    missing: list[str] = []

    wind_speed = wind_gust = wind_dir = precip = precip_mm = None
    pressure = pressure_trend = temp = dewpoint = visibility = None
    fog_risk = False

    imd_result = await imd_adapter.get_imd_current_weather(lat, lon)
    if imd_result.get("status") not in ("unavailable", "failed"):
        data = imd_result.get("data", {})
        wind_speed = data.get("wind_speed_ms")
        wind_dir = data.get("wind_direction_deg")
        precip = data.get("precipitation_probability")
        sources_used.append("IMD")
        freshness["IMD"] = imd_result.get("fetched_at", "")

    if wind_speed is None:
        om_result = await open_meteo_adapter.get_weather_forecast(lat, lon)
        if om_result.get("status") == "success":
            wind_speed = om_result.get("wind_speed_ms")
            wind_gust = om_result.get("wind_gust_ms")
            wind_dir = om_result.get("wind_direction_deg")
            precip = om_result.get("precipitation_probability")
            precip_mm = om_result.get("precipitation_mm_hr")
            pressure = om_result.get("pressure_msl_hpa")
            pressure_trend = om_result.get("pressure_trend_hpa_3h")
            temp = om_result.get("temperature_2m_c")
            dewpoint = om_result.get("dew_point_2m_c")
            fog_risk = bool(om_result.get("fog_risk"))
            visibility = om_result.get("visibility_m")
            sources_used.append("Open-Meteo Forecast")
            freshness["Open-Meteo Forecast"] = om_result.get("fetched_at", "")
        else:
            missing.append("wind/precipitation (both IMD and Open-Meteo failed)")

    if pressure is None:
        missing.append("pressure trend (source did not report it)")

    # Cyclone / lightning: IMD-only for now; flagged missing until IMD or an
    # equivalent alert feed is wired in.
    if "IMD" not in sources_used:
        missing.append("cyclone track (IMD not yet available)")
        missing.append("lightning nowcast (IMD not yet available — no source identified, see readiness audit)")

    return WeatherState(
        wind_speed_ms=wind_speed,
        wind_gust_ms=wind_gust,
        wind_direction_deg=wind_dir,
        precipitation_probability=precip,
        precipitation_mm_hr=precip_mm,
        pressure_msl_hpa=pressure,
        pressure_trend_hpa_3h=pressure_trend,
        temperature_2m_c=temp,
        dew_point_2m_c=dewpoint,
        fog_risk=fog_risk,
        visibility_m=visibility,
        cyclone_active=False,
        sources_used=sources_used,
        data_freshness=freshness,
        partial=bool(missing),
        missing=missing,
    )
