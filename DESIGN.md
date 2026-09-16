# DESIGN.md — JalJeev: System, Model & Interface Design

> **Scope**: this file is mutually exclusive with [CONTEXT.md](CONTEXT.md).
> CONTEXT.md tells you *what JalJeev is and why*; this file tells you
> *exactly how it computes an answer and how that answer reaches a screen* —
> tech stack, architecture, data/model pipeline mechanics, UX/user flow, and
> the concrete UI element inventory (including what to draw for
> infographics). Read CONTEXT.md first if you haven't.

---

## 1. Tech stack

### Backend
| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | async-first throughout |
| Web framework | FastAPI | REST (`app/api/marine.py`) + NL chat (`app/api/chat.py`) |
| Orchestration | LangGraph | State machine behind `/chat`: parse → resolve → execute → synthesize |
| LLM (optional) | Groq, model `openai/gpt-oss-120b` | Only for intent parsing + final phrasing, never for computation |
| LLM fallback | `app/planner/rule_based.py` | Regex/keyword intent parser + template answer renderer, zero-dependency |
| Database | PostgreSQL + PostGIS | EEZ/MPA boundaries, ports table, spatial queries |
| Cache / session | Redis | Per-variable TTL cache (`app/core/cache.py`) + session memory (1hr TTL, `memory_agent.py`) |
| Object storage | MinIO | (docker-compose service, for larger artifacts) |
| Task queue | Celery | Background/async jobs (`core/` config) |
| Geospatial indexing | H3 (Uber) | Hex-grid corridors for A* passage/route search |
| Graph search | NetworkX (A*) | `route_optimizer.py`, `passage_agent.py` |
| ML | XGBoost | Fishing-suitability model (blocked on real labels — see CONTEXT.md §7) |
| ORM | SQLAlchemy (async) | `app/db/` |
| Schema validation | Pydantic | `app/models/schemas.py` — every agent's output shape |
| Networking model | Dedicated thread pool (`app/tools/_executor.py`) | Blocking SDK calls routed here, not `asyncio.to_thread` |
| Resilience | Per-source circuit breaker (`app/tools/_circuit_breaker.py`) | Tracks failures per external source |

### Frontend (web)
| Layer | Choice |
|---|---|
| Framework | React + TypeScript |
| Build tool | Vite |
| Mapping | MapLibre GL |
| Key components | `ChatPanel`, `MarineMap`, `EvidencePanel`, `VesselSelector`, `PassagePanel`, `SafetyMonitor`, `App.tsx` shell |
| API layer | `frontend/src/api.ts` — typed calls to the FastAPI backend |
| Build artifact | `frontend/dist/` (production build exists) |

### Mobile
| Layer | Choice |
|---|---|
| Platform | Native Android (Kotlin, Gradle) |
| Location | `android/` — Gradle Kotlin DSL project, own `README.md` |

### Design tooling
| Layer | Choice |
|---|---|
| UI prototyping | Claude Design canvas — `design-canvas/Main.dc.html`, `States.dc.html`, `canvas.json` |
| Chart prototyping | `design-canvas/jaljeev-chart-interface.html` |

### External data sources (see CONTEXT.md §6 for full status table)
Open-Meteo, Copernicus Marine, ERA5/CDS, NASA Earthdata, GFW, EOT20 (tide),
GEBCO (bathymetry), Marine Regions (EEZ), WDPA (MPA), IBTrACS (cyclones);
MOSDAC (EOS-06 chlorophyll) and Protected Planet (MPA API v4) are active; IMD pending approval.

---

## 2. High-level architecture

```
                        ┌───────────────────────────────────────────┐
                        │             CLIENTS                       │
                        │  React+MapLibre web  ·  Android app        │
                        └───────────────┬─────────────┬──────────────┘
                                        │             │
                         NL question    │             │  Direct REST
                         (voice/text)   ▼             ▼  (typed params)
                        ┌───────────────────┐   ┌─────────────────────┐
                        │   POST /chat       │   │  /marine/* endpoints │
                        │  (chat.py)         │   │  (marine.py)         │
                        └─────────┬──────────┘   └──────────┬───────────┘
                                  │                          │
                                  ▼                          │
                  ┌───────────────────────────────┐          │
                  │   LangGraph Planner (graph.py) │          │
                  │  1. parse_intent (Groq | rule) │          │
                  │  2. resolve_location            │          │
                  │  3. execute_tools (fan-out)     │          │
                  │  4. synthesize_answer (Groq|rule)│         │
                  └───────┬───────────┬─────────────┘          │
                          │           │                        │
             ┌────────────┘           └───────────┐            │
             ▼                                     ▼            ▼
   ┌───────────────────┐                 ┌──────────────────────────────┐
   │ Context & Memory   │                 │   Deterministic Agent Layer   │
   │ Agent (Redis, 1hr) │                 │  (called directly by both     │
   │ session recall     │                 │   /chat's execute_tools AND   │
   └────────────────────┘                 │   the REST endpoints)         │
                                          │                                │
                                          │  Weather · Ocean · Geo         │
                                          │  → Risk (2-stage) → Validation │
                                          │  → Evidence (receipt)          │
                                          │                                │
                                          │  Route (radial) / Passage (A→B)│
                                          │  / Route Optimizer (A*)        │
                                          │  Simulation · Anomaly ·        │
                                          │  Satellite Discovery           │
                                          └───────────────┬────────────────┘
                                                          │
                                                          ▼
                                    ┌──────────────────────────────────────┐
                                    │   Adapters (app/tools/*_adapter.py)   │
                                    │  IMD · Copernicus · Open-Meteo · NOAA │
                                    │  INCOIS · PostGIS boundaries · EOT20  │
                                    │  tide · GEBCO bathymetry · MOSDAC     │
                                    │  Each: timeout + circuit breaker +    │
                                    │  {status, source} contract            │
                                    └────────────────────────────────────────┘
```

### Agent roster and single job of each

| # | Agent | File | Job | LLM? |
|---|---|---|---|---|
| — | Planner (orchestrator) | `planner/graph.py` | LangGraph state machine behind `/chat`. The *only* place an LLM touches the system. | Optional |
| 1 | Weather | `weather_agent.py` | Wind (sustained+gust), pressure+trend, precipitation, fog risk. IMD primary (pending), Open-Meteo fallback (live) | No |
| 2 | Ocean | `ocean_agent.py` | Wave height, swell/wind-wave separation, SST consensus+anomaly, salinity, chlorophyll+HAB proxy, currents, tide (EOT20). All source calls concurrent (`asyncio.gather`) | No |
| 3 | Geo | `geo_agent.py` | EEZ containment, MPA containment, nearest port, bathymetry depth — PostGIS + GEBCO, deterministic | No |
| 4 | Risk | `risk_agent.py` | 2-stage: hard-constraint veto → additive 0-100 score. See §3 below | No |
| 5 | Route (v1) | `route_agent.py` | 16-candidate radial scan (Open-Meteo, fast), ranks by shared Risk Agent logic, scores intermediate waypoints too | No |
| 6 | Passage | `passage_agent.py` | Port-to-port A* over adaptive H3 corridor, leg-by-leg ETA-aware scoring, diversion ports | No |
| 7 | Route Optimizer (v2) | `route_optimizer.py` | Real A* over H3 hex graph (NetworkX), vetoed cells removed from graph entirely, res 5 | No |
| 8 | Validation/Critic | `validation_agent.py` | Physical-plausibility bounds + internal-contradiction checks (the PRD's "safety net") | No |
| 9 | Simulation | `simulation_agent.py` | 3 what-ifs: time-shift (real future forecast point), vessel-swap (real conditions, different boat), wave-perturbation (synthetic stress test, always stamped) | No |
| 10 | Satellite Discovery | `satellite_discovery_agent.py` | Deterministic catalog of which real product/sensor backs each variable, active/inactive by configured credentials | No |
| 11 | Anomaly Detection | `anomaly_agent.py` | SST z-score vs. precomputed single-year (2023) baseline | No |
| 12 | Context & Memory | `memory_agent.py` | Redis session history (1hr TTL) for follow-up questions | No |
| 13 | Explanation & Evidence | `evidence_agent.py` | Deterministic aggregation into `EvidenceReceipt` — what synthesis and the frontend evidence panel both consume | No |

**Only the Planner touches an LLM, and only for two jobs** (intent parsing,
answer phrasing) — every agent above is pure deterministic Python/SQL.

---

## 3. The risk model — exact mechanics

### Stage 1 — Hard constraints (`check_hard_constraints`)
Runs first, independent of scoring. Any hit → `risk_level = "REJECTED"`,
`factor_breakdown = {}` (never scored). Checks:
- Inside a Marine Protected Area (MPA)
- Wave height at or above certain-capsize threshold for the vessel class
- Requested distance outside the vessel's `operational_range_km`
- Insufficient depth vs. draft — **now vessel-class-aware**:
  - Small craft: fixed 1m safety margin under draft
  - Commercial (`commercial=True`) vessels: 10% of static draft (PIANC-style)
    margin, PLUS a real **squat** correction:
    `squat_m ≈ block_coefficient × speed_kn² / 100` (Barrass open-water
    approximation) — ~0.2m for a fishing boat, ~1.7m for a bulker at 14kn
  - Tide (EOT20) subtracted from charted depth when available; **never
    assumed** when absent (no positive value fabricated)
- Point is on land

This exact function is called by Risk Agent, Route Agent's candidate scan,
AND Route Optimizer's A* graph construction — one source of truth, never a
duplicated inline check.

### Stage 2 — Additive scoring (0–100, only survivors of Stage 1)
Every point is individually explainable — each contributing factor gets a
`factor_breakdown` entry (score delta) and a human-readable `explanation`
line. Universal factors: wave height (sub-veto range), wind, visibility/fog,
currents, distance from shore/port, cyclone proximity, HAB/SST anomaly
flags, etc.

**Vessel-class-specific Stage-2 factors** (never vetoes):
- `becalmed` — scores insufficient wind for a sailing vessel to make way
  (halved for `motor_sail` propulsion since an auxiliary engine covers the
  gap). Never scored for pure `motor` propulsion — sail fields are `None`
  on those classes and the branch is guarded.
- `point_of_sail` — scores a course bearing that falls inside the vessel's
  `no_go_angle_deg` (can't sail that close to the wind). Only fires when a
  course bearing is known (i.e. on passage/routing calls that pass
  `course_bearing_deg`), never on a bare point query.

### Function signatures (additive-only parameter)
```
assess_risk(..., course_bearing_deg: float | None = None)
check_hard_constraints(..., course_bearing_deg: float | None = None)
```
Optional and additive — a caller that never passes a heading scores exactly
as it always did, so the original fisherman radial-query path is untouched
by this vessel-awareness work.

### Vessel profile resolution
```
resolve_vessel(vessel_class: str | None, length_m: float | None, **overrides)
    → VesselProfile
```
- Free-text-to-class alias table (`CLASS_ALIASES`) handles synonyms like
  "trawler"→`fishing_mechanized`, "yacht"→`sailing_yacht`,
  "bulker"→`bulk_carrier`.
- Unknown/`None` class → falls back to `fishing_small` (documented default),
  never raises, never guesses — this matters because the input can be raw
  natural language or an LLM hallucination.
- `length_m` is recorded but never used to reshape/interpolate a profile —
  it only enters a calculation where length genuinely matters (squat).
- Per-field numeric overrides default to `None`, not to the small-boat
  numbers — so a caller who says "tanker" but forgets to also disable small-
  boat defaults can never silently score a 250m ship against an 8m boat's
  thresholds.

### 11 vessel classes (see CONTEXT.md §8 for the full table)
`fishing_small` (default, 8m), `fishing_mechanized` (18m), `sailing_yacht`
(12m), `sailing_yacht_aux` (12m+engine), `dhow` (20m sail+motor trader),
`coastal_trader` (40m), `general_cargo` (120m), `bulk_carrier` (200m),
`tanker` (250m), `container_ship` (300m), `passenger_ferry` (60m, wave
threshold deliberately conservative — passenger safety, not hull capability,
is the binding limit).

---

## 4. Passage planning mechanics (A→B)

1. Resolve both endpoints via the **ports table's harbour-entrance
   coordinates** (`get_port_by_name`) — never the geocoder (a geocoded city
   name lands on the city centre, which is on land and would falsely
   hard-veto).
2. Build a great-circle track between the two ports.
3. Generate an **H3 hex corridor** dilated laterally around that track so
   A* has room to route around hazards, not just follow the straight line.
4. H3 resolution is **adaptive by distance**: res 5 (coastal), res 4
   (regional), res 3 (ocean) — with a hard `MAX_CELLS` budget, because cell
   count grows with the square of corridor length (this is the same failure
   mode `route_optimizer.py` already hit going res 6→5 on a 25km search:
   251 seconds).
5. Edge weight = real distance inflated by real Risk Agent score, so total
   path cost stays interpretable (search trades detour distance against
   roughness, not one or the other).
6. **Each leg is scored against the forecast hour the vessel actually
   arrives there**, computed from the vessel's own cruise speed — not
   against departure-time conditions (a multi-day passage scored entirely at
   hour 0 would be a lie).
7. **Convergence loop**: tacking (for sail classes) changes ETA, but tacking
   is only discoverable *after* scoring a leg. So: score → if any leg needed
   tacking, reassign hours → score the whole path again. Without this loop,
   a real tacked passage reported leg times +13h next to a total ETA of
   +19h (measured live, 28 Aug 2026) — an internally contradictory result.
8. Anything beyond the 7-day Open-Meteo forecast horizon is flagged
   `beyond_forecast_horizon` in both the API response and the evidence
   receipt — surfaced in the UI, never silently backfilled.
9. Diversion ports are computed alongside the main route (fallback options
   if conditions on a leg turn bad).

---

## 5. Radial routing mechanics (fisherman's "where's it safe near me?")

- **v1 — `route_agent.py`**: scans 16 candidate zones around the query point
  using fast Open-Meteo data, ranks each against the shared
  `check_hard_constraints` + scoring logic, scores intermediate waypoints
  (not just the final destination zone), then runs a full multi-source
  detail pass on the single winning candidate only (keeps it fast — 16
  cheap scans + 1 expensive one, not 16 expensive ones).
- **v2 — `route_optimizer.py`**: a real A* search over a NetworkX graph built
  from H3 hexes (resolution 5, ~8.7km hex). Vetoed cells are removed from
  the graph entirely (not just penalized), so the search can never route
  through a hard-constraint failure. Edge weights are real Risk Agent
  scores.

---

## 6. End-to-end request lifecycle (the `/chat` path)

```
1. User speaks/types a question (voice is transcribed upstream of /chat)
2. POST /chat {message, session_id?}
3. Planner.parse_intent
     Groq call (structured JSON extraction) — OR if GROQ_API_KEY unset /
     call fails → app/planner/rule_based.py regex+keyword parser
     Output: {intent_type, location_text?, vessel_class?, course_bearing?, ...}
4. Planner.resolve_location
     - place name → geocoder (city centre) OR explicit lat/lon passed through
     - Context & Memory Agent consulted for follow-ups ("what about tomorrow?")
       resolving location/vessel from earlier turns in the same Redis session
5. Planner.execute_tools  (asyncio.gather — NEVER sequential, see gotcha #1)
     → Weather Agent, Ocean Agent, Geo Agent run concurrently
     → Risk Agent (Stage 1 veto, Stage 2 score) on the fused state
     → Route/Passage Agent if the intent implies routing
     → Validation Agent sanity-checks the combined result
     → Evidence Agent assembles the EvidenceReceipt
6. Planner.synthesize_answer
     Groq call, prompted ONLY with the EvidenceReceipt (never asked to
     compute anything) — OR rule_based.py template renderer that repeats
     receipt fields verbatim (cannot hallucinate by construction)
7. ChatResponse {answer_text, evidence_receipt, ...} returned
8. Frontend renders answer in ChatPanel + full receipt in EvidencePanel +
   any route/passage geometry on MarineMap
```

Direct REST callers (`/marine/state`, `/marine/safest-route`,
`/marine/optimize-route`, `/marine/passage`, `/marine/vessel-classes`,
`/marine/ports`, `/marine/simulate/time-shift`,
`/marine/simulate/wave-perturbation`) skip steps 3/4/6 entirely — they take
typed parameters directly and never touch the LLM. Every vessel-taking
endpoint accepts `vessel_class` plus optional per-field overrides.

---

## 7. The Evidence Receipt — the explainability contract

`EvidenceReceipt` (`app/models/schemas.py`) is the single object every
answer is built from, whether by LLM or rule-based renderer, and what the
frontend's Evidence Panel renders directly:

```
decision_id            audit-log correlation id
recommendation_summary  e.g. "Conditions are marginal — proceed with caution"
risk_score / risk_level  0-100 / LOW|MODERATE|HIGH|REJECTED
factor_lines            plain-language "X → +N" lines, already human-readable
sources_used            e.g. ["Open-Meteo", "EOT20 tide model", "GEBCO"]
data_freshness          per-source timestamp/age
data_gaps               what couldn't be fetched, stated honestly
rejected_alternatives   "Why not the other route?" (PRD's "Why not?" feature)
confidence_statement    plain-language confidence caveat
validation_note         Validation Agent's sanity-check note, if any
location_lat/lon +
location_maps_url       exact coordinates + clickable Google Maps link
                        (added 26 Aug 2026 after a real answer said "20km
                        at bearing 45°" with no way to actually find it)
```

Both the LLM prompt template and `rule_based.py`'s renderer are **required**
to surface `location_lat/lon/maps_url` whenever present — this is a
regression class the project explicitly tests against.

---

## 8. User experience & user flow

### Primary user flow (fisherman — radial, most common path)
```
Open app → (optional) select vessel class, defaults to "Small fishing boat"
  → Ask in own language, voice or text: "Is it safe to go out near Kochi?"
  → Loading state (single, since result is fused server-side)
  → Answer card: verdict (Go / Caution / Don't go) + one-line reason
  → Tap "Why?" → Evidence Panel expands: sources, factor breakdown,
    data gaps, confidence, map link
  → Map shows the queried point + (if routing was implied) safest nearby zone
  → Follow-up question ("what about tomorrow?") resolves same location
    from session memory without re-specifying it
```

### Sailor / trader flow (passage planning)
```
Open Passage Panel → pick origin port, destination port (from live
  /marine/ports list, never hardcoded) → pick/confirm vessel class
  (from live /marine/vessel-classes list)
  → Request plan → map renders the full corridor + A* route with
    leg-by-leg markers (heading, distance, ETA, risk at that leg's actual
    arrival hour)
  → Any leg beyond the 7-day forecast horizon is visually flagged
    ("beyond forecast horizon — not scored")
  → Diversion ports shown as alternate markers
  → Evidence Panel available per-leg or for the whole passage
```

### Design principles driving the UX
- **Verdict first, evidence on demand** — never force-read a data dump
  before the actual go/no-go answer.
- **Never a bare number with no reason** — every risk score is paired with
  its `factor_lines`.
- **Never a silently missing source** — `data_gaps` and `missing` fields are
  always rendered, not hidden for a cleaner look.
- **Language- and mode-agnostic core** — the same evidence receipt drives
  voice output, text chat, and the visual evidence panel; nothing is
  computed differently per output channel.
- **Offline-safe by design** — the rule-based path guarantees the app never
  goes fully mute even with no LLM/network access; the UI's job is to make
  that path indistinguishable in quality of experience (same receipt shape,
  same panel).

---

## 9. UI element inventory (frontend/src)

| Component | Responsibility |
|---|---|
| `App.tsx` | Top-level shell, routes between chat/map/passage views |
| `ChatPanel.tsx` | Message thread, text/voice input, renders `answer_text` |
| `MarineMap.tsx` | MapLibre map — query point, hazard zones (MPA/EEZ overlays), route/passage geometry, diversion markers |
| `EvidencePanel.tsx` | Renders the full `EvidenceReceipt`: sources, factor breakdown, data gaps, confidence, rejected alternatives, maps link |
| `VesselSelector.tsx` | Dropdown/picker populated live from `/marine/vessel-classes` — cannot drift from backend-scoreable classes |
| `PassagePanel.tsx` | Origin/destination port pickers (from `/marine/ports`), vessel class, triggers `/marine/passage`, renders leg table |
| `SafetyMonitor.tsx` | Ambient/ongoing risk-level indicator (current query's verdict at a glance) |
| `api.ts` | Typed fetch wrappers for every backend endpoint |

### Infographic / diagram opportunities (for future generation)
When producing visual assets for this project, these are the diagrams worth
building (see `design-canvas/` for existing prototypes to extend rather than
duplicate):
1. **System architecture diagram** — mirrors §2 above: clients → planner →
   agent layer → adapters → external sources.
2. **Risk pipeline flowchart** — Stage 1 hard-constraint gate → Stage 2
   additive scoring → Evidence Receipt, with the REJECTED short-circuit path
   visually distinct.
3. **Vessel-class comparison chart** — same sea state, 11 vessel rows, verdict
   column differing per class (the literal point of `test_vessel_classes.py`
   — makes a strong demo visual).
4. **Passage planning corridor diagram** — great-circle track, H3 hex
   dilation, A* path around a hazard, per-leg ETA-scored markers, tacking
   convergence loop.
5. **Data source / fallback matrix** — each variable (wind, wave, SST, tide,
   depth...) mapped to primary source → fallback source → "unavailable"
   honesty path.
6. **LLM-optional flow** — parse_intent/synthesize_answer boxes with a
   visible fork to `rule_based.py`, emphasizing zero-hallucination-by-
   construction on the fallback branch.

---

## 10. Cross-reference

- Full formal requirements and roadmap phases: `ORCA_PRD_SIH26176_v2.md`
- Dataset provenance and re-fetch commands: `DATA_ACQUISITION.md`
- Project narrative, status, gotchas, philosophy: [CONTEXT.md](CONTEXT.md)
- Existing UI prototypes: `design-canvas/Main.dc.html`,
  `design-canvas/States.dc.html`, `design-canvas/jaljeev-chart-interface.html`
