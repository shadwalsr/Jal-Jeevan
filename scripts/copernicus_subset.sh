#!/usr/bin/env bash
# JalJeev — Copernicus Marine bulk subsets for the Indian Ocean bbox (2023).
# Requires `copernicusmarine login` once (uses the username/password already
# in .env — run: copernicusmarine login  and paste them when prompted).
# Run one command at a time if bandwidth/quota is a concern.
set -e
OUT=data/raw/copernicus
mkdir -p "$OUT"

# Ocean temperature, currents, salinity
copernicusmarine subset -i cmems_mod_glo_phy_my_0.083deg_P1D-m \
  -v thetao -v so -v uo -v vo \
  -x 65 -X 100 -y 0 -Y 25 -z 0 -Z 1 \
  -t 2023-01-01 -T 2023-12-31 \
  -o "$OUT" -f physics_3d_2023.nc

# Sea level and mixed-layer depth
copernicusmarine subset -i cmems_mod_glo_phy_my_0.083deg_P1D-m \
  -v zos -v mlotst \
  -x 65 -X 100 -y 0 -Y 25 \
  -t 2023-01-01 -T 2023-12-31 \
  -o "$OUT" -f physics_surface_2023.nc

# Chlorophyll, NPP, oxygen, nitrate (biogeochemistry)
copernicusmarine subset -i cmems_mod_glo_bgc_my_0.25deg_P1D-m \
  -v chl -v nppv -v no3 -v o2 \
  -x 65 -X 100 -y 0 -Y 25 -z 0 -Z 1 \
  -t 2023-01-01 -T 2023-12-31 \
  -o "$OUT" -f bgc_2023.nc

# Waves and swell
copernicusmarine subset -i cmems_mod_glo_wav_my_0.2deg_PT3H-i \
  -v VHM0 -v VTPK -v VMDR -v VHM0_SW1 \
  -x 65 -X 100 -y 0 -Y 25 \
  -t 2023-01-01 -T 2023-12-31 \
  -o "$OUT" -f waves_2023.nc

# Altimetry and geostrophic currents
copernicusmarine subset -i cmems_obs-sl_glo_phy-ssh_my_allsat-l4-duacs-0.125deg_P1D \
  -v sla -v adt -v ugos -v vgos \
  -x 65 -X 100 -y 0 -Y 25 \
  -t 2023-01-01 -T 2023-12-31 \
  -o "$OUT" -f altimetry_2023.nc

echo "Done. To pull additional years, copy a block above and change -t/-T and the output filename."
