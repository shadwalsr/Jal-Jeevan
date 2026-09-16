"""
Satellite / Source Discovery Agent (PRD Section 8, "Satellite Discovery
Agent" role). Deterministic catalog + selection logic — no LLM: which
underlying product/sensor backs each variable is a fact, not something to
infer.

Job: given the variables a query actually needs, tell the caller which
real-world products/sensors supply them, which adapter in this codebase
calls them, and whether that source is currently active (has credentials
configured) or still pending. This is the "provenance" half of the PRD's
data-quality principle (Section 7-9): a number should never be shown
without saying what actually produced it.

Every entry below is a real, verifiable product — do not add a source here
without confirming what it actually is; this catalog is read as a claim
about what backs the running system, not aspirational metadata.
"""
from app.core.config import settings

CATALOG: dict[str, list[dict]] = {
    "sst": [
        {
            "product": "NOAA OISST v2.1",
            "sensor": "AVHRR (satellite) blended with ship/buoy in-situ obs",
            "data_type": "observation",
            "resolution_km": 25,
            "adapter": "app.tools.noaa_oisst_adapter",
            "requires": None,
        },
        {
            "product": "Copernicus Global Ocean Physics Analysis and Forecast",
            "sensor": "multi-source data-assimilative ocean model (assimilates satellite altimetry + SST + Argo)",
            "data_type": "analysis/forecast",
            "resolution_km": 9,
            "adapter": "app.tools.copernicus_adapter",
            "requires": "COPERNICUS_MARINE_USERNAME",
        },
        {
            "product": "ISRO MOSDAC OCM-3",
            "sensor": "Oceansat-2/3 Ocean Colour Monitor (satellite)",
            "data_type": "observation",
            "resolution_km": 1,
            "adapter": "app.tools.mosdac_adapter",
            "requires": "MOSDAC_USERNAME",
        },
    ],
    "chlorophyll": [
        {
            "product": "Copernicus GlobColour (BGC analysis-forecast, phytoplankton functional types)",
            "sensor": "OLCI (Sentinel-3) / MODIS / VIIRS ocean-colour composite",
            "data_type": "observation",
            "resolution_km": 25,
            "adapter": "app.tools.copernicus_adapter.get_bgc_subset",
            "requires": "COPERNICUS_MARINE_USERNAME",
        },
    ],
    "wave_height": [
        {
            "product": "Open-Meteo Marine",
            "sensor": "ECMWF/NOAA wave model, altimetry-assimilated",
            "data_type": "forecast",
            "resolution_km": 25,
            "adapter": "app.tools.open_meteo_adapter",
            "requires": None,
        },
        {
            "product": "INCOIS Ocean State Forecast",
            "sensor": "WAM wave model",
            "data_type": "forecast",
            "resolution_km": 12,
            "adapter": "app.tools.incois_adapter",
            "requires": None,  # public ERDDAP, but see gotcha: SSL cert broken as of Aug 2026
        },
    ],
    "wind": [
        {
            "product": "Open-Meteo Forecast",
            "sensor": "ECMWF/GFS model reanalysis-forecast blend",
            "data_type": "forecast",
            "resolution_km": 11,
            "adapter": "app.tools.open_meteo_adapter",
            "requires": None,
        },
        {
            "product": "IMD",
            "sensor": "station network + NWP model",
            "data_type": "forecast",
            "resolution_km": 12,
            "adapter": "app.tools.imd_adapter",
            "requires": "IMD_API_KEY",
        },
    ],
    "sea_level_anomaly": [
        {
            "product": "Copernicus DUACS (SSALTO/DUACS multi-mission altimetry)",
            "sensor": "satellite radar altimetry (Jason-3, Sentinel-6, SWOT, etc.), multi-mission merged",
            "data_type": "observation",
            "resolution_km": 25,
            "adapter": "app.tools.copernicus_adapter",
            "requires": "COPERNICUS_MARINE_USERNAME",
        },
    ],
    "tide": [
        {
            "product": "EOT20",
            "sensor": "harmonic constituents derived from satellite altimetry time series",
            "data_type": "model/prediction (astronomical tide only, not storm surge)",
            "resolution_km": 14,
            "adapter": "app.tools.tide_adapter",
            "requires": None,  # local model file, no live credentials needed
        },
    ],
    "bathymetry": [
        {
            "product": "GEBCO_2026",
            "sensor": "shipborne multibeam sonar compiled with satellite-derived bathymetry",
            "data_type": "static reference grid",
            "resolution_km": 0.45,
            "adapter": "app.tools.bathymetry_adapter",
            "requires": None,  # local file, but only a few demo regions loaded — see DATA_ACQUISITION.md
        },
    ],
    "cyclone_track": [
        {
            "product": "IMD cyclone bulletins",
            "sensor": "INSAT-3D/3DR + multi-satellite consensus track",
            "data_type": "observation/forecast",
            "resolution_km": None,
            "adapter": "app.tools.imd_adapter",
            "requires": "IMD_API_KEY",
        },
        {
            "product": "IBTrACS",
            "sensor": "multi-agency historical best-track compilation",
            "data_type": "historical archive only, not live tracking",
            "resolution_km": None,
            "adapter": None,  # bulk-downloaded, not wired into any live adapter yet
            "requires": None,
        },
    ],
}


def discover_sources(variables: list[str]) -> dict:
    """For each requested variable, list the real products/sensors that can
    supply it and whether each is currently active given configured credentials."""
    result = {}
    for var in variables:
        entries = CATALOG.get(var, [])
        if not entries:
            result[var] = {"status": "no_known_source", "entries": []}
            continue
        annotated = []
        for entry in entries:
            requires = entry.get("requires")
            active = requires is None or bool(getattr(settings, requires, None))
            annotated.append({**entry, "active": active})
        result[var] = {"status": "ok", "entries": annotated}
    return result


# Which variables a given planner intent_type actually needs — lets the
# planner's trace say "this question needs SST + chlorophyll + waves" before
# any agent runs, matching the PRD's "make agentic planning visible" ask.
INTENT_VARIABLE_MAP = {
    "current_conditions": ["sst", "wave_height", "wind", "tide", "bathymetry"],
    "safest_zone": ["sst", "wave_height", "wind", "tide", "bathymetry", "sea_level_anomaly"],
    "route": ["sst", "wave_height", "wind", "tide", "bathymetry", "cyclone_track"],
    # A port-to-port passage needs everything a route does, and leans harder
    # on tide and bathymetry than any other intent: a deep-draft trader's
    # under-keel clearance and a sailing vessel's wind are the two things
    # that actually decide whether a passage is viable.
    "passage": ["sst", "wave_height", "wind", "tide", "bathymetry", "cyclone_track", "sea_level_anomaly"],
    "general": [],
}


def variables_for_intent(intent_type: str) -> list[str]:
    return INTENT_VARIABLE_MAP.get(intent_type, [])
