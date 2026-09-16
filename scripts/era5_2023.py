"""
ERA5 reanalysis download via CDS API — Indian Ocean bbox, 2023, 6-hourly.
Requires CDS_API_KEY in .env (already configured) — this script reads the
key from .cdsapirc, so also run: see DATA_ACQUISITION.md for the one-time
~/.cdsapirc setup step (mirrors what's already in .env, cdsapi's client
doesn't read .env directly).

Note: lightning_flash_density is intentionally excluded — not offered by
the ERA5 single-levels download form.
"""
import calendar
from pathlib import Path

import cdsapi

REPO_ROOT = Path(__file__).resolve().parent.parent
out = REPO_ROOT / "data" / "raw" / "era5"
out.mkdir(parents=True, exist_ok=True)
client = cdsapi.Client()

for month in range(1, 13):
    target = out / f"era5_2023_{month:02d}.nc"
    if target.exists():
        continue

    days = [f"{d:02d}" for d in range(1, calendar.monthrange(2023, month)[1] + 1)]

    client.retrieve(
        "reanalysis-era5-single-levels",
        {
            "product_type": ["reanalysis"],
            "variable": [
                "10m_u_component_of_wind",
                "10m_v_component_of_wind",
                "instantaneous_10m_wind_gust",
                "mean_sea_level_pressure",
                "total_precipitation",
                "sea_surface_temperature",
            ],
            "year": ["2023"],
            "month": [f"{month:02d}"],
            "day": days,
            "time": ["00:00", "06:00", "12:00", "18:00"],
            "area": [25, 65, 0, 100],
            "data_format": "netcdf",
            "download_format": "unarchived",
        },
        str(target),
    )
