"""
Ocean Agent — deterministic (no LLM). Wave height from INCOIS OSF (primary)
falling back to Open-Meteo Marine. SST computed as a consensus across every
source currently reachable (INCOIS, NOAA OISST, Copernicus Marine) — flags
disagreement if sources differ by more than 1 degree C, per the PRD
multi-source redundancy matrix (Section 7.3).

MOSDAC OCM-3 SST/chlorophyll will join this consensus automatically once
MOSDAC credentials are configured (see app/tools/mosdac_adapter.py).

All four source calls run CONCURRENTLY (asyncio.gather), not sequentially —
each one has its own internal timeout (10-25s), and running them in series
would let worst-case latencies add up past a minute. Running them together
means total latency is bounded by the slowest single source, not the sum.
"""
import asyncio

from datetime import datetime, timezone

from app.agents.anomaly_agent import detect_sst_anomaly
from app.models.schemas import OceanState
from app.tools import copernicus_adapter, incois_adapter, noaa_oisst_adapter, open_meteo_adapter, tide_adapter


async def run_ocean_agent(lat: float, lon: float) -> OceanState:
    sources_used: list[str] = []
    freshness: dict[str, str] = {}
    missing: list[str] = []

    # Tide no longer needs a cap here. It used to get a 20s one, which was
    # strictly worse than useless: a cold EOT20 prediction measured 61s, so
    # the cap fired every time, cancelled the computation before it could
    # write to Redis, and left tide permanently missing while still costing
    # every single request the full 20s. Measured live 27 Aug 2026 —
    # /marine/state never dropped below ~20s no matter how warm the cache.
    # tide_adapter.get_tide now returns immediately in both cases: a cached
    # prediction, or status="computing" while a background task builds one.
    incois_result, om_marine_result, noaa_result, copernicus_result, bgc_result, tide_result = await asyncio.gather(
        incois_adapter.get_incois_wave_forecast(lat, lon),
        open_meteo_adapter.get_marine_forecast(lat, lon),
        noaa_oisst_adapter.get_sst(lat, lon),
        copernicus_adapter.get_physics_subset(lat, lon),
        copernicus_adapter.get_bgc_subset(lat, lon),
        tide_adapter.get_tide(lat, lon),
    )

    # --- Wave height: INCOIS primary, Open-Meteo Marine fallback ---
    wave_height = wave_period = None
    swell_height = swell_period = swell_dir = None
    wind_wave_height = wind_wave_dir = None
    cross_swell = False

    if incois_result.get("status") != "failed":
        try:
            wave_height = incois_result["data"].get("wave_height")
            sources_used.append("INCOIS OSF")
            freshness["INCOIS OSF"] = incois_result.get("fetched_at", "")
        except Exception as exc:
            print(f"[ocean_agent] failed to parse INCOIS wave data: {type(exc).__name__}: {exc}")
            wave_height = None

    # Swell/wind-wave separation is Open-Meteo-only today (INCOIS's ERDDAP
    # doesn't expose it) — read it whenever Open-Meteo Marine succeeds,
    # regardless of which source won the primary wave-height reading.
    if om_marine_result.get("status") == "success":
        if wave_height is None:
            wave_height = om_marine_result.get("wave_height_m")
            wave_period = om_marine_result.get("wave_period_s")
            sources_used.append("Open-Meteo Marine")
            freshness["Open-Meteo Marine"] = om_marine_result.get("fetched_at", "")

        swell_height = om_marine_result.get("swell_height_m")
        swell_period = om_marine_result.get("swell_period_s")
        swell_dir = om_marine_result.get("swell_direction_deg")
        wind_wave_height = om_marine_result.get("wind_wave_height_m")
        wind_wave_dir = om_marine_result.get("wind_wave_direction_deg")

        # A meaningful cross-sea: two wave trains of comparable size arriving
        # from noticeably different directions — more dangerous than either
        # alone, and invisible in a single combined wave-height number.
        if swell_dir is not None and wind_wave_dir is not None and swell_height and wind_wave_height:
            angle_diff = abs(swell_dir - wind_wave_dir) % 360
            angle_diff = min(angle_diff, 360 - angle_diff)
            cross_swell = angle_diff > 40 and min(swell_height, wind_wave_height) > 0.5

    if wave_height is None:
        missing.append("wave height (INCOIS and Open-Meteo both failed)")
    if swell_height is None:
        missing.append("swell/wind-wave separation (Open-Meteo Marine unavailable)")

    # --- Tide: EOT20 harmonic prediction (astronomical tide only — storm
    # surge is a separate, still-unmodeled hazard, see readiness audit) ---
    tide_height = tide_state = None
    if tide_result.get("status") == "success":
        tide_height = tide_result.get("tide_height_m")
        tide_state = tide_result.get("tide_state")
        sources_used.append("EOT20 (pyTMD)")
        freshness["EOT20 (pyTMD)"] = tide_result.get("fetched_at", "")
    else:
        missing.append(f"tide state ({tide_result.get('reason') or tide_result.get('error') or tide_result.get('status')})")

    # --- SST: multi-source consensus ---
    sst_sources: dict[str, float] = {}
    current_speed = None
    salinity = mld = None

    if noaa_result.get("status") == "success":
        sst_sources["NOAA OISST"] = noaa_result["sst_c"]
        sources_used.append("NOAA OISST")
        freshness["NOAA OISST"] = noaa_result.get("fetched_at", "")

    if copernicus_result.get("status") == "success":
        sst_sources["Copernicus Marine"] = copernicus_result["sst_c"]
        sources_used.append("Copernicus Marine")
        freshness["Copernicus Marine"] = copernicus_result.get("fetched_at", "")
        u, v = copernicus_result.get("current_u_ms"), copernicus_result.get("current_v_ms")
        if u is not None and v is not None:
            current_speed = round((u**2 + v**2) ** 0.5, 3)
        salinity = copernicus_result.get("salinity_psu")
        mld = copernicus_result.get("mixed_layer_depth_m")
    else:
        missing.append("salinity/mixed-layer depth (Copernicus unavailable)")

    sst_consensus = sst_disagreement = None
    if sst_sources:
        vals = list(sst_sources.values())
        sst_consensus = round(sum(vals) / len(vals), 2)
        sst_disagreement = round(max(vals) - min(vals), 2) if len(vals) > 1 else 0.0
    else:
        # Surface the actual per-source reasons (each adapter already
        # captures one) instead of a generic message — matches the pattern
        # used for tide just above. A blanket "all sources failed" with no
        # reason is exactly what let the NOAA/Copernicus SST failures go
        # unnoticed (see CLAUDE.md gotcha #4).
        noaa_reason = noaa_result.get("error") or noaa_result.get("status")
        copernicus_reason = copernicus_result.get("error") or copernicus_result.get("status")
        missing.append(f"SST (NOAA: {noaa_reason}; Copernicus: {copernicus_reason})")

    # --- SST anomaly (single-year 2023 baseline — see anomaly_agent.py) ---
    sst_anomaly = sst_anomaly_z = sst_anomaly_note = None
    if sst_consensus is not None:
        anomaly_result = detect_sst_anomaly(lat, lon, datetime.now(timezone.utc).month, sst_consensus)
        if anomaly_result.get("status") == "success":
            sst_anomaly = anomaly_result["is_anomaly"]
            sst_anomaly_z = anomaly_result["z_score"]
            sst_anomaly_note = anomaly_result["baseline_note"]
        else:
            missing.append(f"SST anomaly baseline ({anomaly_result.get('reason')})")

    # --- Chlorophyll + harmful algal bloom (HAB) proxy ---
    # HAB_THRESHOLD is a coarse, literature-typical bloom indicator for
    # coastal tropical waters, NOT a calibrated regional threshold — treat
    # as a "worth a second look" flag, not a diagnosis. Refine once real
    # regional baselines exist (see readiness audit).
    HAB_THRESHOLD_MG_M3 = 5.0
    chlorophyll = hab_risk = None
    if bgc_result.get("status") == "success":
        chlorophyll = bgc_result.get("chlorophyll_mg_m3")
        hab_risk = chlorophyll is not None and chlorophyll >= HAB_THRESHOLD_MG_M3
        sources_used.append("Copernicus Marine BGC")
        freshness["Copernicus Marine BGC"] = bgc_result.get("fetched_at", "")
    else:
        missing.append("chlorophyll (Copernicus BGC unavailable)")
        hab_risk = False

    return OceanState(
        significant_wave_height_m=wave_height,
        wave_period_s=wave_period,
        swell_height_m=swell_height,
        swell_period_s=swell_period,
        swell_direction_deg=swell_dir,
        wind_wave_height_m=wind_wave_height,
        wind_wave_direction_deg=wind_wave_dir,
        cross_swell=cross_swell,
        current_speed_ms=current_speed,
        tide_height_m=tide_height,
        tide_state=tide_state,
        salinity_psu=salinity,
        mixed_layer_depth_m=mld,
        chlorophyll_mg_m3=chlorophyll,
        hab_risk=bool(hab_risk),
        sst_anomaly=bool(sst_anomaly),
        sst_anomaly_z_score=sst_anomaly_z,
        sst_anomaly_note=sst_anomaly_note,
        sst_c=sst_consensus,
        sst_sources=sst_sources,
        sst_consensus=sst_consensus,
        sst_disagreement=sst_disagreement,
        sources_used=sorted(set(sources_used)),
        data_freshness=freshness,
        partial=bool(missing),
        missing=missing,
    )
