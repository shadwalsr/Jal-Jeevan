# JalJeev — Agentic Marine Intelligence System
### Smart India Hackathon 2026 | SIH26176 (ISRO) | formerly "ORCA"

JalJeev turns India's authoritative ocean/weather/satellite data (INCOIS, IMD,
ISRO MOSDAC, Copernicus, NASA) into explainable, evidence-backed decisions for
fishermen, disaster managers, coast guard, and researchers — in regional
languages, online or offline. Full requirements: [ORCA_PRD_SIH26176_v2.md](ORCA_PRD_SIH26176_v2.md).

This repo is the working codebase, scaffolded Phase-0 / Week-1 per the PRD roadmap (Section 28).

---

## Quick start (once you've filled in `.env`)

```bash
cp .env.example .env
docker compose up -d postgres redis minio
docker compose up backend
```

Then check `http://localhost:8000/health`.

---

## Repo layout

```
backend/app/
  agents/     # LangGraph agent nodes (Weather, Ocean, Fishing, Geo, Risk, ...)
  tools/      # Deterministic data-source adapters (INCOIS, IMD, MOSDAC, ...)
  models/     # Pydantic dataclasses (WeatherState, OceanState, RiskState, ...)
  db/         # SQLAlchemy models, session management
  ml/         # XGBoost fishing model, anomaly detector, training scripts
  api/        # FastAPI routers
  core/       # config, celery app, logging
infra/sql/    # schema migrations (raw SQL for Phase 0, Alembic later)
frontend/     # React + TS + Vite + MapLibre + deck.gl (scaffolding next)
data/         # local raw/processed data cache (gitignored)
```

---

## PHASED PLAN (from PRD Section 28, mapped to concrete deliverables)

### Phase 0 — Internal Round (now → 20 Sep 2026)
- **Week 1** (done in this session): repo scaffold, docker-compose (Postgres+PostGIS, Redis, MinIO), DB schema, INCOIS + IMD adapter templates.
  - **Next:** verify real INCOIS ERDDAP dataset IDs, get IMD/MOSDAC keys wired in, first Celery ingestion job.
- **Week 2:** Weather + Ocean agents (deterministic, no LLM yet), `/chat` endpoint, basic React chat UI.
- **Week 3:** EEZ/MPA boundaries into PostGIS, Geo Agent, map with PFZ overlay, Risk Agent v1.
- **Week 4:** Evidence panel UI, LangGraph orchestrator, Hindi + Odia support, demo recording, submission.

### Phase 1 — Oct: Fishing + ML + full orchestration
Fishing Agent (MOSDAC PFZ, chlorophyll), XGBoost suitability model trained on INCOIS PFZ archive 2003–2025, full LangGraph multi-agent orchestration, GFW integration.

### Phase 2 — Nov: Simulation + Anomaly + Route + UX
Counterfactual "what-if" engine, anomaly detection (Isolation Forest + Z-score), A* route optimizer on H3 grid, uncertainty engine, evidence graph UI, remaining languages.

### Phase 3 — Late Nov–Dec: Polish + demo prep
PWA offline mode, voice I/O (Odia/Tamil/Hindi), proactive alerts, 5 stakeholder modes, demo rehearsal.

---

## YOUR ROLE (what only you can do)

I (Claude) can write the code, agents, ML pipeline, and UI. I **cannot**:

1. **Register accounts / obtain API keys** — these require a real identity, email verification, and sometimes institutional affiliation (KIIT). I can't do this for you.
2. **Make product/scope decisions** that trade off timeline vs. features (e.g., "do we build 10 languages or 3 well").
3. **Provide domain sign-off** — confirm that risk thresholds, vessel classes, and PFZ interpretation make sense to an actual fisherman/domain reviewer.
4. **Run the actual SIH submission logistics** — team registration, PPT/video upload, presenting to judges.
5. **Test voice/language output** for correctness (I can generate it, but a native speaker should verify Odia/Tamil TTS output makes sense).

### Concretely, your action items this week:

| # | Action | Where | Time to activate |
|---|---|---|---|
| 1 | Register ISRO MOSDAC | https://www.mosdac.gov.in → Register | 1–2 days |
| 2 | Register IMD API access | https://mausam.imd.gov.in (or contact IMD for API access) | 1–3 days |
| 3 | Register Copernicus Marine | https://marine.copernicus.eu → Register | same day |
| 4 | Register Copernicus CDS (ERA5) | https://cds.climate.copernicus.eu → Register, generate API key | same day |
| 5 | Register NASA Earthdata | https://urs.earthdata.nasa.gov → Register | same day |
| 6 | Register Protected Planet API key | https://api.protectedplanet.net (mention research/hackathon use) | 2–5 days |
| 7 | Register Global Fishing Watch | https://globalfishingwatch.org/our-apis (research account) | 3–7 days |
| 8 | Get a Gemini API key | https://aistudio.google.com/apikey (free tier) | immediate |

**Do this today** — several take multiple days to activate and Week 2 work depends on them.
Once you have keys, paste them into your local `.env` (never commit it) or send them to me
in this session and I'll wire them in.

Sources that need **no registration** (already wired into adapters or ready to be): INCOIS ERDDAP,
NOAA OISST, Argo GDAC, HYCOM, Marine Regions EEZ, GEBCO bathymetry, Open-Meteo Marine, GBIF.

---

## DATASETS — what & where

### Tier 1 — Core (fetch via API, not one-time download)
| Dataset | Source | Fetch method |
|---|---|---|
| SST, chlorophyll, ocean colour, winds, PFZ advisory | ISRO MOSDAC | MOSDAC Download API (after registration) |
| Wave height/period, swell, currents, SST, tides, MLD, D20 | INCOIS OSF | ERDDAP: `erddap.incois.gov.in/erddap` (no auth) |
| PFZ advisory archive 2003–2025 | INCOIS PFZ portal | Bulk archive — needed for ML training labels |
| Cyclone track, lightning, rainfall, weather forecast | IMD | API (after registration) |
| Physics reanalysis, waves, biogeochemistry | Copernicus Marine | `copernicusmarine` Python toolbox (after registration) |
| Historical atmospheric reanalysis | ERA5 (Copernicus CDS) | `cdsapi` Python client (after registration) |
| Global daily SST 1981–present | NOAA OISST v2.1 | NOAA ERDDAP (no auth) |
| Float profiles (T/S/BGC) | Argo GDAC | `argo.ucsd.edu/data` or Argovis API (no auth) |
| Chlorophyll/ocean colour (global) | NASA OceanColor | `oceandata.sci.gsfc.nasa.gov` (after Earthdata login) |

### Tier 2 — Geospatial / boundaries (one-time download, load into PostGIS)
| Dataset | Source |
|---|---|
| EEZ, territorial seas, internal waters | Marine Regions World EEZ v12 — `marineregions.org/downloads.php` |
| Marine Protected Areas / OECMs | Protected Planet API — `api.protectedplanet.net` |
| Global bathymetry | GEBCO 2026 — `gebco.net/data-and-products` |

### Tier 3 — Differentiators (optional but high value)
| Dataset | Source |
|---|---|
| Historical fishing effort / AIS activity | Global Fishing Watch — `globalfishingwatch.org/our-apis` |
| Species occurrence | GBIF/OBIS — `api.gbif.org` (no auth) |
| Third independent wave/wind source | Open-Meteo Marine — `api.open-meteo.com/v1/marine` (no auth) |

Full table with notes: PRD Section 9; registration timing: PRD Section 34 (Appendix B).

---

## What I've built so far (this session)

- Project scaffold: `backend/`, `frontend/`, `infra/`, `data/`
- `docker-compose.yml`: Postgres+PostGIS, Redis, MinIO, backend, Celery worker/beat
- `.env.example` with every credential the PRD requires, annotated with where to get it
- Initial DB schema (`infra/sql/001_init_schema.sql`): users, vessel_profiles, h3_marine_states, ingestion_log, decisions (audit trail)
- FastAPI skeleton (`backend/app/main.py`) with `/health` and two debug endpoints
- Two working adapter templates: INCOIS ERDDAP (no-auth) and IMD (needs your API key)

## What's next (once you send API keys / confirm)

1. Verify the real INCOIS ERDDAP `dataset_id` against the live catalog (placeholder used for now)
2. Wire MOSDAC + Copernicus Marine adapters
3. Build the Weather + Ocean deterministic agents and a working `/chat` endpoint
4. Stand up the React + MapLibre frontend skeleton
