# JalJeev — Data Acquisition Plan

Answers: how to download training/reference data, where from, and how much.

## The metric correction

Don't target "90% accuracy" for the Fishing Suitability model — PFZ is a
heavily imbalanced binary classification (most cells, most days, are NOT a
PFZ), so a trivial always-predict-no model can already look like >90%
"accuracy" while being useless. Use the PRD's real targets instead
(PRD Section 11.1):
- **AUC-ROC > 0.82**
- **Precision@0.5 > 0.75**
- **Recall@0.5 > 0.70**

## Size estimate (Indian Ocean bbox: 65–100°E, 0–25°N)

| Source | Years | Approx size | Status |
|---|---|---|---|
| Copernicus physics (T/S/currents) | 2023 (extend later) | ~2–4 GB/yr | Script ready |
| Copernicus BGC (chl/O2/NO3/NPP) | 2023 | ~1–2 GB/yr | Script ready |
| Copernicus waves | 2023 | ~0.5–1 GB/yr | Script ready |
| Copernicus altimetry | 2023 | ~0.5–1 GB/yr | Script ready |
| ERA5 (wind/pressure/precip/SST) | 2023 | ~1–2 GB/yr | Script ready |
| OISST SST | 2010–2023 (14 yrs) | ~1–2 GB total | Script ready |
| WOA23 climatologies | static | ~1 GB | Script ready |
| GEBCO bathymetry (regional) | static | ~0.3 GB | Manual (see below) |
| Marine Regions EEZ | static | ~0.1 GB | Manual |
| Protected Planet MPAs | static | ~0.2 GB | Manual |
| GFW fishing effort | 2012–2024 | ~10–20 GB raw (global; regional filter after download shrinks to ~2 GB) | Script ready |
| IBTrACS cyclone tracks | full archive | <10 MB | Script ready |
| **INCOIS PFZ archive 2003–2025** (the actual ML labels) | 22 yrs | Small (polygon advisories) but **not a bulk public download** — needs MOSDAC/INCOIS access | Blocked on MOSDAC approval |

**Total for one representative year (2023) across all Copernicus/ERA5/static sources: ~10–15 GB.**
**Extending Copernicus + ERA5 back to 2015 (8 more years) adds roughly another 40–60 GB.**
Start with 2023 to get the pipeline working end-to-end, then backfill more years once the pipeline is proven — don't download a decade blind.

The one genuinely irreplaceable piece is the **INCOIS PFZ archive** — everything else in this table is a *feature*, not a *label*. Without PFZ history there's no ground truth to train the suitability classifier against, regardless of how much Copernicus/ERA5 data you have. Everything else can substitute a public source; PFZ history cannot.

## How to run it

1. **Public bulk downloads** (no login needed):
   ```bash
   cd D:/Jaljeev
   source backend/.venv/Scripts/activate   # reuse the backend venv, or make a scripts venv
   pip install requests pandas pyarrow xarray netCDF4 h5netcdf pydap argopy
   python scripts/download_public.py
   ```
   Downloads IBTrACS, GFW effort archive, WOA23 climatologies, OISST regional subsets. Safe to re-run — skips existing files.

2. **Copernicus Marine** (your login already in `.env`):
   ```bash
   copernicusmarine login   # paste gsingh12345 / your password once
   bash scripts/copernicus_subset.sh
   ```

3. **ERA5** (`~/.cdsapirc` already created from your CDS key):
   ```bash
   python scripts/era5_2023.py
   ```

4. **Manual downloads** (GUI required, ~10 min):
   - GEBCO 2026 bathymetry: https://download.gebco.net — bbox 65/100/0/25, NetCDF → `data/raw/gebco/gebco_2026_india.nc`
   - Marine Regions EEZ: https://www.marineregions.org/downloads.php — World EEZ v12 (GeoPackage) → `data/raw/boundaries/`
   - Protected Planet: https://www.protectedplanet.net — non-commercial shapefile → `data/raw/boundaries/protected_planet/`

## Storage rules (already reflected in `.gitignore`)
```
data/raw/       # never edit, never commit
data/interim/   # cropped/regridded
data/processed/ # H3-indexed Parquet training tables
```
Keep files compressed (NetCDF zlib, ZIP). Don't build one giant master Parquet — partition by source/year/month.

## Tide model (added 25 Aug 2026)

**EOT20** (DGFI-TUM Empirical Ocean Tide model 2020) via the open-source `pyTMD`
library. Chosen over FES2014/TPXO because it's freely downloadable with no
registration wall — direct link from its DOI (10.17882/79489) resolves to
SEANOE, a public French ocean-data repository.

```bash
mkdir -p data/raw/tides
# 2.2 GB — harmonic constituent grids (17 tidal constituents, global)
curl -L -o data/raw/tides/EOT20.zip https://www.seanoe.org/data/00683/79489/data/85762.zip
cd data/raw/tides && unzip EOT20.zip && cd ../../..
```

This predicts **astronomical tide only** (moon/sun-driven) — not storm surge,
which is a separate, still-unmodeled hazard. Wired into `app/tools/tide_adapter.py`
and consumed by the Ocean Agent; reported in `OceanState.tide_height_m` /
`tide_state` ("rising"/"falling"/"high"/"low"). Currently informational only in
the Risk Agent — scoring real bar-crossing risk needs bathymetry (GEBCO, still
not loaded) to know harbour depth relative to tide height.

## What I have not done yet
I have not executed any of these downloads — they're tens of GB and will take a while. Tell me to go ahead (I'll run it in the background and report progress), or run them yourself with the commands above.
