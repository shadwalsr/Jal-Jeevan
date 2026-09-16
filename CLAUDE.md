# JalJeev — Agentic Marine Intelligence System (SIH26176)

Marine decision-support system for Indian fishermen, **sailors and maritime
traders**, coastal authorities, and maritime operators. Converts
heterogeneous ocean/atmospheric data into explainable, evidence-backed
operational decisions — delivered via voice/text in Indian regional
languages, online or offline. Built for Smart India Hackathon problem
statement 26176 (ISRO).

**Three user groups, one engine (28 Aug 2026).** The system was originally
built around a single implicit vessel — an 8m fishing boat — which made
every risk threshold effectively a constant. It now reasons about a vessel
CLASS (`app/agents/vessel_profiles.py`), so the same deterministic pipeline
gives a fisherman, a sailor and a cargo operator each a correct and
different answer about the same water. See "Vessels and user groups" below
before touching anything in `risk_agent.py`.

Full requirements live in `ORCA_PRD_SIH26176_v2.md` — read it before making
architectural decisions. This file is the practical "how it actually works
today" companion to that PRD.

## Core philosophy (do not violate this)

**The LLM never computes a number.** Wave height, risk scores, GIS
intersections, route geometry — all of it is deterministic Python/SQL. The
LLM's only two jobs are (1) parsing natural-language intent into structured
parameters and (2) phrasing a final answer from an evidence receipt it's
given (see `app/agents/evidence_agent.py`). If you find yourself asking an
LLM to calculate or estimate a physical value, stop — that belongs in a
deterministic agent instead.

**The LLM is optional, not a dependency.** As of 26 Aug 2026, both LLM jobs
have a real, tested, non-degraded fallback (`app/planner/rule_based.py`) —
a regex/keyword intent parser and a template-based answer renderer that
reads the same `EvidenceReceipt` directly. This engages automatically
whenever `GROQ_API_KEY` is unset OR a live call fails (quota, network,
anything) — not just "unconfigured." Verified live end-to-end with the key
removed entirely: geocoding, all 5 marine agents, risk scoring, evidence
aggregation, and answer rendering all ran with zero LLM calls. The rule-based
answer renderer is structurally incapable of hallucinating — it only ever
repeats fields already present in the receipt, never generates new text.

**Never fabricate data or results.** Every adapter that can't be verified
(MOSDAC, IMD — pending approval) returns an honest `{"status": "unavailable"}`
rather than a plausible-looking guess. The ML training pipeline distinguishes
real labels from synthetic placeholder labels loudly (see
`app/ml/train_fishing_suitability.py`) — synthetic-label metrics are never to
be reported as real results. The Anomaly Agent's SST baseline is explicitly
labeled as a single-year (2023) baseline, not a true multi-year climatology,
in every response it produces — don't let that caveat get dropped in any UI
that surfaces it.

**Graceful degradation over hanging or crashing.** Every external source call
has a timeout. If a source fails, the system falls back to another source or
reports the gap honestly (`missing: [...]`) rather than blocking or lying.

**Hard constraints veto; soft constraints only rank.** As of 26 Aug 2026 this
is real, not aspirational — see "Decision pipeline" below. Never add a new
legal/safety constraint (a new protected-area type, a new no-go condition) as
a scored `factor_breakdown` entry; it belongs in
`risk_agent.py::check_hard_constraints` instead, which every candidate is
checked against BEFORE any scoring happens.

## Vessels and user groups (read before touching risk_agent.py)

`app/agents/vessel_profiles.py` is the registry: 11 named classes across
fishing / sailing / trade, each with draft, block coefficient, wave and wind
limits, range and cruise speed. `resolve_vessel()` is the ONLY thing that
should build a `VesselProfile` from user input — it is a dictionary lookup
with alias matching, and an unrecognised class falls back to the documented
`fishing_small` default rather than raising or guessing. Numbers are
representative class averages, not a certified vessel database, and every
response says so.

Three things behave genuinely differently by class, and all three are
deterministic:

1. **Sail: wind is a resource, not only a hazard.** A motor vessel in 1 m/s
   of wind is having a perfect day; a sailing vessel has no drive and no
   steerage. `becalmed` scores that (halved for a motor-sailer with an
   auxiliary engine) and is never a veto. `point_of_sail` scores a course
   inside the vessel's no-go angle, and only fires when a course bearing is
   known — i.e. on the passage/routing paths, never on a bare point query.
   A motor vessel can never pick up either factor: the sail fields are
   `None` on motor classes and every sail branch is guarded on them.
2. **Trade: squat and proportional under-keel clearance.** `squat_m()` is
   Barrass's open-water approximation (Cb·V²/100, V in knots) — ~0.2m for a
   fishing boat, ~1.7m for a bulker at 14kn. Commercial vessels are held to
   10% of static draft (PIANC-style) instead of the small-boat fixed 1m
   margin, and the depth check now subtracts the EOT20 tide when one is
   available. Tide is never ASSUMED when absent — no value means "charted
   depth only", never a helpful positive.
3. **Hard constraints are still the only vetoes.** Everything above is
   Stage 2 scoring except the depth/squat/UKC rule, which is Stage 1. The
   constraint hierarchy is unchanged: a new legal/safety constraint still
   goes in `check_hard_constraints`, never into `factor_breakdown`.

`assess_risk(..., course_bearing_deg=None)` and
`check_hard_constraints(..., course_bearing_deg=None)` both take an optional
heading. It is additive only — a caller that doesn't pass one scores exactly
as it did before the parameter existed, which is why the pre-existing
fisherman path is untouched. Covered by `tests/test_vessel_classes.py`,
whose whole point is that the SAME sea must produce different correct
verdicts per class.

## Passage planning (A → B) vs. radial routing

Two genuinely different questions, two agents:

- **Radial** — "where near me is it safe?" — `route_agent.py` (16-candidate
  scan) and `route_optimizer.py` (A* to the safest cell at the edge of a
  radius). The fisherman's question. There is no destination.
- **Port-to-port** — "get me from Kochi to Kakinada and tell me when I
  arrive" — `passage_agent.py`, `/marine/passage`. The sailor's and
  trader's question, and the capability they had no way to ask for before.

`passage_agent.py` builds an H3 corridor along the great-circle track,
dilated laterally so A* can route AROUND hazards. Resolution is ADAPTIVE by
distance (res 5 coastal / 4 regional / 3 ocean) with a hard `MAX_CELLS`
budget — cell count grows with the square of corridor length, and this is
the same failure route_optimizer.py already hit going res 6 → 5. Edge weight
is real distance inflated by real risk, so total cost stays interpretable
and the search trades detour against roughness instead of doing only one.

**It scores each leg against the forecast hour the vessel actually arrives
there**, not against departure conditions — a multi-day passage scored
entirely at hour 0 would be a lie. Because tacking changes the ETA and
tacking is only known after scoring, this iterates: score, and if any leg
turned out to need tacking, reassign the hours and score the path once more.
Without that convergence a tacked passage reported legs scored at +13h next
to an ETA of +19h (measured live, 28 Aug 2026). Anything past the 7-day
Open-Meteo horizon is flagged `beyond_forecast_horizon` and surfaced in the
UI and the evidence receipt — never silently filled in.

Endpoints resolve from the ports table's HARBOUR ENTRANCE coordinates
(`get_port_by_name`), not the geocoder: a geocoded city name resolves to the
city centre, which is on land and correctly hard-vetoes (see gotcha #8).

## Architecture

```
User query (NL)
  → /chat → LangGraph planner (app/planner/graph.py)
      parse_intent (Groq, or rule-based) → resolve_location → execute_tools → synthesize_answer (Groq, or template)
              ↓                        ↓                  ↓
   Satellite Discovery Agent    Context & Memory    Weather · Ocean · Geo Agents
   (which sources are needed)   Agent (session       → Risk Agent → Validation Agent
                                 recall for follow-    → Evidence Agent (receipt)
                                 up questions)
                                      ↓
                    External sources (IMD, Copernicus, Open-Meteo, NOAA,
                    INCOIS, PostGIS boundaries, EOT20 tide model, GEBCO bathymetry)
```

Direct REST access also exists at `/marine/state`, `/marine/safest-route`,
`/marine/optimize-route`, `/marine/passage`, `/marine/vessel-classes`,
`/marine/ports`, `/marine/simulate/time-shift`,
`/marine/simulate/wave-perturbation` (app/api/marine.py). Every
vessel-taking endpoint accepts `vessel_class` plus optional per-field
overrides; the numeric overrides default to None, NOT to the small-boat
numbers, so asking about a tanker can never silently score it against an 8m
boat's thresholds. Omitting `vessel_class` resolves to the original 8m
fishing boat, so every pre-existing caller is unchanged. for callers that
don't need the conversational layer — none of these touch the LLM at all.

A React + MapLibre frontend (`frontend/`) exists — chat panel, marine map,
evidence panel, vessel selector, passage panel — wired to these real
endpoints, has a production build (`frontend/dist/`). The vessel selector is
populated from `/marine/vessel-classes` and the passage destinations from
`/marine/ports` rather than hardcoded lists, so neither can drift from what
the backend can actually score or plan to.

### Agents built (10 of 11 in the PRD's target roster — everything except Fishing)

| Agent | File | Job |
|---|---|---|
| Planner (orchestrator) | `app/planner/graph.py` | LangGraph state machine behind `/chat`. Only place an LLM touches this system (Groq, optional — see core philosophy), and only for intent parsing + final phrasing. |
| Weather | `app/agents/weather_agent.py` | Wind (sustained + gust), pressure + trend, precipitation, fog risk. IMD primary (pending), Open-Meteo fallback (live). |
| Ocean | `app/agents/ocean_agent.py` | Wave height, swell/wind-wave separation, SST consensus + anomaly flag, salinity, chlorophyll + HAB proxy, currents, tide (EOT20). Every source call runs concurrently, never sequentially — see gotcha #1. |
| Geo | `app/agents/geo_agent.py` | EEZ containment, MPA containment, nearest port, bathymetry depth — deterministic PostGIS + GEBCO lookups, no LLM. |
| Risk | `app/agents/risk_agent.py` | **Two-stage pipeline**: Stage 1 `check_hard_constraints` (MPA, certain-capsize wave height, out-of-range distance, insufficient depth vs. draft, on-land) vetoes outright → `risk_level="REJECTED"`, never scored. Stage 2 only runs on survivors — 0–100 additive score, every point individually explainable. Covered by `tests/test_risk_agent.py`. |
| Route (v1, fast) | `app/agents/route_agent.py` | Scans 16 candidate zones (Open-Meteo, fast) within a radius, ranks by shared Risk Agent hard-constraint+score logic, scores intermediate waypoints too (not just the destination), runs full multi-source detail on the winner. |
| Passage (A -> B) | `app/agents/passage_agent.py` | Port-to-port voyage planning for sailors and traders — A* over an adaptive-resolution H3 corridor between two real endpoints, leg-by-leg headings/distances/ETA from the vessel's own cruise speed, each leg scored against the forecast hour it is actually reached, plus diversion ports. `/marine/passage`. |
| Route Optimizer (v2, A*) | `app/agents/route_optimizer.py` | Real A* search over an H3 hex graph (NetworkX) — edge weights are real Risk Agent scores, vetoed cells are removed from the graph entirely. H3 resolution 5 (~8.7km hex) after resolution 6 measured 251s for a 25km search — cell count grows quadratically with ring count, res 5 cuts it ~4x. `/marine/optimize-route`. |
| Validation/Critic | `app/agents/validation_agent.py` | Physical-plausibility bounds + internal-contradiction checks (e.g. `vetoed=True` but `risk_level != REJECTED` would mean Risk Agent's own wiring broke) — the PRD's "safety net" before a result reaches the user. |
| Simulation | `app/agents/simulation_agent.py` | Three what-if types: time-shift (reads a REAL future point in Open-Meteo's own forecast), vessel-swap (reruns real conditions against a different boat), wave-perturbation (hypothetical stress-test, always stamped `is_synthetic_perturbation=True` — never confused with a forecast). |
| Satellite Discovery | `app/agents/satellite_discovery_agent.py` | Deterministic catalog: which real product/sensor backs each variable (OISST/AVHRR, Copernicus multi-source assimilation, GlobColour, EOT20, GEBCO, etc.) and whether it's currently active given configured credentials. |
| Anomaly Detection | `app/agents/anomaly_agent.py` | SST z-score vs. a precomputed baseline (`scripts/build_sst_climatology.py`, built from our own real 2023 downloads — 8,484 grid-cell/month entries). Explicitly NOT a multi-year climatology; every response says so. |
| Context & Memory | `app/agents/memory_agent.py` | Redis-backed per-session conversation history (1hr TTL) — lets "what about tomorrow?" resolve location from earlier in the same session without the user repeating it. |
| Explanation & Evidence | `app/agents/evidence_agent.py` | Deterministic aggregation into one structured `EvidenceReceipt` (sources, factor breakdown, gaps, rejected alternatives, confidence) — what the planner's synthesis step is fed (LLM or rule-based, either way), and what the frontend's evidence panel renders. |

**Not built**: Fishing Agent — blocked on MOSDAC PFZ labels, explicitly left
out per user instruction (26 Aug 2026), revisit once MOSDAC access lands.

### Decision pipeline (this replaced a real bug — read this if touching risk_agent.py)

Before 26 Aug 2026, `risk_agent.py` was a single flat additive score where an
MPA violation contributed +20 points instead of vetoing — meaning a spot
inside a protected area could still come back "LOW risk" if enough other
factors stayed low. `check_hard_constraints()` is the fix: it runs FIRST,
independently of scoring, and anything it flags short-circuits straight to
`risk_level="REJECTED"`, `factor_breakdown={}`. `route_agent.py`'s candidate
scan and `route_optimizer.py`'s graph both call this exact same function
(not a separate inline check) — single source of truth for what counts as a
veto vs. a ranking factor. When adding a new legal/safety constraint, it
goes in Stage 1, not Stage 2. Regression-tested in `tests/test_risk_agent.py`.

## Directory layout

```
backend/app/
  agents/       All agent files (11 built + route_optimizer v2 + passage_agent) and
                vessel_profiles.py, the vessel class registry — see table above
  api/          FastAPI routers (marine.py, chat.py)
  core/         config.py (env settings), cache.py (Redis), decisions.py (audit log)
  db/           SQLAlchemy async session
  ml/           Feature engineering + XGBoost training pipeline
  models/       Pydantic schemas (shared response shapes)
  planner/      LangGraph state machine + rule_based.py (LLM-free fallback)
  tools/        Adapters for each external source, plus _executor.py (dedicated thread
                pool) and _circuit_breaker.py (per-source failure tracking)
backend/tests/  pytest suite — risk hierarchy, circuit breaker, rule-based planner,
                vessel classes + class-aware risk, passage geometry (93 tests)
frontend/       React + Vite + MapLibre — ChatPanel, MarineMap, EvidencePanel (src/)
scripts/        Data-acquisition + precompute scripts (download_public.py, era5_2023.py,
                copernicus_subset.sh, load_boundaries.py, build_sst_climatology.py,
                prewarm_demo.py)
infra/sql/      Postgres schema + seed data (ports table)
data/
  raw/          Never edit — original downloads (Copernicus, ERA5, GFW, tides, boundaries,
                GEBCO bathymetry regional tiles)
  processed/    Derived tables (H3-indexed features, SST climatology, Parquet)
  models/       Trained model artifacts
DATA_ACQUISITION.md   How every dataset was fetched and why, with size estimates
```

## Running it locally

**Docker Desktop must be started manually first** (it does not auto-start) —
then bring up Postgres+PostGIS and Redis:
```bash
docker compose up -d postgres redis
```

Backend runs as a local process, not containerized — faster iteration:
```bash
cd backend
source .venv/Scripts/activate   # Windows Git Bash; .venv/bin/activate on Linux/macOS
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`.env`'s `DATABASE_URL`/`REDIS_URL` point at `localhost` for this reason;
docker-compose.yml overrides both back to the in-network hostnames
(`postgres`, `redis`) for the `backend`/`celery_*` services specifically, in
case the whole stack is run in Docker later.

Postgres is on host port **5433**, not 5432 — another local project already
owns 5432 on this machine. Redis is on the standard 6379.

**Frontend**:
```bash
cd frontend
npm install   # first time only
npm run dev
```

**Tests** (fast, no network, no server needed):
```bash
cd backend && python -m pytest tests/ -v
```

**Before a demo**: run `python scripts/prewarm_demo.py` ~10-15 minutes ahead
of time — it warms the Redis cache with real (not fabricated) responses so
every query during the demo returns in under a second instead of paying a
cold Copernicus/tide fetch live. Best-verified demo point right now: 15-25km
offshore Visakhapatnam (17.65, 83.35 / 17.6, 83.45) — real ~40-56m depth,
genuinely non-vetoed. Puri's exact coastline is NOT a good demo point — see
gotcha #8. Note geocoding a city NAME (e.g. "Visakhapatnam") resolves to the
city center, which is on land and will correctly hard-veto — use the
offshore coordinates directly, not the place name, for a "safe" demo result.

## Environment / secrets

Real credentials live in `.env` (gitignored, never commit). `.env.example`
documents every variable with where to get it. Status as of 26 Aug 2026:

- **Working now**: Copernicus Marine (username/password), NASA Earthdata
  (bearer token, has an expiry baked into the JWT — regenerate from the
  Earthdata profile if adapters start failing auth), CDS/ERA5, GFW, **Groq**
  (`GROQ_MODEL=openai/gpt-oss-120b` — primary LLM as of 26 Aug 2026, see
  gotcha #9 for why Gemini was dropped). `GEMINI_API_KEY` is still in `.env`
  but unused by any code path now; safe to remove.
- **Pending approval, wired but inactive**: MOSDAC, IMD, Protected Planet.
  Their adapters (`mosdac_adapter.py`, `imd_adapter.py`) short-circuit to
  `{"status": "unavailable"}` when the key is missing — dropping the key
  into `.env` activates them with zero other code changes, the calling
  agents already have the fallback chain built.

## Known gotchas (read before touching networking/async code)

1. **Never call multiple external sources sequentially in one agent.** Use
   `asyncio.gather`. A real bug of exactly this shape was found and fixed in
   `planner/graph.py::execute_tools` — three agent calls were written as
   `a, b, c = await x(), await y(), await z()`, which Python evaluates
   strictly in order despite looking parallel. If a "concurrent" block is
   mysteriously slow, check for this exact pattern first.

2. **`asyncio.to_thread()` shares asyncio's own internal executor — route
   genuinely blocking calls through the dedicated `network_executor`
   (`app/tools/_executor.py`) instead.** Confirmed live, twice: once for
   Copernicus/erddapy adapters, and again on 26 Aug 2026 for the LLM call
   itself — a call that took 4-8s standalone consistently hit its timeout
   when run inside the live server via `asyncio.to_thread`, and was fixed
   by switching to `loop.run_in_executor(network_executor, ...)`. This
   pattern is now used everywhere a blocking SDK call is made, LLM included.

3. **Endpoint-level timeouts must be per-agent, not wrapped around the whole
   `asyncio.gather()`.** One slow source (Copernicus) would otherwise
   discard fast, successful results from the others. See
   `_run_with_timeout` in `app/api/marine.py` for the corrected pattern.

4. **Never swallow an exception without logging its type and message —
   "it's probably just slow" is a guess, not a diagnosis.** A ~20s failure
   that looked exactly like a hang across two full debugging sessions (with
   `asyncio.to_thread` fixed to `network_executor`, retries added, timeouts
   raised) turned out to be an instant `429 RESOURCE_EXHAUSTED` — Gemini's
   free-tier daily quota (20 requests/day) exhausted by testing volume —
   that a bare `except Exception: return None` was hiding. Adding one
   `print(f"{type(exc).__name__}: {exc}")` found it immediately. This is
   why Groq replaced Gemini as the primary LLM (see gotcha #9) — not because
   the async fixes were wrong, but because the actual root cause was never
   a timeout at all.

5. **On Windows, `taskkill //F //IM uvicorn.exe` between test runs** — a
   stale process holding port 8000 causes silent connection-refused errors
   that look like a code bug. Kill it explicitly before restarting.

6. Redis/Postgres caching TTLs are deliberately variable-specific (see
   `app/core/cache.py`'s `TTL_SECONDS`) — SST is cached longer than wind,
   because it actually changes more slowly. Don't collapse this to one
   blanket TTL.

7. **A large single OPeNDAP request can silently truncate and zero-fill the
   rest — no error raised.** An India-wide GEBCO bathymetry subset (25x35
   degrees) came back 96% zeros past the first ~200 rows, and every
   downstream depth lookup silently returned "0m / land" instead of real
   bathymetry. The fix in `app/tools/bathymetry_adapter.py` is to fetch
   small (~1x1 degree) regional tiles with an explicit nonzero-fraction
   sanity check (`>85%`) before saving — never trust a large OPeNDAP
   transfer without verifying real values landed. Only a handful of demo
   regions are loaded (`data/raw/gebco/regions/`); a point outside all of
   them returns `status: "unavailable"`, not a wrong depth.

8. **Puri's exact coastline is a genuinely very shallow river-delta shelf** —
   confirmed against the live GEBCO source, not a data bug: 0m depth extends
   tens of km offshore near the Mahanadi delta (why Paradip/Puri need
   dredged approach channels in real life). It will correctly hit the
   draft-vs-depth hard veto for any normal small-boat draft. Use
   Visakhapatnam for demos instead (steeper natural shelf, verified
   ~40-56m a short distance out) — but note the city CENTER is on land
   (see the demo section above); use offshore coordinates, not the geocoded
   place name, when you need a non-vetoed result.

9. **Gemini was replaced with Groq as the primary LLM (26 Aug 2026).** Not
   a technical failure of Gemini itself — the free tier's 20-requests/day
   quota for `gemini-3.6-flash` was exhausted by development testing volume,
   and (per gotcha #4) that failure mode was mistaken for an async/network
   bug for a long time because the real exception was being swallowed.
   Groq (`app/planner/graph.py`, model `openai/gpt-oss-120b`) has a more
   generous free tier and measured ~0.6s for a trivial call. If Groq's
   quota is ever exhausted too, the system does NOT hang or error — it
   falls through to `app/planner/rule_based.py` automatically (see core
   philosophy above). Don't remove that fallback thinking Groq solves the
   quota problem permanently; it's still a free-tier third-party API.

## Data acquired so far

See `DATA_ACQUISITION.md` for the full list with sizes and re-fetch commands.
Summary: Copernicus (physics/BGC/waves/altimetry, full 2023), ERA5 (12/12
months 2023), IBTrACS, GFW vessel identity + monthly effort, Marine Regions
EEZ, WDPA marine protected areas (bbox-filtered to the Indian Ocean), the
EOT20 global tide model, and GEBCO bathymetry (small verified regional tiles
only — see gotcha #7). WOA23 climatologies and the GFW MMSI daily archive are
incomplete (external server issues / paused, both resumable by re-running
`scripts/download_public.py`).

`data/processed/sst_climatology.parquet` — precomputed by
`scripts/build_sst_climatology.py` from the real 2023 feature table, feeds
the Anomaly Agent. Single-year baseline, not a true climatology (see the
core philosophy section above).

**The one dataset that matters most and isn't a bulk download**: the INCOIS
PFZ advisory archive (2003–2025) — the actual training labels for fishing
suitability. Gated on MOSDAC access. Nothing else substitutes for it.

## Conventions for future work in this repo

- Every adapter function returns a dict with at least `{"status": ..., "source": ...}`
  — `"success"`, `"failed"`, or `"unavailable"` (the last specifically means
  "not configured yet," not "tried and failed").
- Agents (not adapters) are what return the shared Pydantic schemas in
  `app/models/schemas.py`. Adapters return raw dicts; agents translate.
- A new legal/safety constraint goes in `risk_agent.py::check_hard_constraints`
  (Stage 1, vetoes). A new hazard/signal that should influence ranking among
  already-legal candidates goes in `factor_breakdown` (Stage 2) — needs both
  a breakdown entry and an `explanation` line, per the project's
  explainability requirement.
- Don't add a new external source without a timeout and a documented
  fallback behavior. See gotcha #2 above.
- Before trusting a large bulk geospatial/OPeNDAP fetch, verify actual
  values landed (nonzero fraction, spot-check against a known point) before
  saving — see gotcha #7.
- **Never swallow an exception silently in an adapter or LLM call** — see
  gotcha #4. Log or return `type(exc).__name__: exc`, not just "failed."
- Any new hard-coded intent-parsing/answer-rendering logic added to
  `rule_based.py` should get a test in `tests/test_rule_based_planner.py` —
  it's the zero-dependency fallback path, it needs to be trustworthy on its
  own merits, not just "good enough as a backup."
