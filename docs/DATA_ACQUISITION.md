# JalJeev — Data Acquisition Architecture & Source Directory

**Project:** JalJeev — Agentic Marine Intelligence System  
**Team:** Team Felix, KIIT University, Bhubaneswar  
**SIH Problem Statement:** SIH26176 (ISRO)  
**Last Updated:** September 2026  

---

## 1. Executive Summary

JalJeev ingests, harmonises, and serves marine intelligence by orchestrating data across **16 primary data providers** and **over 25 distinct datasets**. The data pipeline spans real-time spaceborne Earth observation (ISRO EOS-06 OCM-3), numerical ocean state analysis (Copernicus Marine, NOAA CoastWatch), high-resolution atmospheric forecasts (Open-Meteo, IMD), global hydrodynamic tide models (EOT20), high-resolution bathymetric terrain grids (GEBCO 2026), international maritime boundary delineations (Marine Regions EEZ, UNCLOS), and planetary conservation databases (Protected Planet WDPA).

Every reading delivered across JalJeev’s multi-agent system carries strict provenance metadata (sensor source, spatial resolution, fetch timestamp, and validation status) to ensure safety-critical transparency for coastal and artisanal fishing communities.

---

## 2. Master Data Source Directory & Portals

| # | Provider / Organization | Dataset & Scientific Product | Underlying Sensor / Platform | Spatial Res. | Access Protocol & Endpoints | Official Portal & Dataset Link | Status | Primary Code Handler |
|---|---|---|---|---|---|---|---|---|
| **1** | **ISRO MOSDAC** | EOS-06 OCM-3 L4 Analyzed Chlorophyll (`E06OCM_L4_AC`) | Ocean Colour Monitor-3 on Oceansat-3 (MOM5+TOPAZ model assimilation) | 1 km | REST API (`mdapi`) + NetCDF binary stream | [OCEANSAT-3 Mission Data Portal](https://www.mosdac.gov.in/oceansat-3?utm_source=gemini) | ✅ Active / Integrated | [mosdac_adapter.py](file:///d:/Jaljeev/backend/app/tools/mosdac_adapter.py) |
| **2** | **Copernicus Marine (CMEMS)** | Global Ocean Physics Analysis & Forecast (`cmems_mod_glo_phy_anfc_0.083deg_PT1H-m`) | Multi-altimetry + satellite SST + in-situ Argo profiling floats | 1/12° (~9 km) | `copernicusmarine` CLI / OPeNDAP client | [CMEMS Dataset Viewer (PHY)](https://data.marine.copernicus.eu/viewer/expert?view=datasetServices&dataset=GLOBAL_ANALYSISFORECAST_PHY_001_024&utm_source=gemini) | ✅ Live | [copernicus_adapter.py](file:///d:/Jaljeev/backend/app/tools/copernicus_adapter.py) |
| **2b** | **Copernicus Marine (CMEMS)** | Global Biogeochemistry Analysis & Forecast (`cmems_mod_glo_bgc-pft_anfc_0.25deg_P1D-m`) | OLCI (Sentinel-3) + MODIS-Aqua + VIIRS ocean-colour composite | 1/4° (~25 km) | `copernicusmarine` client | [CMEMS Dataset / Earth Engine Catalog (BGC)](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_MARINE_GLOBAL_ANALYSISFORECAST_BGC_001_028_PFT?utm_source=gemini&authuser=1) | ✅ Live | [copernicus_adapter.py](file:///d:/Jaljeev/backend/app/tools/copernicus_adapter.py) |
| **3** | **Open-Meteo Marine** | Marine Wave, Swell & Sea-State API | ECMWF / NOAA WaveWatch III assimilating radar altimetry | ~25 km | REST JSON API | [Open-Meteo Marine Weather API](https://open-meteo.com/en/docs/marine-weather-api?utm_source=gemini) | ✅ Live (Workhorse) | [open_meteo_adapter.py](file:///d:/Jaljeev/backend/app/tools/open_meteo_adapter.py) |
| **4** | **Open-Meteo Weather** | Global Atmospheric Weather Forecast API | ECMWF Integrated Forecasting System (IFS) & NOAA GFS Blend | 11 km | REST JSON API | [Open-Meteo General API](https://open-meteo.com/?utm_source=gemini) | ✅ Live (Workhorse) | [open_meteo_adapter.py](file:///d:/Jaljeev/backend/app/tools/open_meteo_adapter.py) |
| **5** | **NOAA NCEI CoastWatch** | Daily Optimum Interpolation SST (OISST v2.1, `ncdcOisst21Agg_LonPM180`) | AVHRR Satellite blended with ships, drifting and moored buoys | 1/4° (~25 km) | ERDDAP GridDAP protocol | [NOAA CoastWatch ERDDAP Server](https://coastwatch.noaa.gov/cwn/data-access-tools/erddap-noaa-coastwatch.html?utm_source=gemini) | ✅ Live | [noaa_oisst_adapter.py](file:///d:/Jaljeev/backend/app/tools/noaa_oisst_adapter.py) |
| **6** | **INCOIS** | Ocean State Forecast (OSF) Wave & Swell | WAM / SWAN numerical wave model suite | ~12 km | ERDDAP GridDAP (`incois_osf_wave`) | [INCOIS Ocean Services / OSF Portal](https://incois.gov.in/oceanservices/osf_w.jsp?utm_source=gemini) | ⚠️ SSL cert issues (Fallback active) | [incois_adapter.py](file:///d:/Jaljeev/backend/app/tools/incois_adapter.py) |
| **7** | **IMD** | City & Coastal Weather Forecast | IMD Automatic Weather Station (AWS) network + NWP regional models | ~12 km | REST JSON API (`city.imd.gov.in/api`) | [IMD Official Mausam Portal](https://mausam.imd.gov.in/?utm_source=gemini) | ⬜ Pending Key Activation | [imd_adapter.py](file:///d:/Jaljeev/backend/app/tools/imd_adapter.py) |
| **8** | **DGFI-TUM / SEANOE** | EOT20 (Empirical Ocean Tide Model 2020) | 17 Harmonic tidal constituents derived from 28-yr multi-satellite altimetry | ~0.125° (~14 km) | Local NetCDF harmonic engine via `pyTMD` | [SEANOE Data Repository for EOT20](https://www.seanoe.org/data/00683/79489/?utm_source=gemini) | ✅ Live (Zero Latency) | [tide_adapter.py](file:///d:/Jaljeev/backend/app/tools/tide_adapter.py) |
| **9** | **GEBCO / BODC** | GEBCO_2026 Global Terrain Grid | Shipborne multibeam sonar compiled with satellite-derived bathymetry | 15 arc-sec (~450 m) | OPeNDAP (CEDA/BODC THREDDS server) | [GEBCO Gridded Bathymetry Data](https://www.gebco.net/data_and_products/gridded_bathymetry_data/?utm_source=gemini) | ✅ Live (Regional Tiles) | [bathymetry_adapter.py](file:///d:/Jaljeev/backend/app/tools/bathymetry_adapter.py) |
| **10** | **Marine Regions** | World EEZ v12 & Territorial Waters (12NM) | Delineated UNCLOS maritime boundaries & boundaries treaty database | Vector Polygons | PostGIS Spatial Database / GeoPackage | [Zenodo / Marine Regions v12 Data Repository](https://zenodo.org/records/16314546?utm_source=gemini) | ✅ Live in PostGIS | [load_boundaries.py](file:///d:/Jaljeev/scripts/load_boundaries.py) |
| **11** | **UNEP-WCMC** | World Database on Protected Areas (WDPA & WD-OECM) | Marine Protected Area (MPA) designations and boundaries | Vector Polygons | REST API v4 (`api.protectedplanet.net`) + Shapefiles | [Protected Planet / World Database on Protected Areas (WDPA)](https://www.protectedplanet.net/en/thematic-areas/marine-protected-areas?utm_source=gemini) | ✅ Live Adapter + PostGIS fallback | [protected_planet_adapter.py](file:///d:/Jaljeev/backend/app/tools/protected_planet_adapter.py) |
| **12** | **Global Fishing Watch (GFW)** | GFW Vessel Identity & Daily/Monthly Fishing Effort | Terrestrial & Satellite Automatic Identification System (AIS) | 0.01° / 0.1° | Bulk CSV Archive / Zenodo (`14982712`) | [GFW Datasets and Code Portal](https://globalfishingwatch.org/datasets-and-code-vessel-identity/?utm_source=gemini) | ✅ Pipeline Ready | [download_public.py](file:///d:/Jaljeev/scripts/download_public.py) |
| **13** | **ECMWF / Copernicus CDS** | ERA5 Atmospheric Reanalysis | 4D-Var Data Assimilated Global Atmospheric Reanalysis | 0.25° (~31 km) | CDS API (`cdsapi` client) | [Copernicus Climate Data Store (ERA5 on Single Levels)](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?utm_source=gemini) | ✅ Bulk Ingestion Ready | [era5_2023.py](file:///d:/Jaljeev/scripts/era5_2023.py) |
| **14** | **NOAA NCEI** | IBTrACS v04r01 (Tropical Cyclones) | Multi-agency official tropical cyclone best-track historical archive | Vector Tracks | Direct CSV / Google Earth Engine | [IBTrACS Catalog / Data Access](https://developers.google.com/earth-engine/datasets/catalog/NOAA_IBTrACS_v4?utm_source=gemini&authuser=1) | ✅ Downloaded | [download_public.py](file:///d:/Jaljeev/scripts/download_public.py) |
| **14b** | **NOAA NCEI** | World Ocean Atlas 2023 (WOA23) | Quality-controlled in-situ CTD, XBT, and Argo profiling float profiles | 1.00° / 0.25° | Direct NetCDF HTTP download | [NOAA NCEI WOA23 Data Access](https://www.ncei.noaa.gov/access/world-ocean-atlas-2023/?utm_source=gemini) | ✅ Ingestion Script Ready | [download_public.py](file:///d:/Jaljeev/scripts/download_public.py) |
| **15** | **OpenStreetMap / Nominatim** | Nominatim Geocoding Search Service | Collaborative OpenStreetMap geospatial database | Point Coordinates | REST API | [Nominatim API Portal](https://nominatim.org/?utm_source=gemini) | ✅ Live | [geocode_adapter.py](file:///d:/Jaljeev/backend/app/tools/geocode_adapter.py) |
| **16** | **Natural Earth** | 1:50m Physical Land Polygons | Public Domain Cartographic Vector Coastlines | Vector Polygons | Bundled GeoJSON (`frontend/public/basemap/`) | [Natural Earth 1:50m Physical Vectors](https://www.naturalearthdata.com/downloads/50m-physical-vectors/?utm_source=gemini) | ✅ Bundled Offline | [fetch_basemap_land.py](file:///d:/Jaljeev/scripts/fetch_basemap_land.py) |

---

## 3. Detailed Data Acquisition Channels & Ingestion Mechanics

### 3.1 Satellite Ocean Color & Chlorophyll-a (ISRO MOSDAC EOS-06)
- **Primary Source:** ISRO MOSDAC [OCEANSAT-3 Mission Data Portal](https://www.mosdac.gov.in/oceansat-3?utm_source=gemini)
- **Product ID:** `E06OCM_L4_AC` (EOS-06 OCM-3 L4 Analyzed Chlorophyll).
- **Physical Context:** Chlorophyll-a concentration serves as the core biological indicator for phytoplankton blooms and Potential Fishing Zones (PFZs). It is generated by assimilating Ocean Colour Monitor (OCM-3) observations into a coupled physical-biogeochemical model (MOM5 + TOPAZ).
- **Acquisition Protocol:**
  1. Automated authentication handshake: `POST https://mosdac.gov.in/download_api/gettoken` delivering `access_token` and `refresh_token`.
  2. Granule search: `GET https://mosdac.gov.in/apios/datasets.json?datasetId=E06OCM_L4_AC` across recent date windows.
  3. Stream download: `GET https://mosdac.gov.in/download_api/download?id=<record_id>` streaming binary NetCDF to `data/raw/mosdac/`.
  4. Cached extraction: Local cache retention for 24 hours (`CACHE_MAX_AGE_HOURS = 24`) avoiding redundant bandwidth usage.

### 3.2 Physical Oceanography & Biogeochemistry (Copernicus Marine CMEMS)
- **Primary Source:** Copernicus Marine Service ([Physics Viewer](https://data.marine.copernicus.eu/viewer/expert?view=datasetServices&dataset=GLOBAL_ANALYSISFORECAST_PHY_001_024&utm_source=gemini) & [Biogeochemistry Catalog](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_MARINE_GLOBAL_ANALYSISFORECAST_BGC_001_028_PFT?utm_source=gemini&authuser=1))
- **Physics Variables:**
  - `thetao`: Sea water potential temperature (°C) at 0.5m depth.
  - `uo` & `vo`: Eastward & northward surface velocity components (m/s) for ocean current drift calculations.
  - `zos`: Sea surface height above geoid / sea level anomaly (m), identifying mesoscale cold/warm-core eddies.
  - `so`: Salinity in Practical Salinity Units (PSU).
- **Biogeochemistry Variables:**
  - `chl`: Phytoplankton mass concentration (mg/m³) used to track both pelagic feeding zones and red tide / Harmful Algal Blooms (HAB, triggered when `chl > 10.0 mg/m³`).
- **Concurrency & Memory Management:** Managed under process-wide semaphore bounds (`MAX_CONCURRENT_DATASET_OPENS = 2`) and strict thread isolation to prevent NetCDF/HDF5 interpreter segmentation faults.

### 3.3 Wave Dynamics, Swell & Surface Meteorology (Open-Meteo)
- **Primary Source:** Open-Meteo [Marine Weather API](https://open-meteo.com/en/docs/marine-weather-api?utm_source=gemini) & [General API](https://open-meteo.com/?utm_source=gemini)
- **Extracted Wave Variables:**
  - Total significant wave height (`wave_height`), wave period (`wave_period`), direction (`wave_direction`).
  - Swell separation: `swell_wave_height`, `swell_wave_period`, `swell_wave_direction`.
  - Wind-wave separation: `wind_wave_height`, `wind_wave_direction`.
- **Extracted Weather Variables:**
  - 10m wind speed (`wind_speed_10m`), wind gusts (`wind_gusts_10m`), wind direction (`wind_direction_10m`).
  - Rain rate (`precipitation` in mm/hr) and precipitation probability (`precipitation_probability`).
  - Mean sea level pressure (`pressure_msl`) and 3-hour barometric pressure trend (`pressure_trend_hpa_3h`) for rapid squall/storm detection.
  - Fog hazard calculation: `temperature_2m` - `dew_point_2m` (< 2.5°C threshold flags imminent coastal sea fog).
- **Time Offset Capability:** Ingestion supports `hour_offset = +N`, allowing the Counterfactual Simulation Agent to compute risks for future departure windows.

### 3.4 Satellite SST Consensus (NOAA CoastWatch OISST v2.1)
- **Primary Source:** NOAA NCEI CoastWatch [ERDDAP Server](https://coastwatch.noaa.gov/cwn/data-access-tools/erddap-noaa-coastwatch.html?utm_source=gemini)
- **Dataset ID:** `ncdcOisst21Agg_LonPM180`
- **Methodology:** Daily optimum interpolation combining AVHRR satellite measurements with surface observations from ships and buoys, adjusted for bias. Queried directly via GridDAP protocol and cached for 6 hours.

### 3.5 Regional Weather & Ocean State (IMD & INCOIS)
- **INCOIS:** [INCOIS Ocean Services / OSF Portal](https://incois.gov.in/oceanservices/osf_w.jsp?utm_source=gemini) provides high-resolution SWAN/WAM wave models along the Indian coastline.
- **IMD:** [IMD Official Mausam Portal](https://mausam.imd.gov.in/?utm_source=gemini) provides official meteorological warnings, coastal station readings, and cyclone bulletins.

### 3.6 Hydrodynamic Tidal Constituent Engine (EOT20)
- **Primary Source:** DGFI-TUM / [SEANOE Data Repository for EOT20](https://www.seanoe.org/data/00683/79489/?utm_source=gemini)
- **Structure:** 17 global NetCDF constituent grid files (`2N2`, `J1`, `K1`, `K2`, `M2`, `M4`, `MF`, `MM`, `N2`, `O1`, `P1`, `Q1`, `S1`, `S2`, `SA`, `SSA`, `T2`) spanning 2.2 GB.
- **Latency Optimization:** Computes an entire 28-hour time series in one multi-offset call, cached in Redis for 12 hours. Lookups are executed via local mathematical spline interpolation in sub-milliseconds.

### 3.7 Bathymetric Soundings & Under-Keel Safety (GEBCO 2026)
- **Primary Source:** BODC / [GEBCO Gridded Bathymetry Data](https://www.gebco.net/data_and_products/gridded_bathymetry_data/?utm_source=gemini)
- **Resolution:** 15 arc-seconds (~450 meters).
- **Ingestion Technique:** Downloaded as small regional 1° × 1° tiles (Puri, Paradip, Gopalpur, Visakhapatnam, Chennai, Kochi) from CEDA THREDDS OPeNDAP servers. Filtered with a strict validation gate (`MIN_NONZERO_FRACTION = 0.85`) to guarantee no corrupted zero-elevation transfers corrupt marine navigation.

### 3.8 Maritime Governance & International Geofencing
- **Marine Regions EEZ v12:** [Zenodo / Marine Regions v12 Data Repository](https://zenodo.org/records/16314546?utm_source=gemini) provides UNCLOS Exclusive Economic Zone polygons and territorial sea boundaries, ingested into PostGIS (`eez_boundaries`) with a 5 km buffer alerting fishermen before crossing international waters.
- **Protected Planet (WDPA):** UNEP-WCMC [Protected Planet / World Database on Protected Areas](https://www.protectedplanet.net/en/thematic-areas/marine-protected-areas?utm_source=gemini) supplies official Marine Protected Areas (MPAs) and no-take conservation zones, accessed via REST API v4 and PostGIS tables.

### 3.9 Historical ML Training & Benchmarking Datasets
- **Global Fishing Watch (GFW):** [GFW Datasets and Code Portal](https://globalfishingwatch.org/datasets-and-code-vessel-identity/?utm_source=gemini) supplies 2012–2024 global vessel identities and gridded AIS fishing hours (Zenodo `14982712`).
- **ECMWF ERA5 Reanalysis:** [Copernicus Climate Data Store](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?utm_source=gemini) full 2023 hourly atmospheric reanalysis across the Indian Ocean basin `[25°N, 65°E, 0°N, 100°E]`.
- **NOAA IBTrACS v04r01:** [IBTrACS Catalog / Data Access](https://developers.google.com/earth-engine/datasets/catalog/NOAA_IBTrACS_v4?utm_source=gemini&authuser=1) tropical cyclone best tracks.
- **NOAA World Ocean Atlas (WOA23):** [NOAA NCEI WOA23 Data Access](https://www.ncei.noaa.gov/access/world-ocean-atlas-2023/?utm_source=gemini) decadal climatological temperature, salinity, and nutrient profiles.
- **OpenStreetMap Nominatim:** [Nominatim API Portal](https://nominatim.org/?utm_source=gemini) for geocoding fishing village queries.
- **Natural Earth 1:50m Vectors:** [Natural Earth 1:50m Physical Vectors](https://www.naturalearthdata.com/downloads/50m-physical-vectors/?utm_source=gemini) bundled offline on the frontend as a static basemap.

---

## 4. Multi-Source Consensus & Fallback Architecture

To ensure uninterrupted safety guidance at sea, the data pipeline enforces multi-tiered fallback hierarchies for every variable:

```
[Wave Height & Swell]
  ├─ Tier 1: INCOIS OSF (ERDDAP)
  ├─ Tier 2: Copernicus Marine (Physics model)
  └─ Tier 3: Open-Meteo Marine (ECMWF/WW3) [Active Workhorse]

[Sea Surface Temperature (SST)]
  ├─ Tier 1: NOAA OISST v2.1 (Satellite + In-situ)
  ├─ Tier 2: Copernicus Marine Physics (Analysis/Forecast)
  └─ Tier 3: ISRO MOSDAC (EOS-06 OCM-3)

[Chlorophyll-a & HAB Risk]
  ├─ Tier 1: ISRO MOSDAC (EOS-06 OCM-3 L4 AC)
  └─ Tier 2: Copernicus Marine (GlobColour BGC PFT)

[Surface Meteorology & Squall Tracking]
  ├─ Tier 1: IMD Regional API (Coastal stations)
  └─ Tier 2: Open-Meteo Forecast (ECMWF IFS / GFS Blend)

[Tidal Soundings]
  └─ Tier 1: EOT20 Empirical Tide Model (Local 28-hr harmonic spline)

[Seafloor Depth & Bathymetry]
  └─ Tier 1: GEBCO 2026 (Regional High-Res Tiles in PostGIS / NumPy)

[Maritime Boundaries & MPA Zones]
  ├─ Tier 1: PostGIS Pre-Loaded EEZ & Territorial Waters (Marine Regions)
  └─ Tier 2: Protected Planet API v4 (Live Shapely Polygon Fallback)
```

---

## 5. Storage Directory Structure

```
data/
├── raw/                              # Immutable raw downloaded assets
│   ├── basemap/                      # Natural Earth 50m land vector
│   ├── boundaries/                   # Marine Regions EEZ & territorial seas
│   │   ├── eez/
│   │   └── protected_planet/         # WDPA shapefiles
│   ├── gebco/                        # Regional GEBCO 2026 tiles (~1° x 1°)
│   │   └── regions/                  # vizag.nc, puri.nc, paradip.nc, etc.
│   ├── gfw/                          # GFW vessel registry & AIS effort CSVs
│   ├── ibtracs/                      # IBTrACS North Indian Ocean cyclone archive
│   ├── mosdac/                       # EOS-06 OCM-3 NetCDF cache
│   ├── oisst/                        # NOAA OISST annual NetCDF subsets
│   ├── tides/                        # EOT20 17 NetCDF constituent files
│   └── woa23/                        # World Ocean Atlas climatologies
├── interim/                          # Regridded and cropped intermediary matrices
└── processed/                        # H3-indexed training features & SST climatology
    ├── features_2023.parquet
    └── sst_climatology.parquet
```

---

*Report prepared by Team Felix, KIIT University, Bhubaneswar*  
*SIH Problem Statement: SIH26176 (ISRO)*
