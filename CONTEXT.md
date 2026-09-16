# CONTEXT.md — JalJeev (SIH26176 / formerly "ORCA")

> **Purpose of this file**: hand this single file to any other AI/human and
> they should understand what JalJeev is, why it exists, how it is built,
> what is done vs. not done, and every non-obvious decision baked into it —
> without needing to read the code first. It is mutually exclusive with
> [DESIGN.md](DESIGN.md): this file is the **what/why/status**, DESIGN.md is
> the **how it computes and how it's shown**. Read this one first.

---

## 1. One-paragraph summary

JalJeev is an agentic marine decision-support system built for **Smart India
Hackathon problem statement 26176** (issued by ISRO). It takes a natural-
language question from a fisherman, sailor, or maritime trade operator
("Is it safe to go out near Kochi today?", "Plan my passage from Kochi to
Kakinada"), fuses live ocean/weather/satellite data from multiple real
government and scientific sources, runs it through a deterministic
hard-constraint-then-score risk pipeline tuned to the asker's actual vessel
class, and returns an explainable, evidence-backed answer in text or voice —
in Indian regional languages, and even when the LLM or network is
unavailable. It is not a weather app: it is a decision engine that says
**go / don't go / go with caution, and exactly why**, with every number
traceable to a real source.

## 2. Who it's for (three distinct user groups, one engine)

As of **28 Aug 2026** the system explicitly reasons about three user groups,
each mapped to real vessel classes (`app/agents/vessel_profiles.py`):

| Group | Example vessels | Central question | Central agent |
|---|---|---|---|
| **Fisherman** | 8m small boat, 18m mechanized trawler | "Is it safe near here, right now / today?" | Route Agent (radial scan) |
| **Sailor** | Cruising yacht, yacht with auxiliary engine, dhow | "Is there enough wind, and can I actually sail this course?" | Passage Agent, sail-specific risk factors |
| **Trader / commercial operator** | Coastal trader, general cargo, bulk carrier, tanker, container ship, passenger ferry | "Can I get this ship from Port A to Port B, and will it ground?" | Passage Agent, squat/UKC risk factors |

This was a deliberate mid-project pivot (28 Aug 2026): the system originally
assumed one implicit vessel (an 8m fishing boat) baked into every threshold.
It now takes a `vessel_class` parameter everywhere, resolved by
`resolve_vessel()` — a dictionary lookup with alias matching that degrades an
unrecognized class to the documented default (`fishing_small`) rather than
guessing or crashing.

## 3. Why it exists — the problem being solved

Indian small-craft fishermen, coastal sailors, and traders currently rely on
scattered, hard-to-interpret sources (raw IMD bulletins, generic weather
apps not tuned to marine hazards, word of mouth) to decide whether to go to
sea. Wrong calls cost lives (capsizing, being caught in cyclones) and money
(spoiled catch, grounded cargo, missed weather windows). JalJeev's job is to:

1. **Fuse** multiple authoritative data sources (never a single point of
   failure) into one coherent picture of a location/time.
2. **Score risk deterministically** against the specific vessel's real
   physical limits — not a generic "small boat" average.
3. **Explain** every recommendation with a traceable evidence receipt —
   never a black-box "unsafe" with no reason.
4. **Degrade gracefully** — never hang, never fabricate, never require an
   internet connection or a paid LLM subscription to produce a usable
   answer.
5. **Speak the user's language** — Indian regional languages, voice or text,
   online or offline.

## 4. Core philosophy (non-negotiable, drives every design decision)

- **The LLM never computes a number.** Wave height, risk scores, GIS
  intersections, route geometry — all deterministic Python/SQL. The LLM's
  only two jobs: (1) parse natural-language intent into structured
  parameters, (2) phrase a final answer from an evidence receipt it's
  handed. If an LLM is ever asked to estimate a physical value, that is a
  bug.
- **The LLM is optional, not a dependency.** Both LLM jobs have a real,
  tested, non-degraded fallback (`app/planner/rule_based.py`): a
  regex/keyword intent parser and a template-based answer renderer reading
  the same `EvidenceReceipt` directly. Engages automatically whenever
  `GROQ_API_KEY` is unset OR a live call fails (quota, network, anything).
  Verified live end-to-end with zero LLM calls: geocoding, all 5 marine
  agents, risk scoring, evidence aggregation, and answer rendering. The
  rule-based renderer is structurally incapable of hallucinating — it only
  ever repeats fields already present in the receipt.
- **Never fabricate data or results.** Every adapter that can't be verified
  (IMD — pending approval) returns an honest
  `{"status": "unavailable"}` rather than a plausible-looking guess. Real
  labels vs. synthetic placeholder labels are distinguished loudly in the ML
  pipeline; synthetic-label metrics are never reported as real results. The
  Anomaly Agent's SST baseline is explicitly labeled a single-year (2023)
  baseline, not a true multi-year climatology, in every response.
- **Graceful degradation over hanging or crashing.** Every external call has
  a timeout. A failed source falls back to another or reports the gap
  honestly (`missing: [...]`) rather than blocking or lying.
- **Hard constraints veto; soft constraints only rank.** Real, not
  aspirational, as of 26 Aug 2026 — see Section 7 below.

## 5. Problem statement origin

Built for **Smart India Hackathon 2026, problem statement SIH26176**, issued
by **ISRO**. Full formal requirements are in `ORCA_PRD_SIH26176_v2.md`
(3000+ lines) — that PRD is the source of truth for scope and long-term
roadmap; this file and DESIGN.md describe what's actually built today. The
project was originally named **"ORCA"** (still visible in the PRD filename
and some early scaffolding); it has since been renamed **JalJeev**.

## 6. Data sources (real, not fabricated)

| Source | What it provides | Status |
|---|---|---|
| Open-Meteo | Wind, wave, pressure, precipitation forecasts (7-day horizon) | **Live**, primary fallback for weather/ocean |
| Copernicus Marine | Physics/biogeochemistry/waves/altimetry | **Live** (username/password), full 2023 downloaded |
| ERA5 (CDS) | Reanalysis atmospheric data | **Live**, 12/12 months 2023 downloaded |
| NASA Earthdata | Satellite products | **Live** (bearer token — has a JWT expiry, regenerate from Earthdata profile if adapters start failing auth) |
| GFW (Global Fishing Watch) | Vessel identity + monthly fishing effort | **Live**, downloaded |
| EOT20 | Global harmonic tide model | **Live**, precomputed |
| GEBCO | Bathymetry (depth) | **Live**, but only small verified regional tiles (see gotcha in Section 11) |
| Marine Regions | EEZ boundaries | **Live**, loaded into PostGIS |
| WDPA | Marine Protected Area boundaries | **Live**, bbox-filtered to Indian Ocean, loaded into PostGIS |
| IBTrACS | Historical cyclone tracks | Downloaded |
| MOSDAC (ISRO) | EOS-06 OCM-3 L4 analyzed chlorophyll, satellite products | **Live** (Sep 2026) — downloads NetCDF via MOSDAC Download API. Note: PFZ advisories are on INCOIS, not MOSDAC. |
| IMD | Official Indian met bulletins | **Pending approval** — same pattern |
| Protected Planet | Marine Protected Areas API v4 (WDPA + WD-OECM) | **Live** (Sep 2026) — v4 API key configured, search, GeoJSON boundary retrieval, and live PostGIS sync active. |
| Groq (LLM) | Intent parsing + answer phrasing (optional) | **Live**, `openai/gpt-oss-120b` |

Full acquisition method and sizes for every dataset: `DATA_ACQUISITION.md`.

### The one dataset that matters most and isn't a bulk download
The INCOIS PFZ (Potential Fishing Zone) advisory archive (2003–2025) is the
actual training-label source for a real fishing-suitability model. It is
gated on **INCOIS portal access** (not MOSDAC — PFZ advisories are published
by INCOIS at incois.gov.in, not MOSDAC). **Nothing else substitutes for it**
— this is why the Fishing Agent (below) is the one PRD-roster agent not yet
built.

## 7. What's built vs. not built

### Built — 10 of 11 target agents (PRD roster)
Weather, Ocean, Geo, Risk, Route (v1 radial), Passage (A→B), Route Optimizer
(v2 A*), Validation/Critic, Simulation, Satellite Discovery, Anomaly
Detection, Context & Memory, Explanation & Evidence. (13 listed because Route
v1/v2 count as one PRD line item with two implementations, and
Satellite/Anomaly/Memory/Evidence are the PRD's 4 support agents alongside
the 6 domain agents + orchestrator — see DESIGN.md Section 2 for the exact
per-agent breakdown.)

### Not built
**Fishing Agent** — blocked on INCOIS PFZ label access (PFZ advisories are
published by INCOIS, not MOSDAC). MOSDAC access landed Sep 2026 and provides
L4 chlorophyll, but not PFZ. Revisit once INCOIS portal access is obtained.
This is the only functional gap against the PRD's target roster.

### Decision pipeline — real bug this fixed
Before 26 Aug 2026, risk scoring was a single flat additive score, so an MPA
violation contributed only +20 points — meaning a spot inside a protected
area could still return "LOW risk" if other factors were low. Fixed by
splitting into two stages:
- **Stage 1 — `check_hard_constraints()`**: MPA violation, certain-capsize
  wave height, out-of-range distance, insufficient depth vs. draft (with
  squat and tide corrections), on-land. Any hit → short-circuits straight to
  `risk_level="REJECTED"`, `factor_breakdown={}`. This is the single source
  of truth for vetoes — Route Agent's candidate scan and Route Optimizer's
  graph both call this exact function, never a separate inline copy.
- **Stage 2 — scoring**: only runs on survivors of Stage 1. 0–100 additive
  score, every point individually explainable via `factor_breakdown` +
  `explanation`.

Regression-tested in `backend/tests/test_risk_agent.py`.

## 8. Vessel-class-aware behavior (three genuinely different things, all deterministic)

1. **Sail: wind is a resource, not only a hazard.** A motor vessel in light
   wind is having a perfect day; a sailing vessel has no drive and no
   steerage. `becalmed` scores this (halved for a motor-sailer with an
   auxiliary engine) and is never a veto. `point_of_sail` scores a course
   inside the vessel's no-go angle, firing only when a course bearing is
   known (passage/routing paths only, never a bare point query). Motor
   vessels can never trigger either — sail fields are `None` on motor
   classes and every sail branch is guarded.
2. **Trade: squat and proportional under-keel clearance.** `squat_m()` uses
   Barrass's open-water approximation (`Cb·V²/100`, V in knots) — ~0.2m for
   a fishing boat, ~1.7m for a bulker at 14kn. Commercial vessels are held
   to 10% of static draft (PIANC-style) instead of the small-boat fixed 1m
   margin; the depth check subtracts the EOT20 tide when available. Tide is
   never assumed absent — no value means "charted depth only."
3. **Hard constraints remain the only vetoes** — everything above is Stage 2
   scoring except the depth/squat/UKC rule, which is Stage 1.

11 named vessel classes across 3 groups (`app/agents/vessel_profiles.py`):
`fishing_small` (8m, default), `fishing_mechanized` (18m trawler),
`sailing_yacht` (12m), `sailing_yacht_aux` (12m + engine), `dhow` (20m,
sail+motor trader), `coastal_trader` (40m), `general_cargo` (120m),
`bulk_carrier` (200m), `tanker` (250m), `container_ship` (300m),
`passenger_ferry` (60m). Numbers are representative class averages, not a
certified vessel database — every response says so.

## 9. Two distinct routing questions

- **Radial** ("where near me is it safe?") — the fisherman's question, no
  destination. `route_agent.py` (16-candidate scan, Open-Meteo, fast) +
  `route_optimizer.py` (A* to safest cell within a radius, H3 resolution 5).
- **Port-to-port** ("get me from Kochi to Kakinada and tell me when I
  arrive") — the sailor's/trader's question, previously impossible to ask.
  `passage_agent.py`, `/marine/passage`. Builds an H3 corridor along the
  great-circle track, dilated laterally so A* can route around hazards.
  Adaptive H3 resolution by distance (res 5 coastal / 4 regional / 3 ocean)
  with a hard cell budget. Scores each leg against the forecast hour the
  vessel actually arrives there (not departure conditions) — this required
  an iterative converge-on-tacking fix (28 Aug 2026) because tacking changes
  ETA and ETA determines which hour to score against. Anything past the
  7-day Open-Meteo horizon is flagged `beyond_forecast_horizon`, never
  silently filled in. Endpoints resolve from the ports table's harbour
  entrance coordinates, not the geocoder (a geocoded city name resolves to
  the city center, which is on land and correctly hard-vetoes).

## 10. Repo layout

```
CLAUDE.md                    Living project instructions (source this file is derived from)
ORCA_PRD_SIH26176_v2.md      Full formal PRD (3000+ lines) — architectural source of truth
README.md                    Quick-start + original repo layout (Phase-0 scaffolding era)
DATA_ACQUISITION.md          Every dataset: how fetched, size, re-fetch command
docker-compose.yml           Postgres+PostGIS, Redis, MinIO, backend, celery services
backend/
  app/
    agents/        11 built agents + vessel_profiles.py registry
    api/           FastAPI routers: marine.py (REST), chat.py (/chat NL endpoint)
    core/          config.py (env settings), cache.py (Redis, per-variable TTLs), decisions.py (audit log)
    db/            SQLAlchemy async session
    ml/            Feature engineering + XGBoost fishing-suitability training pipeline
    models/        schemas.py — shared Pydantic response shapes for every agent
    planner/       graph.py (LangGraph state machine), rule_based.py (LLM-free fallback)
    tools/         Adapters per external source + _executor.py (dedicated thread pool) + _circuit_breaker.py
  tests/           pytest suite, 93 tests: risk hierarchy, circuit breaker, rule-based planner,
                   vessel classes + class-aware risk, passage geometry
frontend/           React + Vite + TS + MapLibre — ChatPanel, MarineMap, EvidencePanel,
                    VesselSelector, PassagePanel; has a production build (frontend/dist/)
android/            Native Android app shell (Gradle/Kotlin project) — mobile client
design-canvas/      Claude Design canvas artboards (Main.dc.html, States.dc.html) — UI mockups/prototyping
scripts/            Data-acquisition + precompute: download_public.py, era5_2023.py,
                    copernicus_subset.sh, load_boundaries.py, build_sst_climatology.py, prewarm_demo.py
infra/sql/          Postgres schema + seed data (ports table)
data/
  raw/              Never edit — original downloads (Copernicus, ERA5, GFW, tides, boundaries, GEBCO tiles)
  processed/        Derived tables (H3-indexed features, SST climatology parquet)
  models/           Trained ML artifacts
docs/               (present, currently empty — reserved for generated documentation)
```

## 11. Known gotchas (operational landmines already hit and fixed)

1. **Never call multiple external sources sequentially inside one agent.**
   Must use `asyncio.gather`. A real bug of exactly `a, b, c = await x(), await y(), await z()`
   (looks concurrent, runs sequentially) was found and fixed in
   `planner/graph.py::execute_tools`.
2. **`asyncio.to_thread()` shares asyncio's own internal executor** — route
   blocking calls through the dedicated `network_executor`
   (`app/tools/_executor.py`). Confirmed live twice, including for the LLM
   call itself (a call that took 4-8s standalone consistently timed out via
   `asyncio.to_thread` under live server load; fixed by
   `loop.run_in_executor(network_executor, ...)`).
3. **Per-agent timeouts, not one timeout around the whole `gather()`.** One
   slow source (Copernicus) would otherwise discard fast successful results
   from the others. See `_run_with_timeout` in `app/api/marine.py`.
4. **Never swallow an exception without logging type + message.** A ~20s
   failure that looked like a hang across two debugging sessions turned out
   to be an instant `429 RESOURCE_EXHAUSTED` (Gemini's free-tier daily quota)
   hidden by a bare `except Exception: return None`. This is *why* Groq
   replaced Gemini as primary LLM.
5. **Windows: `taskkill //F //IM uvicorn.exe`** between test runs — a stale
   process on port 8000 causes silent connection-refused errors that look
   like a code bug.
6. Redis/Postgres cache TTLs are deliberately variable-specific
   (`app/core/cache.py::TTL_SECONDS`) — SST cached longer than wind because
   it changes more slowly. Don't collapse to one blanket TTL.
7. **A large single OPeNDAP request can silently truncate and zero-fill**
   with no error. An India-wide GEBCO bathymetry subset came back 96% zeros
   past the first ~200 rows, silently returning "0m / land" for every
   downstream depth lookup. Fix in `bathymetry_adapter.py`: fetch small
   ~1x1° regional tiles with an explicit >85% nonzero-fraction sanity check
   before saving. Only a handful of demo regions are loaded
   (`data/raw/gebco/regions/`); outside them returns `unavailable`, never a
   wrong depth.
8. **Puri's exact coastline is genuinely very shallow** (confirmed against
   live GEBCO — not a data bug): 0m depth extends tens of km offshore near
   the Mahanadi delta. Correctly hard-vetoes any normal small-boat draft.
   Use Visakhapatnam for demos (steeper shelf, verified ~40-56m a short
   distance out) — but the city *center* is on land, so use offshore
   coordinates, not the geocoded place name.
9. **Gemini → Groq (26 Aug 2026).** Not a technical failure of Gemini — its
   free tier's 20-requests/day quota was exhausted by dev testing, and (per
   gotcha 4) was mistaken for an async bug for a long time because the real
   exception was swallowed. Groq has a more generous free tier
   (~0.6s/trivial call). If Groq's quota is ever exhausted, the system falls
   through to `rule_based.py` automatically — that fallback is permanent
   infrastructure, not a stopgap.

## 12. Environment / secrets status (as of 26 Aug 2026)

- **Working**: Copernicus Marine, NASA Earthdata, CDS/ERA5, GFW, MOSDAC
  (EOS-06 OCM-3 chlorophyll), Groq (`GROQ_MODEL=openai/gpt-oss-120b`).
- **Pending approval, wired but inactive**: IMD, Protected Planet —
  their adapters short-circuit to `unavailable` until a key is dropped into
  `.env`, at which point they activate with zero other code changes.
- `GEMINI_API_KEY` still present in `.env` but unused by any code path —
  safe to remove.
- Real credentials live in `.env` (gitignored, never commit).
  `.env.example` documents every variable and where to get it.

## 13. Running it locally (operational reference)

Docker Desktop must be started **manually** first (no auto-start), then:
```bash
docker compose up -d postgres redis
```
Backend runs as a local process (not containerized) for faster iteration:
```bash
cd backend
source .venv/Scripts/activate   # Windows Git Bash; .venv/bin/activate on Linux/macOS
uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Postgres is on host port **5433** (not 5432 — another local project owns
5432 on this machine). Redis on standard 6379.

Frontend:
```bash
cd frontend
npm install   # first time only
npm run dev
```

Tests (fast, no network, no server needed):
```bash
cd backend && python -m pytest tests/ -v
```

Before a demo: run `python scripts/prewarm_demo.py` ~10-15 min ahead to warm
the Redis cache with real (not fabricated) responses so every query returns
in under a second instead of paying a cold Copernicus/tide fetch live. Best
verified demo point: 15-25km offshore Visakhapatnam (17.65, 83.35 /
17.6, 83.45), real ~40-56m depth, genuinely non-vetoed.

## 14. Testing status

93 pytest tests in `backend/tests/`, no network or server required: risk
hierarchy (hard constraints vs. scoring), circuit breaker, rule-based
planner, vessel classes + class-aware risk (`test_vessel_classes.py` — its
whole point is that the *same* sea produces different correct verdicts per
vessel class), passage geometry.

## 15. Conventions for anyone extending this codebase

- Every adapter function returns `{"status": ..., "source": ...}` at
  minimum — `"success"`, `"failed"`, or `"unavailable"` (the last means "not
  configured yet," not "tried and failed").
- Agents (not adapters) return the shared Pydantic schemas in
  `app/models/schemas.py`. Adapters return raw dicts; agents translate.
- A new legal/safety constraint → `risk_agent.py::check_hard_constraints`
  (Stage 1, vetoes). A new hazard/signal that should influence ranking among
  already-legal candidates → `factor_breakdown` (Stage 2), needs both a
  breakdown entry and an `explanation` line.
- No new external source without a timeout and documented fallback.
- Verify actual values landed (nonzero fraction, spot-check) before saving
  any large bulk geospatial/OPeNDAP fetch.
- Never swallow an exception silently in an adapter or LLM call — log or
  return `type(exc).__name__: exc`.
- New hard-coded logic in `rule_based.py` needs a test in
  `test_rule_based_planner.py` — it's the zero-dependency fallback, it must
  be trustworthy on its own merits.

## 16. Project naming note

The problem statement / PRD filename still says **"ORCA"** — this was the
project's working name before it was renamed **JalJeev**. Both names refer
to the same system; ORCA is not a separate or legacy product.

---
*For how the models, agents, and UI actually work end-to-end — pipeline
mechanics, tech stack, architecture diagrams, UX/user flows, and UI element
inventory — see [DESIGN.md](DESIGN.md).*
