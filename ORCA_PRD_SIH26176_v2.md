# PRODUCT REQUIREMENTS DOCUMENT (PRD)
## ORCA — Agentic Marine Intelligence System
### Smart India Hackathon 2026 | Problem Statement: SIH26176
### Organisation: Indian Space Research Organisation (ISRO) | Theme: Miscellaneous | Category: Software

---

| Field | Detail |
|---|---|
| Document Type | Product Requirements Document (PRD) |
| Version | 2.1 — Full PRD, reconciled with the built system (supersedes PID v1.0) |
| Status | Active — Internal Round Submission |
| Team Name | Team ORCA |
| Institution | KIIT University, Bhubaneswar |
| PS Number | SIH26176 |
| Issuing Organisation | Indian Space Research Organisation (ISRO) |
| Internal Round Deadline | 20 September 2026 |
| Grand Finale | December 2026 |
| Last Updated | 27 August 2026 |

---

## DOCUMENT PURPOSE

This PRD is the single source of truth for the ORCA platform. It defines the problem, the complete proposed solution, every functional and non-functional requirement, the full data architecture, the complete technology stack with justifications, all agent specifications, user stories, API design, database schema, ML model specifications, testing strategy, deployment plan, and roadmap. Nothing is omitted. Every team member, mentor, and ISRO evaluator should be able to understand the full scope of what ORCA is and how it works from this document alone.

---

## CHANGE LOG

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | August 2026 | Shadwal | Initial PID |
| 2.0 | August 2026 | Shadwal | Full PRD — user stories, functional requirements, NFRs, API specs, DB schema, testing, deployment, team roles, KPIs, glossary |
| 2.1 | 27 August 2026 | Shadwal | **Reconciled with the built system.** Sections marked *(built)* describe code that exists and has been run, not intent. Adds: native Android client (§10.7, §16.7); two-stage constraint hierarchy replacing the flat risk score (§8.5); LLM-optional rule-based planner (§8.0); Validation/Critic Agent (§8.11); A* route optimiser over an H3 risk graph (§8.12); request-path latency architecture with measured before/after figures (§7.4); Groq replacing Gemini as primary LLM (§10.2); GEBCO regional tiling incl. Odisha coverage (§9.2); as-built API surface (§14.1); Odisha demo script (§27.2). |

**Reading this document after v2.1:** headings tagged *(built)* have working code behind them and figures quoted in those sections are measured, not estimated. Untagged sections remain design intent. Where the two once disagreed, the built behaviour is now the specification and the reason for the change is recorded inline.

---

## TABLE OF CONTENTS

1. Executive Summary
2. Problem Statement Analysis
3. Gap Analysis
4. Proposed Solution
5. Target Users & Personas
6. User Stories
7. System Architecture (Complete)
8. Agent Design
9. Data Sources (Tier 1 / 2 / 3)
10. Technology Stack (Full, Justified)
11. Machine Learning Models (Full Specification)
12. Database Schema (Complete)
13. Storage Architecture
14. API Specifications
15. Tool Registry
16. Frontend / PWA Design
17. Multilingual & Voice Strategy
18. Offline / Low-Bandwidth Strategy
19. Functional Requirements (FR-001 to FR-085)
20. Non-Functional Requirements (NFR-001 to NFR-030)
21. Security & Privacy
22. Evaluation & Validation Strategy
23. Testing Strategy
24. Deployment Architecture
25. Team Composition & Roles
26. KPIs & Success Metrics
27. Demo Script
28. Phased Roadmap
29. Risk Assessment & Mitigations
30. Innovation Highlights
31. What We Are Not Building
32. Winning Philosophy
33. Appendix A — Additional Stack Recommendations
34. Appendix B — Data Source Registration Requirements
35. Appendix C — Glossary

---

## 1. EXECUTIVE SUMMARY

ORCA (Marine EcOsystem Reasoning with Collaborative Agents) is an agentic marine intelligence platform built for SIH26176 issued by ISRO. It converts heterogeneous, multi-source Indian ocean and atmospheric data into explainable, evidence-backed operational decisions for fishermen, coastal authorities, disaster managers, maritime operators, and marine researchers — delivered in Indian regional languages via voice and text, on any device, online or offline.

The core innovation is not a chatbot. It is a **Marine Digital Twin** — a continuously updated, H3-indexed spatial model of the Indian Ocean and Indian EEZ — orchestrated by a multi-agent AI planner that selects specialist tools dynamically, fuses data from 15+ authoritative sources, validates its own uncertainty, and returns grounded recommendations with full evidence trails that judges and users can inspect and challenge.

ORCA is designed to be deployed, not just demonstrated. Every architectural decision — offline mode, voice input, PWA installability, vessel-aware risk, multi-source consensus, proactive alerts — is motivated by the actual conditions under which a fisherman from Puri, Rameswaram, or Kochi would use it.

---

## 2. PROBLEM STATEMENT ANALYSIS

### 2.1 PS-26176 as issued by ISRO

**Title:** ORCA — Marine EcOsystem Reasoning with Collaborative Agents  
**Category:** Software | **Theme:** Miscellaneous | **Deadline:** December 2026

### 2.2 What ISRO explicitly requires

- Natural language query interface for diverse marine stakeholders
- Automatic intent identification and task decomposition
- Multi-agent autonomous coordination
- Integration of satellite EO, GIS, weather, oceanographic, and advisory data
- Spatial, temporal, and contextual reasoning across heterogeneous sources
- Explainable, evidence-based recommendations via conversational interface
- Indian regional language support including voice interaction
- Proactive alerts: adverse weather, cyclones, lightning, high waves
- Geofencing: international boundaries, restricted waters, ecologically sensitive zones
- Route optimisation and safe navigation assistance

### 2.3 Representative queries from ISRO

- "Where is the nearest Potential Fishing Zone (PFZ) today?"
- "Is it safe to venture into the sea tomorrow morning?"
- "What are the tide, weather, and sea conditions near my fishing location?"
- "Are there any lightning or cyclone alerts in my area?"
- "Which regions show high chlorophyll and favourable SST?"
- "What is the safest route for a fishing vessel considering weather and sea-state?"
- "Why has fish productivity declined in a particular coastal region?"
- "Which fishing zones should be avoided due to hazardous conditions or geofencing restrictions?"

---

## 3. GAP ANALYSIS

### 3.1 India's marine data infrastructure is world-class — but inaccessible

India has the following authoritative operational systems producing real data daily:
- **INCOIS** publishes Ocean State Forecasts (OSF) 5–7 days ahead
- **ISRO MOSDAC** distributes EOS-06/Oceansat-3 satellite data: SST, chlorophyll, ocean colour, PFZ advisories
- **IMD** issues cyclone tracks, lightning warnings, rainfall forecasts in near-real-time
- **INCOIS PFZ** advisories combine SST, chlorophyll, currents, winds, altimetry into fishing zone maps

### 3.2 Why none of it reaches the fisherman

A Puri fisherman planning a 5 AM departure would need to visit five separate government portals, read English scientific data formats, and manually correlate heterogeneous outputs. No fisherman does this.

### 3.3 The technical gap

| Existing approach | Limitation |
|---|---|
| Single weather app | No ocean data, no PFZ, no geofencing, no vessel context |
| INCOIS OSF portal | Scientific output for researchers — not interpretable by operators |
| Generic LLM chatbot | Hallucinates marine data, no real data, English only |
| Simple chatbot + weather API | No geofencing, no historical reasoning, no risk engine, no offline |

### 3.4 What ORCA fills

ORCA is the intelligent orchestration layer between authoritative Indian marine data infrastructure and the end user. It consumes the outputs of INCOIS, IMD, and MOSDAC, fuses them, reasons over them, and delivers a single plain-language, evidence-backed, localised answer with full explainability.

---

## 4. PROPOSED SOLUTION — ORCA PLATFORM

### 4.1 One-line pitch

> **ORCA is an Agentic Marine Intelligence System that converts heterogeneous Indian ocean observations into explainable operational decisions for fishermen, coastal authorities, and maritime operators — in their own language.**

### 4.2 Positioning

Call it: **"An agentic orchestration and decision layer over India's authoritative marine data infrastructure — delivering explainable maritime intelligence in regional languages."**

### 4.3 Core design philosophy

```
OBSERVE → UNDERSTAND → REASON → PREDICT → SIMULATE → DECIDE → EXPLAIN → ACT
```

Every component maps onto this chain. No step is skipped. Every output is auditable.

### 4.4 Differentiation table

| Typical hackathon solution | ORCA |
|---|---|
| One LLM + one weather API | Multi-agent planner over 15+ live data sources |
| Generic map overlay | H3-indexed Marine Digital Twin with per-cell marine state vector |
| English only | 10 Indian regional languages + voice I/O |
| Online only | Full offline mode with service workers + cached advisories |
| Single static recommendation | Risk-ranked candidates + evidence graph + rejected alternatives |
| No confidence score | Uncertainty engine — per-variable confidence + data freshness |
| LLM computes everything | LLM explains only — all computation is deterministic Python + ML |

---

## 5. TARGET USERS & PERSONAS

### Persona 1 — The Artisanal Fisherman (Primary)

**Name:** Ramesh | **Location:** Puri, Odisha | **Device:** Android 4G phone | **Language:** Odia  
**Vessel:** 8m fibreglass boat, 40HP outboard, max safe wave 2m, range 60km  
**Current behaviour:** Checks the sky, calls a fisherman friend, guesses  
**Pain point:** No way to know cyclone risk, restricted zones, or where fish actually are  
**What ORCA gives him:** Speaks to app in Odia, hears a spoken recommendation, sees colour-coded map, gets proactive push alert if conditions deteriorate overnight

### Persona 2 — The Disaster Management Officer (Secondary)

**Name:** Priya | **Role:** Coastal disaster preparedness, Andhra Pradesh  
**What ORCA gives her:** National Maritime Risk Grid showing coastal cells at AMBER/RED risk, communities needing alerts, resource pre-positioning guidance

### Persona 3 — The Coast Guard Officer (Secondary)

**Name:** Sub-Inspector Das | **Location:** Paradip, Indian Coast Guard  
**What ORCA gives him:** Vessels approaching EEZ boundaries, anomalous routes, nearest safe harbour, sea state for patrol vessel planning

### Persona 4 — The Marine Researcher (Tertiary)

**Name:** Dr. Kavitha | **Role:** Fisheries science, CMFRI, Kochi  
**What ORCA gives her:** Temporal analysis of SST anomalies, chlorophyll trends, historical PFZ correlations, automated anomaly detection over multi-year datasets

### Persona 5 — The Port / Shipping Operator (Tertiary)

**Name:** Suresh | **Role:** Operations Manager, Visakhapatnam Port  
**What ORCA gives him:** Sea-state risk by route, wave height consensus forecast, optimal departure/arrival windows, cyclone proximity alerts

---

## 6. USER STORIES

### Fisherman

| ID | As a fisherman I want to... | So that... | Priority |
|---|---|---|---|
| US-F01 | Ask in Odia whether it's safe to fish tomorrow | I don't need English or multiple portals | P0 |
| US-F02 | See the nearest PFZ zone on a map | I know where to sail before leaving | P0 |
| US-F03 | Know wave height at my planned zone | I can decide if my 8m boat can handle it | P0 |
| US-F04 | Get a phone alert if a cyclone is approaching | I can return before it's dangerous | P0 |
| US-F05 | Know if I'm approaching a restricted area | I don't cross a boundary accidentally | P0 |
| US-F06 | Ask by voice | I don't type on a moving boat | P1 |
| US-F07 | Use the app offline at sea | I still get my last-cached forecast | P1 |
| US-F08 | See the safest route to my fishing zone | I avoid dangerous corridors even if longer | P1 |
| US-F09 | Ask "what if I leave at 8 AM instead?" | I compare departure times before deciding | P2 |
| US-F10 | Set up my vessel profile once | The app gives me vessel-specific risk | P1 |

### Disaster Management

| ID | As a DM officer I want to... | Priority |
|---|---|---|
| US-D01 | See a national coastal risk grid | P1 |
| US-D02 | Get a proactive alert when risk crosses RED | P1 |
| US-D03 | See cyclone track with uncertainty cone | P1 |
| US-D04 | Download risk summaries | P2 |

### Coast Guard

| ID | As a Coast Guard officer I want to... | Priority |
|---|---|---|
| US-CG01 | Know which vessels are near EEZ boundaries | P2 |
| US-CG02 | Find nearest port from any coordinates | P1 |
| US-CG03 | Check sea state along planned patrol route | P1 |

### Researcher

| ID | As a researcher I want to... | Priority |
|---|---|---|
| US-R01 | Ask why productivity declined near Chilika in 2025 | P2 |
| US-R02 | See SST anomaly trends over 3 years | P2 |
| US-R03 | Query historical PFZ frequency for any cell | P2 |

---

## 7. SYSTEM ARCHITECTURE (COMPLETE)

### 7.1 Macro architecture

```
                              REAL WORLD
                                  │
         ┌────────────────────────┼────────────────────────┐
         ↓                        ↓                         ↓
    SATELLITE                   OCEAN                    WEATHER
  ISRO MOSDAC               INCOIS OSF                    IMD
  NASA OceanColor           Copernicus Marine           ERA5/CDS
  EOS-06 / OCM-3               HYCOM                  Open-Meteo
  SARAL/AltiKa                  Argo                   NCMRWF
  Oceansat-2 / SCATSAT-1    NOAA OISST

         ┌────────────────────────┼────────────────────────┐
         ↓                        ↓                         ↓
    GEOSPATIAL                 FISHING                  ECOLOGY
  Marine Regions EEZ          ISRO PFZ               Protected Planet
  World EEZ v12            Global Fishing Watch        MPA / OECM
  GEBCO 2026 Bathymetry    INCOIS PFZ Archive        Coral / Mangrove
  Territorial Seas          AIS / Vessel data         GBIF / OBIS

                       ┌──────────────────────────┐
                       │   DATA INGESTION LAYER    │
                       │  Celery + Redis + Airflow │
                       │  (scheduled pull jobs,    │
                       │   per-source adapters,    │
                       │   retry / backoff logic)  │
                       └────────────┬─────────────┘
                                    │
                       ┌────────────▼─────────────┐
                       │   NORMALISATION LAYER     │
                       │  Unit conversion,         │
                       │  Spatial alignment (H3),  │
                       │  Temporal resampling,     │
                       │  Quality Control (QC),    │
                       │  Cloud-mask application   │
                       └────────────┬─────────────┘
                                    │
                       ┌────────────▼─────────────┐
                       │    MARINE DATA FABRIC     │
                       │  MinIO (raw raster/NetCDF)│
                       │  PostGIS (vector/geo)     │
                       │  TimescaleDB (time-series)│
                       │  pgvector (embeddings)    │
                       │  Zarr (chunked arrays)    │
                       └────────────┬─────────────┘
                                    │
                       ┌────────────▼─────────────┐
                       │   MARINE DIGITAL TWIN     │
                       │  H3 resolution-7 grid     │
                       │  (~5km cell edge)         │
                       │  Per-cell state vector    │
                       │  (SST, chl, wave, wind,   │
                       │   current, tide, risk,    │
                       │   PFZ score, boundaries)  │
                       └────────────┬─────────────┘
                                    │
                       ┌────────────▼─────────────┐
                       │    AGENTIC PLANNER        │
                       │    (LangGraph)            │
                       │  State machine orchestrator│
                       │  Tool registry dispatch   │
                       │  Multi-turn memory        │
                       │  Cycle detection + timeout│
                       └─────┬──────┬──────┬──────┘
                             │      │      │
              ┌──────────────┼──────┼──────┼──────────────┐
              ↓              ↓      ↓      ↓              ↓
          WEATHER        OCEAN  FISHING  GEO         SATELLITE
          AGENT          AGENT  AGENT    AGENT        DISCOVERY
              └──────────────┼──────┼──────┼──────────────┘
                             │      │      │
                       ┌─────▼──────▼──────▼──────┐
                       │  ANOMALY DETECTION AGENT  │
                       │  RISK AGENT               │
                       │  SIMULATION AGENT         │
                       │  CONTEXT / MEMORY AGENT   │
                       └────────────┬─────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ↓                     ↓                      ↓
       SPATIO-TEMPORAL       UNCERTAINTY ENGINE     DECISION ENGINE
       REASONING ENGINE      (multi-source          (ranked candidates,
       (H3 neighbour ops,     disagreement,          optimal zone,
        temporal trends,      data freshness,        route selection)
        anomaly context)      confidence score)
              └─────────────────────┼─────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ↓                     ↓                      ↓
       EXPLANATION ENGINE   EVIDENCE GRAPH           PREDICTION CARD
       (cite every claim,   (visual factor tree,     GENERATOR
        rejected alts,       positive/negative        per-variable
        reasoning chain,     factors displayed)       confidence UI
        regional language)
              └─────────────────────┼─────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ↓                     ↓                      ↓
        CHAT / VOICE            GIS MAP               ALERT ENGINE
        (multilingual,          (MapLibre + deck.gl   (Web Push,
         voice I/O,              H3 overlay,           WebSocket,
         multi-turn context,     route render,         proactive
         Odia, Tamil, etc.)      zone shading,         monitoring)
                                 advisory layers)
              └─────────────────────┼─────────────────────┘
                                    ↓
                          ACTIONABLE DECISION
```

### 7.1a Client layer — two clients, one API *(built)*

The decision produced above is consumed by two independent clients over the
same HTTP surface. Neither holds business logic: both render what the
backend computed.

```
                    ┌───────────────────────────────┐
                    │   FastAPI  (single API layer)  │
                    │  /chat  /marine/*  /health     │
                    └───────┬───────────────┬────────┘
                            │               │
              ┌─────────────▼───┐   ┌───────▼──────────────────┐
              │  REACT PWA      │   │  NATIVE ANDROID APP       │
              │  (frontend/)    │   │  (android/)               │
              │  Vite + MapLibre│   │  Kotlin + Jetpack Compose │
              │  ChatPanel      │   │  Ask / Map / Route / Watch│
              │  MarineMap      │   │  MapLibre Native          │
              │  EvidencePanel  │   │  Foreground safety service│
              │  SafetyMonitor  │   │  Last-known-good cache    │
              │                 │   │                           │
              │  judges, desk,  │   │  fisherman, at sea,       │
              │  any browser    │   │  screen off, in a pocket  │
              └─────────────────┘   └───────────────────────────┘
```

**Why both, rather than PWA alone (revises §16.1):** the PWA remains correct
for judges, desk users and instant access with no install. But the single
most operationally important feature — continuous safety monitoring of the
vessel's own position while under way — is not something a browser tab can
do reliably. A backgrounded browser is throttled or suspended by the OS, and
a warning that arrives when the user next unlocks their phone is not a
warning. That capability requires an Android foreground service, so the
native client exists for the user who is actually on the water. See §10.7
and §16.7.

### 7.2 Data freshness policy

| Variable | Max acceptable staleness | Primary source | Fallback |
|---|---|---|---|
| Cyclone location / track | 30 minutes | IMD | INCOIS |
| Lightning warnings | 15 minutes | IMD nowcast | — |
| Wave forecast | 6 hours | INCOIS OSF | Copernicus Marine |
| Wind speed forecast | 6 hours | IMD / INCOIS | Open-Meteo Marine |
| SST live/NRT | 12 hours | INCOIS | MOSDAC OCM-3 |
| Tidal height | 1 hour | INCOIS tide model | — |
| PFZ advisory | 24 hours | ISRO MOSDAC | INCOIS |
| Chlorophyll (satellite) | 48 hours (cloud-dependent) | MOSDAC OCM-3 | NASA OceanColor |
| Ocean current | 12 hours | INCOIS OSF | HYCOM |
| SST historical baseline | Static monthly climatology | NOAA OISST | ERA5 |
| Geofencing boundaries | Weekly integrity check | Marine Regions | PostGIS local |
| Bathymetry | Static | GEBCO 2026 | — |
| Marine Protected Areas | Weekly integrity check | Protected Planet | Local PostGIS |

### 7.3 Multi-source redundancy matrix

| Variable | Source 1 | Source 2 | Source 3 | Consensus |
|---|---|---|---|---|
| SST | INCOIS | MOSDAC OCM-3 | NOAA OISST | Weighted mean; flag if >1°C spread |
| Wave height | INCOIS OSF | Copernicus Marine | Open-Meteo Marine | Ensemble mean; report std dev |
| Ocean current | INCOIS | Copernicus Marine | HYCOM | Ensemble mean; flag if >0.3 m/s spread |
| Wind speed | IMD | ERA5 | Open-Meteo | Ensemble mean; IMD highest priority |
| Chlorophyll | MOSDAC OCM-3 | NASA OceanColor | Copernicus BGC | Weighted by cloud-free coverage |

### 7.4 Request-path latency architecture *(built)*

The system's read latency is deliberately decoupled from its sources'
latency. Three rules, each of which came out of a measured failure:

**1. Cache what is time-invariant, not what is current.**
Tide was originally cached as "the height right now", which forces a short
TTL, which means the expensive computation recurs forever. It is now cached
as a **28-hour predicted series** and the current height is interpolated out
of it per request. Astronomical tide is deterministic, so a series computed
this morning is still exactly correct this evening — a 12h TTL costs nothing
in freshness. Same principle applies to any harmonic or ephemeris quantity.

**2. A cold cache must never block a request.**
An uncached tide point returns `status: "computing"` immediately and
schedules the work in a deduplicated background task; the next request for
that point gets a real value. The user waits for nothing that will be
identical whenever it is calculated.

**3. Bound the expensive resource, not the request.**
Per-source timeouts are per-agent, never wrapped around a whole
`asyncio.gather` (one slow source must not discard fast successful ones).
Blocking SDK calls go through a dedicated `network_executor`, never
asyncio's shared default pool. Concurrent Copernicus dataset opens are
capped. Route verification is bounded to 3 candidates — run concurrently,
so the caller waits for the slowest rather than the sum.

**Measured effect (27 Aug 2026, same machine, same points):**

| Endpoint | Before | After |
|---|---|---|
| `/marine/state` (cold) | 34.8 s | 2.5 s |
| `/marine/state` (warm) | 20.5 s | 0.4 s |
| `/chat` | 23.7 s | 4.3 s |
| `/marine/quick-check` (warm) | 0.06 s | 0.06 s |
| Ocean sources returned | 0 — agent timed out and its result was discarded | 5, including tide |

The last row matters more than the timings: the old path was not merely slow,
it was **returning a risk assessment computed with no ocean data at all**,
because the Ocean Agent exceeded the endpoint's 25 s per-agent budget and was
replaced with an empty state. Fixing latency here restored correctness, not
just speed.
---

## 8. AGENT DESIGN — ALL AGENTS, INPUTS, OUTPUTS, TOOLS

### 8.0 Master Orchestrator — Agentic Planner *(built)*

**Framework:** LangGraph | **LLM:** Groq `openai/gpt-oss-120b` (primary), **rule-based parser (no LLM) as a full fallback**  
**Per-agent timeout:** 25s | **Total query timeout:** 115s

**As-built graph:**
```
parse_intent → resolve_location → execute_tools → synthesize_answer
```

**The LLM does exactly two jobs, and neither is arithmetic:**
1. `parse_intent` — natural language → structured parameters
2. `synthesize_answer` — phrase a final answer from an already-built evidence receipt

Everything between those two nodes is deterministic Python and SQL. No agent
asks a model to compute or estimate a physical value.

#### The LLM is optional, not a dependency *(built)*

`app/planner/rule_based.py` provides a regex/keyword intent parser and a
template answer renderer that reads the same `EvidenceReceipt` directly. It
engages automatically whenever `GROQ_API_KEY` is unset **or a live call fails
for any reason** — quota, network, malformed JSON — not merely when the
system is "unconfigured". Verified end-to-end with the key removed entirely:
geocoding, all five marine agents, risk scoring, evidence aggregation and
answer rendering all ran with zero LLM calls.

The rule-based renderer is *structurally* incapable of hallucinating: it only
ever repeats fields already present in the receipt and never generates new
text. This is the strongest possible form of NFR-10, and it is worth stating
plainly to evaluators — the system's safety-critical output path does not
require a language model to be correct, or even to be reachable.

`resolve_location` resolves position in strict priority order, so an explicit
instruction always beats an inference:
1. coordinates or a place name in **this** message (geocoded via Nominatim, cached 7 days)
2. a location established **earlier in this session** (Context & Memory Agent — makes "what about tomorrow?" work)
3. the client's own reported GPS position, last resort only

**LangGraph state schema:**
```python
class MasterState(TypedDict):
    messages: list[BaseMessage]
    user_profile: UserProfile
    query_intent: str
    required_agents: list[str]
    agent_outputs: dict[str, AgentOutput]
    marine_state: MarineState
    risk_score: float
    confidence: float
    uncertainty_flags: list[str]
    candidate_zones: list[FishingZone]
    recommended_zone: FishingZone | None
    route: Route | None
    evidence: EvidenceGraph
    response_language: str
    turn_count: int
    session_id: str
```

---

### 8.1 Weather Agent

**Data sources:** IMD API (primary) → INCOIS OSF → ERA5 → Open-Meteo

**Tools:**
```
get_current_weather(lat, lon)
get_weather_forecast(lat, lon, hours_ahead)
get_cyclone_list()
get_cyclone_track(cyclone_id)
get_cyclone_windfield(cyclone_id, lat, lon)
get_lightning_risk(lat, lon, time_window_hours)
get_rainfall_forecast(lat, lon)
get_weather_historical_baseline(lat, lon, month)
```

**Output dataclass:**
```python
@dataclass
class WeatherState:
    wind_speed_ms: float
    wind_direction_deg: float
    wind_gust_ms: float
    precipitation_probability: float
    rainfall_mm_24h: float
    atmospheric_pressure_hpa: float
    visibility_km: float
    cyclone_active: bool
    cyclone_name: str | None
    cyclone_category: int | None
    cyclone_distance_km: float | None
    cyclone_eta_hours: float | None
    cyclone_track_uncertainty_km: float | None
    lightning_probability: float
    weather_suitability_score: float   # 0-100
    sources_used: list[str]
    data_freshness: dict[str, datetime]
    multi_source_agreement: float
```

---

### 8.2 Ocean Agent

**Data sources:** INCOIS OSF (primary) → Copernicus Marine → HYCOM → NOAA OISST → Argo → INCOIS tide model

**Tools:**
```
get_wave_forecast(lat, lon, time)
get_wave_period(lat, lon, time)
get_swell_forecast(lat, lon, time)
get_ocean_current(lat, lon, depth_m, time)
get_ocean_sst(lat, lon)
get_ocean_sst_multi_source(lat, lon)
get_ocean_salinity(lat, lon)
get_sea_level_anomaly(lat, lon)
get_mixed_layer_depth(lat, lon)
get_tide(lat, lon, time)
get_d20(lat, lon)
get_argo_profile(lat, lon, radius_km)
```

**Output dataclass:**
```python
@dataclass
class OceanState:
    significant_wave_height_m: float
    wave_period_s: float
    swell_height_m: float
    swell_direction_deg: float
    current_u_ms: float
    current_v_ms: float
    current_speed_knots: float
    sst_c: float
    sst_sources: dict[str, float]
    sst_consensus: float
    sst_disagreement: float
    salinity_psu: float
    sea_level_anomaly_m: float
    tide_height_m: float
    tide_phase: str
    mixed_layer_depth_m: float
    d20_m: float
    subsurface_profile: ArgoProfile | None
    wave_height_multi_source: dict[str, float]
    wave_disagreement: float
    sources_used: list[str]
    data_freshness: dict[str, datetime]
```

---

### 8.3 Fishing Agent

**Data sources:** ISRO MOSDAC PFZ → INCOIS PFZ archive → MOSDAC OCM-3 → NASA OceanColor → GFW → BGC-Argo → GBIF/OBIS

**Tools:**
```
get_pfz(lat, lon, date)
get_chlorophyll(lat, lon, date)
get_chlorophyll_anomaly(lat, lon, month)
get_sst_anomaly(lat, lon, month)
get_fishing_effort(lat, lon, date_range)
get_species_habitat(species, lat, lon, season)
get_bgc_argo_profile(lat, lon, radius_km)
predict_fishing_suitability(feature_vector)
get_historical_pfz_frequency(lat, lon, month)
```

**ML model:** XGBoost Fishing Suitability Predictor (see Section 11.1)

**Output dataclass:**
```python
@dataclass
class FishingState:
    pfz_advisory_active: bool
    pfz_zone_geojson: dict | None
    pfz_confidence_tier: str
    chlorophyll_mg_m3: float
    chlorophyll_anomaly_sd: float
    sst_anomaly_sd: float
    fishing_effort_kwh_km2: float
    fishing_suitability_score: float
    candidate_zones: list[CandidateZone]
    dominant_productivity_driver: str
    historical_pfz_frequency_pct: float
    sources_used: list[str]
    data_freshness: dict[str, datetime]
```

---

### 8.4 Geo Agent

**Data sources:** Marine Regions EEZ (PostGIS) → Protected Planet MPA → GEBCO bathymetry → Custom restricted zones

**Tools:**
```
check_eez(lat, lon)
check_territorial_waters(lat, lon)
check_mpa(lat, lon)
check_restricted_zone(lat, lon)
get_bathymetry(lat, lon)
compute_route(start, end, vessel_draft, risk_weights)
analyze_route_risk(route_geojson, vessel_profile)
get_nearest_port(lat, lon)
get_boundary_distance(lat, lon)
get_geofencing_summary(lat, lon)
```

**Output dataclass:**
```python
@dataclass
class GeoState:
    inside_indian_eez: bool
    eez_name: str
    inside_territorial_waters: bool
    inside_mpa: bool
    mpa_name: str | None
    inside_restricted_zone: bool
    restriction_reason: str | None
    bathymetry_m: float
    bathymetry_safe_for_vessel: bool
    nearest_port_name: str
    nearest_port_distance_km: float
    nearest_port_coords: tuple[float, float]
    boundary_distances: dict[str, float]
    recommended_route: Route | None
    safe_operational_area_geojson: dict
```

---

### 8.5 Risk Agent *(built — supersedes the flat score below)*

#### The constraint hierarchy: some constraints veto, others only rank

This is the single most important correction in v2.1, and it fixed a real
defect rather than a hypothetical one.

The original design (the composite formula below) was a single flat additive
score. Under it, an MPA violation contributed **+20 points** — so a spot
*inside a legally protected area* could still be returned as "LOW risk" if
every other factor happened to be favourable. A legal prohibition was
competing on a numeric scale with wave height, and losing.

The built system runs **two stages**, in order:

**Stage 1 — `check_hard_constraints()`. Vetoes. Runs first, independently of
any scoring.** A candidate that trips any of these is returned immediately
as `risk_level="REJECTED"` with `factor_breakdown={}` and is never scored:
- inside a Marine Protected Area
- wave height above the certain-capsize threshold for the vessel
- water depth below vessel draft plus safety margin (grounding)
- the point is on land
- distance from nearest port exceeds the vessel's operational range

**Stage 2 — additive 0–100 scoring.** Runs *only* on candidates that survived
Stage 1. Every point is individually attributable to a named factor.

**Consequences that must not be undone:**
- A `REJECTED` result has **no meaningful score**. Its empty `factor_breakdown`
  is correct output, not missing data, and no UI may render it on the same
  0–100 scale as a scored result (see §16.7).
- `route_agent.py` and `route_optimizer.py` call this exact same function —
  not a re-implemented inline check — so "what counts as a veto" has one
  definition system-wide.
- **A new legal or safety constraint belongs in Stage 1, never as a
  `factor_breakdown` entry.** A new hazard that should influence ranking
  among already-legal candidates belongs in Stage 2, and needs both a
  breakdown entry and an `explanation` line.

Regression-tested in `tests/test_risk_agent.py`.

**Composite risk formula** (Stage 2 only — this now ranks survivors, it does
not decide legality):
```
Operational Risk Score (0–100) =
  w1 × wave_risk_factor(wave_height, vessel_max_safe_wave)
+ w2 × wind_risk_factor(wind_speed, vessel_wind_threshold)
+ w3 × cyclone_risk_factor(cyclone_distance, cyclone_category)
+ w4 × lightning_risk_factor(lightning_probability)
+ w5 × boundary_risk_factor(boundary_distances)
+ w6 × bathymetry_risk_factor(depth, vessel_draft)
+ w7 × precipitation_risk_factor(rainfall_intensity)
+ w8 × visibility_risk_factor(visibility_km)
+ w9 × current_risk_factor(current_speed, engine_power)

Vessel class weights:
  Small fishing boat (<10m): w1=0.35, w3=0.22
  Medium trawler (10-20m):   w1=0.25, w3=0.20
  Large vessel (>20m):       w1=0.15, w3=0.18
```

**Risk tiers** *(as built — names differ from the v2.0 draft above)*:

| Tier | Score | Meaning |
|---|---|---|
| `LOW` | 0–24 | Safe to proceed |
| `MODERATE` | 25–49 | Proceed with caution |
| `HIGH` | 50–74 | Strongly advise against departure |
| `EXTREME` | 75–100 | Do not proceed — return to port if at sea |
| `REJECTED` | *(none)* | **Stage 1 veto.** Not permitted or not survivable. No score exists. |
| `INSUFFICIENT_DATA` | *(none)* | Too many inputs missing to score honestly. Refuses to guess. |

The last two are not points on the scale — they are separate outcomes, and
must be presented as such.

**Output schema** *(as built — `app/models/schemas.py`)*:
```python
class HardConstraintResult(BaseModel):
    vetoed: bool = False
    reasons: list[str] = []          # why, in plain language, one per veto

class RiskAssessment(BaseModel):
    risk_score: int                  # 0-100; meaningless when vetoed
    risk_level: str                  # LOW/MODERATE/HIGH/EXTREME/REJECTED/INSUFFICIENT_DATA
    factor_breakdown: dict[str, int] # factor name -> points contributed; {} when vetoed
    explanation: list[str]           # human-readable "X -> +N" lines
    hard_constraints: HardConstraintResult
    insufficient_confidence: bool = False
    confidence_reason: str | None = None
```

`vetoed=True` together with `risk_level != "REJECTED"` is an internal
contradiction and is caught by the Validation Agent (§8.11).

---

### 8.6 Satellite Discovery Agent

**Data sources:** NASA CMR API → MOSDAC Download API → NASA OceanColor file search

**Tools:**
```
search_satellite_archive(bbox, date_range, variable, sensor)
search_mosdac_archive(dataset_id, date_range, bbox)
get_latest_chlorophyll_granule(bbox)
get_latest_sst_granule(bbox)
get_cloud_cover_estimate(granule_id)
check_data_availability(lat, lon, variable, date)
```

---

### 8.7 Anomaly Detection Agent

**Detects:** SST anomaly, chlorophyll anomaly, wave anomaly, current anomaly, marine heatwave

**Models:**
1. Statistical Z-score: `(current - climatological_mean) / climatological_std`
2. Isolation Forest (unsupervised) — trained on 10+ years of H3-cell feature vectors

**Tools:**
```
compute_sst_anomaly(lat, lon, current_sst, month)
compute_chlorophyll_anomaly(lat, lon, current_chl, month)
detect_marine_heatwave(lat, lon)
get_historical_marine_state(lat, lon, date_range)
run_isolation_forest(h3_cell_state)
```

**Output:** Anomaly flag, Z-score magnitude, duration (days), temporal trend, plain-language interpretation

---

### 8.8 Simulation Agent (Counterfactual Engine)

**Supported scenario modifications:**
- Departure time (different hour → wave/wind/tide state changes)
- Weather scenario (cyclone track shift, storm intensity)
- Vessel change (different class → different risk weights)
- Range constraint (go only X km from shore)
- Date shift (tomorrow vs day-after vs next week)

**Process:** Accept base_state + parameter_override dict → re-query only affected agents → run Risk + Decision engines → return delta summary

---

### 8.9 Explanation & Evidence Agent

**Hard constraints (enforced in system prompt):**
- NEVER compute any numeric value — only narrate pre-computed values
- Every claim must cite a specific tool output with its timestamp
- Must show rejected alternatives with reasons
- Must state confidence score and data freshness concerns
- Must respond in the user's detected language

**Output structure per response:**
```
RECOMMENDATION (1–2 sentences, user's language)
EVIDENCE (cited data points with source and timestamp)
REJECTED ALTERNATIVES (zones/routes rejected + reason)
UNCERTAINTY (confidence %, data freshness, model disagreement)
DATA SOURCES USED (source name + last updated)
RECOMMENDED ACTION (plain language, user's language)
VOICE OUTPUT (TTS if voice mode enabled)
```

**As built — the receipt is a structured object, not prose.** Deterministic
aggregation happens *before* any language model is involved, producing one
`EvidenceReceipt` that the synthesis step is fed and the UI renders directly:

```python
class EvidenceReceipt(BaseModel):
    decision_id: str | None
    recommendation_summary: str
    risk_score: int | None
    risk_level: str | None
    factor_lines: list[str]            # already human-readable "X -> +N"
    sources_used: list[str]
    data_freshness: dict[str, str]     # source -> timestamp
    data_gaps: list[str]               # what we did NOT know
    rejected_alternatives: list[str]   # the "why not?" list
    confidence_statement: str
    validation_note: str | None        # from the Validation Agent (§8.11)
    location_lat: float | None
    location_lon: float | None
    location_maps_url: str | None      # ready-to-click deep link
```

Two design points worth defending to evaluators:

- **`data_gaps` is a first-class field, not an afterthought.** What the system
  did not know is part of the answer, and both clients give it its own visible
  section rather than hiding it behind a toggle.
- **`location_*` exists because of a real failure.** An early answer told a
  user "the safest zone is 20 km at bearing 45°" with no way to actually find
  it without doing the trigonometry themselves. Both the LLM prompt and the
  rule-based renderer are now required to surface these when present.

---

### 8.10 Context & Memory Agent

**Memory layers:**
- Short-term (session): conversation history, current query chain, agent outputs
- Long-term (cross-session): vessel profile, home port, language preference, alert subscriptions
- Alert subscriptions: active monitoring + push notification queue

**Persistence:** PostgreSQL (profiles, subscriptions) + Redis (session state, recent agent outputs)

**As built:** Redis-backed per-session conversation history with a 1-hour TTL.
This is what lets a follow-up question resolve its location from earlier in
the same session without the user repeating it.

---

### 8.11 Validation / Critic Agent *(built — new in v2.1)*

The PRD's "safety net" layer, made concrete. Runs after the Risk Agent and
before any result reaches the user. Two classes of check:

**Physical plausibility** — bounds on every value that reached the fusion
layer. A wave height of 40 m or a negative wind speed is a source or parsing
fault, not weather, and must be surfaced rather than scored.

**Internal contradiction** — cross-field consistency that can only fail if
our own wiring broke. The canonical example: `hard_constraints.vetoed == True`
while `risk_level != "REJECTED"` means the two-stage pipeline in §8.5 has
been mis-wired, and no answer built on it should be trusted.

Output is `ValidationResult{valid, issues[]}`; issues propagate into the
evidence receipt's `validation_note` and are rendered in red by both clients.
A validation failure downgrades confidence to zero rather than being silently
dropped.

---

### 8.12 Route Optimizer v2 — A* over an H3 risk graph *(built)*

The PRD's §11.3 design, implemented. Complements — does not replace — the
fast candidate scan in the Route Agent.

| | Route Agent (v1) | Route Optimizer (v2) |
|---|---|---|
| Endpoint | `/marine/safest-route` | `/marine/optimize-route` |
| Method | 16 candidate zones (8 bearings × 2 rings), ranked | A* search over an H3 hex graph (NetworkX) |
| Edge weight | — | Real Risk Agent scores per cell |
| Vetoed cells | Excluded from ranking | **Removed from the graph entirely** |
| Data per point | Open-Meteo only (fast) | Open-Meteo only (fast) |
| Typical cost | seconds | tens of seconds |

**H3 resolution 5 (~8.7 km edge), not 6.** Resolution 6 measured **251 s** for
a 25 km search: cell count grows quadratically with ring count, and res 5
cuts it roughly 4×. Recorded here because it is the kind of parameter that
looks like a free accuracy knob and is not.

**Two-phase pattern in v1, retained deliberately:** scan coarsely with one
fast source, then run the *full* multi-source fusion on the winner. The scan
does not skip real fusion, it defers it — and the detailed re-check is
allowed to **overrule** the scan. It has to be: a real query once returned
`found_safe_zone: true` for a destination that the detailed re-check had
itself just scored `REJECTED` (on land), while the recommendation text still
quoted the scan's stale "LOW risk". The verification now walks candidates in
ascending risk order and accepts the first whose full check also clears
Stage 1, bounded to 3 attempts and run concurrently.

---

## 9. DATA SOURCES — COMPLETE STACK

### 9.1 TIER 1 — ABSOLUTELY ESSENTIAL (Core)

#### Indian Primary Sources

| Source | Full Name | Data Provided | Access | Notes |
|---|---|---|---|---|
| ISRO MOSDAC | Met & Oceanographic Satellite Data Archival Centre | SST, Chlorophyll, Ocean colour, Wind vectors (OCM-3, SCAT-3, SSTM), SARAL altimetry, PFZ advisory | MOSDAC Download API (free registration) | 5,000-file/day limit; bbox + date filtering |
| EOS-06 / Oceansat-3 OCM-3 | Ocean Colour Monitor 3rd generation | Chlorophyll-a, ocean colour, optical properties, PAR, SST, biological indicators | Via MOSDAC | Daily analysed chlorophyll products |
| Oceansat-2 OCM | Ocean Colour Monitor (legacy) | Chlorophyll, phytoplankton, suspended sediment, historical productivity | Via MOSDAC | Historical baseline for climatology |
| SCATSAT-1 / SCAT-3 | Scatterometer satellites | Ocean surface wind vectors (speed + direction) | Via MOSDAC | Wind data for fishing + cyclone research |
| SARAL/AltiKa | ISRO-CNES altimeter mission | Sea surface height, sea level anomaly, ocean dynamics | MOSDAC + AVISO | Current strength + SLA anomaly |
| INCOIS OSF | Ocean State Forecast | Wave height, period, swell, currents, SST, MLD, D20, tides, oil-spill trajectories | INCOIS ERDDAP (erddap.incois.gov.in) | 5–7 day forecast; operational Indian Ocean system |
| INCOIS PFZ | Potential Fishing Zone advisory | PFZ zone polygons; combines SST, chl, currents, winds, altimetry, GIS | INCOIS PFZ portal + archive | Archive back to 2003 — critical training labels |
| INCOIS Data Holdings | Full in-situ archive | Argo, moored buoys, AWS, drifting buoys, HF radar, RAMA, tide gauges, wave-rider buoys | INCOIS data holdings portal | Many series extend back decades |
| INCOIS Digital Ocean (ESSDP) | Earth System Science Data Portal | Integrated in-situ + spatial ocean data | incois.gov.in/essdp | Deep historical research queries |
| INCOIS Tsunami / Sea Level | Indian Tsunami Early Warning System | Tide gauge network, BPRs, real-time sea level, storm surge | tsunami.incois.gov.in | Disaster management mode |
| IMD | India Meteorological Department | Weather obs, forecast (10-day), cyclone track + windfield, lightning nowcast, rainfall QPF | api.imd.gov.in | Primary weather authority; cyclone + lightning |

#### Global Ocean Sources

| Source | Data Provided | Access | Notes |
|---|---|---|---|
| Copernicus Marine | Physics reanalysis (currents, T, S, SL), waves, biogeochemistry (chl, O2, nutrients) | copernicusmarine Python toolbox; NetCDF/Zarr/CSV | Free registration |
| HYCOM | SST, salinity, currents, sea level, 3D T/velocity (~1/12°, 8-day forecast) | THREDDS/OPeNDAP; hycom.org/dataserver | Key for multi-source disagreement detection |
| NOAA OISST v2.1 | Global daily 1/4° SST from 1981–present | NOAA ERDDAP; NCEI direct | Historical SST baseline for anomaly computation |
| ERA5 | Hourly atmospheric reanalysis 1940–present: wind, waves, T, P, precipitation, SST | Copernicus Climate Data Store (CDS) Python API | Historical atmospheric baseline |
| World Ocean Atlas 2023 | T, S, O2, phosphate, nitrate, silicate at standard depths | NCEI direct download | Deep ocean climatology |
| Argo GDAC | Float profiles: T/S/pressure/depth + BGC (O2, chlorophyll, nitrate) | argo.ucsd.edu/data; Argovis API | BGC-Argo adds subsurface biogeochemistry |

#### Satellite Archives

| Source | Data Provided | Access |
|---|---|---|
| NASA OceanColor | MODIS Aqua/Terra, VIIRS, SeaWiFS — Level 2/3 chlorophyll, ocean colour, PAR | oceandata.sci.gsfc.nasa.gov |
| NASA CMR | All NASA Earth data granule search: bbox, temporal, polygon filters | cmr.earthdata.nasa.gov (no auth) |

### 9.2 TIER 2 — GEOSPATIAL & BOUNDARY (Required for Geofencing)

| Source | Data Provided | Format | Access |
|---|---|---|---|
| Marine Regions World EEZ v12 | EEZ (200nm), territorial seas (12nm), contiguous zones, internal waters, high seas, extended continental shelf | Shapefile / GeoPackage | marineregions.org/downloads.php (free) |
| Protected Planet API v4 | Marine Protected Areas, OECMs (post-2025 WDPA + WD-OECM merger) | GeoJSON via API | api.protectedplanet.net (non-commercial) |
| GEBCO 2026 | Global 15-arc-second bathymetry/topography | NetCDF grid | gebco.net/data-products (free) |

#### 9.2a GEBCO ingestion — verified regional tiles, not one national file *(built)*

**Never fetch a large OPeNDAP subset without verifying the values landed.**
An India-wide GEBCO request (25° × 35°, ~101 MB) came back **96% zeros past
roughly the first 200 rows** — silently truncated and zero-filled, with no
error raised at any layer. Every downstream depth lookup then returned
"0 m / land", which in the built system means a *grounding veto*: the bug
would have quietly refused every fishing ground in India while looking like
correct, conservative behaviour.

Ingestion is therefore **~1° × 1° tiles**, each passing three gates before it
is allowed to touch `data/raw/` (`scripts/fetch_gebco_regions.py`):

| Gate | Threshold | Catches |
|---|---|---|
| Nonzero fraction | > 85% | Truncated / zero-filled transfer |
| Elevation bounds | −11 500 m … 9 000 m | Corrupt or misinterpreted values |
| Distinct values | ≥ 10 | A constant tile, which is not terrain |

A tile that fails is reported and **not saved**. Adding a region is
`--add NAME lat_min lat_max lon_min lon_max`.

**Source:** GEBCO_2026 via the CEDA/BODC THREDDS OPeNDAP endpoint
(`dap.ceda.ac.uk/thredds/dodsC/bodc/gebco/global/gebco_2026/ice_surface_elevation/netcdf/GEBCO_2026.nc`).

**Loaded coverage:**

| Tile | Lat | Lon | Purpose |
|---|---|---|---|
| `kochi` | 9.30–10.30 | 75.30–76.30 | Arabian Sea demo |
| `chennai` | 12.60–13.60 | 79.80–80.80 | Coromandel demo |
| `vizag` | 17.20–18.20 | 82.90–83.90 | Primary Andhra demo point |
| `puri` | 19.30–20.30 | 85.30–86.30 | Odisha — original |
| `paradip` | 19.80–20.80 | 86.30–87.30 | Odisha — Mahanadi mouth, Paradip port |
| `puri_offshore` | 18.80–19.80 | 85.30–86.30 | Odisha — deep water south of Puri |
| `odisha_se_offshore` | 19.00–20.00 | 86.30–87.30 | Odisha — SE offshore |
| `gopalpur` | 18.80–19.80 | 84.40–85.40 | Odisha — Chilika / Gopalpur |

Contiguous Odisha coverage now spans **18.8–20.8 N, 84.4–87.3 E**. A point
outside every loaded tile returns `status: "unavailable"` — explicitly not a
depth of zero, because "we have no data here" and "this is land" must never
be the same answer.

**Correction to a previously documented finding.** Project notes recorded that
"0 m depth extends tens of km offshore near the Mahanadi delta", which was
used to rule Odisha out as a demo region. Measured against the loaded tiles,
the transect due south of Puri at 85.83 E reads **26 m at 11 km, 16 m at
22 km, 413 m at 33 km** — good working water. The earlier note conflated the
Puri *coastline* (correctly 0 m and land-vetoed) with the water offshore of
it. Odisha is a viable demo region; see §27.2.

### 9.3 TIER 3 — EXTRA-MILE DATA (Differentiators)

| Source | Data Provided | Why It Matters | Access |
|---|---|---|---|
| Global Fishing Watch (GFW) | Historical fishing effort (kW-hours/km², daily 2012–present), vessel presence, AIS-derived activity, vessel identity, events | Validates PFZ against actual historical fishing — far better than PFZ alone | globalfishingwatch.org/our-apis; free research |
| BGC-Argo | Dissolved oxygen, chlorophyll, nitrate profiles | Subsurface ocean intelligence — thermocline, below-surface productivity | Argovis API; argo.ucsd.edu/data |
| GBIF / OBIS | Marine species occurrence by location, date, season | "Which fish historically appear in this temperature/chlorophyll regime?" | api.gbif.org (free, no auth) |
| Marine Heatwave derived layer | Persistent SST anomaly detection vs OISST percentile baseline | Answers "why has productivity declined?" with temporal evidence | Derived from OISST + ERA5 internally |
| HF Radar current data | Near-real-time coastal current observations (select INCOIS stations) | Ground truth for current model validation near coast | INCOIS data holdings |
| Coral / Mangrove / Seagrass | Coastal ecosystem distribution polygons | Conservation mode, ecological zone awareness | UNEP-WCMC (free research) |
| Open-Meteo Marine API | Wave height, period, swell, wind wave, current direction — hourly, global | Third independent wave source; no registration, free | api.open-meteo.com/v1/marine |

---

## 10. TECHNOLOGY STACK (FULL, JUSTIFIED)

### 10.1 Frontend

| Component | Technology | Version | Purpose | Justification |
|---|---|---|---|---|
| Core framework | React | 18.3 | Component-based UI | Industry standard; excellent ecosystem |
| Language | TypeScript | 5.5 | Type safety across all frontend | Prevents runtime errors in geo/data handling |
| Build tool | Vite | 5.4 | Fast HMR dev + optimised production build | Significantly faster than CRA; native ESM |
| PWA layer | Vite PWA plugin | 0.20 | Service worker generation, manifest, offline | Workbox-based; precaching + runtime caching |
| Service worker | Workbox | 7.x | Offline caching strategy per route/asset | NetworkFirst for live data, CacheFirst for static tiles |
| Map engine | MapLibre GL JS | 4.x | Vector tile map, raster overlay | Open-source (no Mapbox billing risk); WebGL; deck.gl compatible |
| High-perf geo rendering | deck.gl | 9.x | H3HexagonLayer, ScatterplotLayer, PathLayer, HeatmapLayer | WebGL-accelerated; handles 100k+ H3 cells at 60fps |
| Client-side geo | Turf.js | 6.5 | Distance, buffer, intersect in browser | No server round-trip for local spatial calculations |
| H3 frontend | h3-js | 4.1 | H3 grid operations in browser | Official Uber H3 WASM port; consistent with backend |
| State management | Zustand | 4.5 | Global frontend state | Lightweight; no boilerplate; TypeScript-first |
| Data fetching | TanStack Query | 5.x | API caching, background refetch, stale-while-revalidate | Critical for ocean data that must stay fresh |
| Real-time alerts | Native WebSocket API | — | Push notifications from backend | Persistent connection for cyclone/wave alerts |
| Voice input | Web Speech API (browser) | — | Voice-to-text (English); fallback to Whisper API | Fallback to Google Cloud STT for Indian languages |
| Charts | Recharts | 2.12 | Time-series wave height, SST trend, risk history | React-native; composable; TypeScript-first |
| Styling | Tailwind CSS | 3.4 | Utility-first, consistent UI | Rapid development; consistent spacing and colour |
| Internationalisation | i18next + react-i18next | 23.x | UI strings for 10 Indian languages | Industry standard; lazy loading; pluralisation rules |
| Component testing | Vitest + Testing Library | 1.x | Unit + integration tests | Vite-native; faster than Jest in this setup |
| 3D globe (stretch) | CesiumJS | 1.120 | 3D globe H3 grid + cyclone track (Phase 3) | Open-source; impressive visual for final demo |

### 10.2 Backend

| Component | Technology | Version | Purpose | Justification |
|---|---|---|---|---|
| API framework | FastAPI | 0.112 | Async REST + WebSocket API server | Native async; auto OpenAPI docs; Pydantic validation |
| Language | Python | 3.11+ | All backend, data engineering, ML | Best ocean/geo library ecosystem |
| Data validation | Pydantic | 2.8 | Request/response schema validation | FastAPI-native; strict typing throughout |
| ASGI server | Uvicorn + Gunicorn | 0.30 | Production ASGI server | Multi-worker; production-grade |
| Task queue | Celery | 5.4 | Scheduled ingestion jobs, background ML inference | Distributed task execution; retry/backoff; cron |
| Message broker | Redis | 7.2 | Celery broker + API cache + session state | Fast in-memory; Celery-native; TTL-based caching |
| WebSocket | FastAPI WebSocket | native | Push alerts to PWA clients | Zero additional library |
| Agent framework | LangGraph | 0.2 | State-machine multi-agent orchestration | Explicit state machines; cycle detection; human-in-the-loop support |
| LLM primary *(built)* | Groq `openai/gpt-oss-120b` | — | Intent parsing + final phrasing **only** | Generous free tier; ~0.6s measured for a trivial call. Replaced Gemini (see below) |
| LLM fallback *(built)* | **None — rule-based Python** | — | Same two jobs, no model | `app/planner/rule_based.py`. Cannot hallucinate by construction; see §8.0 |

**Why Groq replaced Gemini (26 Aug 2026).** Not a technical failure of Gemini:
its free tier allowed 20 requests/day, which development testing exhausted.
The lesson worth recording is the *debugging* failure, not the quota. Every
symptom looked like a network hang — ~20 s stalls, timeouts, retries — and
two full sessions were spent on async and timeout fixes. The actual cause was
an **instant `429 RESOURCE_EXHAUSTED`** being swallowed by a bare
`except Exception: return None`. One line printing `type(exc).__name__` found
it immediately.

This is now a standing rule: **an adapter or LLM call must never swallow an
exception without recording its type and message.** "It's probably just slow"
is a guess, not a diagnosis. The async fixes made along the way were correct
and were kept — but they were not the bug.

Groq is still a free-tier third-party API. The rule-based fallback exists
precisely because that will eventually be exhausted too, and must not be
removed on the assumption that Groq solved the problem permanently.
| Structured output | Pydantic + Gemini structured mode | — | Force LLM to return typed outputs | Prevents hallucination in data extraction |
| Voice STT | Google Cloud Speech-to-Text | v2 | Server-side Indian language recognition | Best Indian language model accuracy (Odia, Tamil, Bengali, Hindi) |
| Voice TTS | Google Cloud Text-to-Speech | v1 | Voice output in regional languages | WaveNet voices for Hindi, Tamil, Bengali, Malayalam, Telugu |
| Language detection | langdetect + LLM verify | — | Auto-detect input language | langdetect for speed; LLM for ambiguous cases |
| Data pipeline (production) | Apache Airflow | 2.9 | DAG-based scheduled ingestion from 15+ sources | Explicit dependency graphs; failure alerting; retry |
| Data pipeline (internal round) | Prefect | 2.x | Simpler DAG orchestration | Python-native; faster setup; migrate to Airflow for production |

### 10.3 Data Engineering

| Component | Technology | Version | Purpose | Justification |
|---|---|---|---|---|
| NetCDF/raster reading | xarray | 2024.6 | Read/process/subset NetCDF ocean data | Standard for N-dimensional labelled arrays; Zarr-compatible |
| Raster processing | rasterio | 1.3 | Read/write GeoTIFF, cloud masks, reproject | Industry standard for raster I/O |
| GDAL bindings | GDAL / osgeo | 3.9 | Format conversion, projection, warping | Foundational geo library |
| Zarr store | Zarr | 2.18 | Cloud-optimised chunked array storage | Fast partial reads of large NetCDF by lat/lon/time chunk |
| Geospatial analysis | GeoPandas | 1.0 | Vector GIS operations, boundary processing | Pandas-compatible; PostGIS round-trips |
| Geometry | Shapely | 2.0 | Geometric operations (intersect, buffer, within) | GeoPandas-native; GEOS-backed |
| ERDDAP access | erddapy | 2.0 | Unified ERDDAP protocol client for INCOIS + NOAA | Single interface for multiple ERDDAP-compliant sources |
| Copernicus Marine | copernicusmarine | 1.3 | Official Copernicus Marine Toolbox | Spatial + temporal subsetting; NetCDF/Zarr/CSV |
| NASA CMR | pystac-client + requests | — | STAC/CMR granule search | Programmatic satellite archive search |
| H3 indexing | h3 (Python) | 3.7 | Convert all lat/lon to H3 cells; kring queries | Uber H3; efficient spatial indexing |
| Large raster (stretch) | Apache Sedona | 1.6 | Distributed raster processing for historical archives | Spark-based; needed if single-node xarray too slow |

### 10.4 Databases

| Database | Version | Purpose | Justification |
|---|---|---|---|
| PostgreSQL | 16 | Primary relational database | ACID; PostGIS; TimescaleDB; pgvector all extend Postgres |
| PostGIS | 3.4 | Geospatial extension | Industry standard for vector GIS in SQL |
| pgvector | 0.7 | Vector similarity search | Powers RAG-based "find similar past marine conditions" queries |
| TimescaleDB | 2.15 | Time-series optimised extension | Automatic time partitioning; fast time-range queries |
| Redis | 7.2 | Cache + broker + session | Sub-ms latency; TTL expiry; Celery-native |
| MinIO | RELEASE.2024 | S3-compatible object storage for raw raster/NetCDF | Self-hosted; S3 API compatible |

### 10.5 Machine Learning

| Component | Technology | Version | Purpose |
|---|---|---|---|
| Gradient boosted trees | XGBoost | 2.1 | Fishing Suitability Predictor (tabular features) |
| Alternative tree model | LightGBM | 4.4 | Comparative model for ensemble or A/B |
| Anomaly detection | scikit-learn (Isolation Forest) | 1.5 | Per-cell ocean state anomaly flagging |
| Statistical anomaly | Z-score (scipy) | — | Baseline anomaly: deviation from climatological mean |
| Time-series forecasting | PyTorch (LSTM / TFT) | 2.3 | Short-term condition forecasting |
| Seasonal decomposition | Prophet | 1.1 | Climatological baseline + seasonal patterns |
| Deep learning | PyTorch | 2.3 | All neural model training and inference |
| Experiment tracking | MLflow | 2.14 | Training runs, parameters, metrics, model versions |
| Route graph search | NetworkX + A* (custom) | — | H3 adjacency graph with risk-weighted edges |

### 10.6 DevOps & Infrastructure

| Component | Technology | Purpose |
|---|---|---|
| Containerisation | Docker | Reproducible environment for all services |
| Orchestration | docker-compose | Multi-service local and production deployment |
| Reverse proxy | Nginx | Static serving, HTTPS termination, API proxy, gzip |
| SSL | Let's Encrypt / Certbot | Free HTTPS with auto-renewal |
| Monitoring | Prometheus + Grafana | System metrics, API latency, ML model performance |
| Error tracking | Sentry (self-hosted) | Backend exception capture and alerting |
| Logging | structlog | Structured JSON logging throughout backend |
| Testing (backend) | pytest + httpx | Unit + integration tests (async-compatible) |
| Testing (frontend) | Vitest + Testing Library | Component + hook tests |
| CI/CD | GitHub Actions | Automated test + lint + deploy pipeline |
| Python linting | ruff | Fast Python linter + formatter |
| TypeScript linting | ESLint + Prettier | TypeScript/React linting |
| Dependency management | uv (Python) | 10–100x faster than pip; lock file support |

---

### 10.7 Native Android client *(built — new in v2.1)*

| Component | Technology | Purpose | Justification |
|---|---|---|---|
| Language | Kotlin 2.0 | All app code | Coroutines/Flow map cleanly onto an async API |
| UI | Jetpack Compose + Material 3 | All screens | No XML layouts; least boilerplate for a hackathon timeline |
| Map | MapLibre Native (Android SDK) | Basemap, route overlay, tap-to-query | Same engine and *same OSM raster style JSON* as the PWA — the two clients cannot disagree about the basemap, and neither needs a commercial tile key |
| HTTP | Retrofit + OkHttp | REST client | Interceptor rewrites the base URL at runtime |
| Serialisation | kotlinx.serialization | JSON ↔ typed models | Compile-time safety against the Pydantic schemas |
| Storage | DataStore (Preferences) | Settings, vessel profile | Async, no SharedPreferences footguns |
| Offline cache | JSON file cache | Last-known-good `/marine/state` | Deliberately simple; see §16.7 |
| Background work | Foreground `Service` | Live safety watch | Survives screen-off; WorkManager cannot poll at this cadence |
| Location | Fused Location Provider | Vessel position | Returns null rather than a stale fix — see below |
| DI | **None — manual `AppContainer`** | 6 singletons | Hilt would add a KSP round to every build and a Kotlin/AGP version matrix to maintain, to solve a problem this size does not have |
| Min / target SDK | 24 / 35 | — | API 24 covers the low-end Android that fishermen actually carry |

**Build status:** compiles clean — zero errors, zero warnings — on Microsoft
OpenJDK 17, Gradle 8.9, Android SDK platform 35 / build-tools 35.0.0. Debug
APK ~59 MB (unminified; MapLibre ships native `.so` for every ABI). 5 wire-
contract unit tests pass. **Not yet verified at runtime on a device or
emulator** — the code builds and its tests pass; that is not the same as
"the map renders".

**Location returns null rather than a stale fix.** Every judgement the system
makes is vessel-position-relative, so a silently wrong position produces a
confident, wrong safety verdict. Missing position is reported as missing.

---

## 11. MACHINE LEARNING MODELS (FULL SPECIFICATION)

### 11.1 Fishing Suitability Predictor

**Model type:** XGBoost — `XGBClassifier` with `predict_proba` output as continuous suitability score  
**Objective:** Binary classification — PFZ advisory issued (1) or not (0)  
**Training data:** INCOIS PFZ archive 2003–2025 cross-referenced with MOSDAC/Copernicus/ERA5 features  
**Retraining cadence:** Monthly as new PFZ observations accumulate

**Complete feature table:**

| Feature | Source | Type | Notes |
|---|---|---|---|
| SST (°C) | MOSDAC / INCOIS | Continuous | Raw value |
| SST anomaly (°C) | NOAA OISST climatology | Continuous | current − climatological_mean(region, month) |
| SST 7-day trend | MOSDAC time-series | Continuous | 7-day SST change |
| Chlorophyll (mg/m³) | OCM-3 / MODIS | Continuous | Surface chlorophyll |
| Chlorophyll anomaly | OceanColor 20yr climatology | Continuous | Deviation from 20yr baseline |
| Chlorophyll gradient | Spatial gradient computation | Continuous | High gradient → convergence fronts |
| Upwelling index | Derived from wind + coast angle | Continuous | Positive = coastal upwelling |
| Wind speed (m/s) | SCATSAT / INCOIS | Continuous | |
| Wind direction (deg) | SCATSAT / INCOIS | Continuous | |
| Ocean current speed (knots) | INCOIS / Copernicus | Continuous | |
| Current direction (deg) | INCOIS / Copernicus | Continuous | |
| Significant wave height (m) | INCOIS | Continuous | |
| Wave period (s) | INCOIS | Continuous | |
| Tide height (m) | INCOIS | Continuous | |
| Sea level anomaly (m) | SARAL / Copernicus | Continuous | |
| Mixed layer depth (m) | INCOIS | Continuous | Shallow MLD = higher surface productivity |
| D20 (m) | INCOIS | Continuous | 20°C isotherm depth |
| Seabed depth (m) | GEBCO | Continuous | Shelf vs open ocean |
| Season (1–4) | Derived | Categorical | SW monsoon, NE monsoon, etc. |
| Month (1–12) | Derived | Categorical | One-hot encoded |
| Historical fishing effort | GFW | Continuous | kW-hours/km² |
| Historical PFZ frequency | INCOIS PFZ archive | Continuous | How often PFZ issued here in this month, last 5yr |
| Distance to coast (km) | Derived | Continuous | |
| Distance to upwelling centre | Derived | Continuous | |
| Inside MPA (0/1) | Protected Planet | Binary | |
| Cyclone distance (km) | IMD | Continuous | |
| Chlorophyll 14-day anomaly | OceanColor | Continuous | Longer-term trend |

**Hyperparameters (initial):**
```python
XGBClassifier(
    n_estimators=500,
    max_depth=6,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    min_child_weight=5,
    reg_alpha=0.1,
    reg_lambda=1.0,
    eval_metric='auc'
)
```

**Validation:** Temporal split — train 2003–2022, validate 2023–2024, test 2025  
**Target metrics:** AUC-ROC > 0.82, Precision@0.5 > 0.75, Recall@0.5 > 0.70  
**Explainability:** SHAP values computed per prediction for evidence graph

---

### 11.2 Ocean State Anomaly Detector

**Model type:** Isolation Forest (unsupervised, scikit-learn)  
**Training data:** 10+ years of H3-cell state vectors from ERA5 + OISST + OceanColor  
**Input features:** SST, chlorophyll, wave height, current speed, wind speed, sea level anomaly, MLD (7 features)  
**Output:** Anomaly score + Z-score per variable

**Z-score baseline:**
```python
def compute_z_score_anomaly(current_val, region_id, month, variable):
    baseline = load_climatological_stats(region_id, month, variable)
    return (current_val - baseline.mean) / baseline.std
```
Anomaly flagged if |Z-score| > 2.5 σ or Isolation Forest score < threshold.

---

### 11.3 Maritime Route Risk Optimizer

**Algorithm:** A* graph search on H3 resolution-7 hexagonal grid (~5 km edge length)  
**Graph:** All Indian Ocean H3 cells within Indian EEZ + 200 km buffer

**Edge cost function:**
```python
def edge_cost(h3_cell: str, vessel: VesselProfile) -> float:
    state = get_h3_state(h3_cell)
    wave_risk    = sigmoid_risk(state.wave_height, vessel.max_safe_wave)
    wind_risk    = sigmoid_risk(state.wind_speed, vessel.wind_threshold)
    cyclone_risk = cyclone_proximity_risk(state.cyclone_distance, state.cyclone_category)
    lightning_risk = state.lightning_probability
    boundary_risk = boundary_proximity_risk(h3_cell, vessel.flag_state)
    depth_risk   = depth_safety_risk(state.bathymetry, vessel.draft)
    fuel_cost    = distance_km(h3_cell) / vessel.fuel_efficiency
    weights = VESSEL_WEIGHTS[vessel.vessel_class]
    return (weights.w_wave * wave_risk + weights.w_wind * wind_risk +
            weights.w_cyclone * cyclone_risk + weights.w_lightning * lightning_risk +
            weights.w_boundary * boundary_risk + weights.w_depth * depth_risk +
            weights.w_fuel * fuel_cost)
```

**Key property:** Returns safest route, not shortest. Shows rejected shorter route with risk tooltip.

---

### 11.4 Drift / Model Degradation Monitor

**Algorithm:** Kolmogorov-Smirnov two-sample test on rolling 30-day window vs training distribution  
**Monitored:** SST, chlorophyll, wave height (top features)  
**Action:** If KS statistic > 0.15 (p < 0.05), set `model_confidence_reduction = True` — flagged in Uncertainty Engine

---

## 12. DATABASE SCHEMA (COMPLETE)

```sql
-- USERS AND VESSEL PROFILES
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    language_code   CHAR(2) NOT NULL DEFAULT 'en',
    home_port_name  TEXT,
    home_port_lat   DOUBLE PRECISION,
    home_port_lon   DOUBLE PRECISION,
    alert_enabled   BOOLEAN DEFAULT TRUE
);

CREATE TABLE vessel_profiles (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID REFERENCES users(id) ON DELETE CASCADE,
    vessel_name             TEXT,
    vessel_class            TEXT NOT NULL,   -- 'small_fishing' | 'medium_trawler' | 'large_vessel'
    length_m                DOUBLE PRECISION,
    engine_hp               INTEGER,
    max_safe_wave_m         DOUBLE PRECISION,
    wind_threshold_ms       DOUBLE PRECISION,
    operational_range_km    DOUBLE PRECISION,
    draft_m                 DOUBLE PRECISION,
    fuel_efficiency         DOUBLE PRECISION,   -- km per litre
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- H3 MARINE STATE GRID (TimescaleDB hypertable)
CREATE TABLE h3_marine_states (
    cell_id                 TEXT NOT NULL,      -- H3 cell ID (resolution 7)
    timestamp               TIMESTAMPTZ NOT NULL,
    sst_c                   DOUBLE PRECISION,
    sst_anomaly_c           DOUBLE PRECISION,
    chlorophyll_mg_m3       DOUBLE PRECISION,
    chlorophyll_anomaly     DOUBLE PRECISION,
    wave_height_m           DOUBLE PRECISION,
    wave_period_s           DOUBLE PRECISION,
    swell_height_m          DOUBLE PRECISION,
    wind_speed_ms           DOUBLE PRECISION,
    wind_direction_deg      DOUBLE PRECISION,
    current_u_ms            DOUBLE PRECISION,
    current_v_ms            DOUBLE PRECISION,
    tide_height_m           DOUBLE PRECISION,
    sea_level_anomaly_m     DOUBLE PRECISION,
    mixed_layer_depth_m     DOUBLE PRECISION,
    cyclone_distance_km     DOUBLE PRECISION,
    lightning_probability   DOUBLE PRECISION,
    pfz_score               DOUBLE PRECISION,
    fishing_suitability     DOUBLE PRECISION,
    fishing_effort          DOUBLE PRECISION,
    bathymetry_m            DOUBLE PRECISION,
    inside_mpa              BOOLEAN,
    inside_restricted       BOOLEAN,
    inside_eez              BOOLEAN,
    data_freshness          JSONB,              -- {variable: timestamp}
    sources_used            TEXT[],
    PRIMARY KEY (cell_id, timestamp)
);
SELECT create_hypertable('h3_marine_states', 'timestamp');

-- PFZ ADVISORY ARCHIVE
CREATE TABLE pfz_advisories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issued_at       TIMESTAMPTZ NOT NULL,
    valid_from      TIMESTAMPTZ NOT NULL,
    valid_to        TIMESTAMPTZ NOT NULL,
    source          TEXT NOT NULL,        -- 'MOSDAC' | 'INCOIS'
    region          TEXT,
    zone_geojson    JSONB NOT NULL,
    confidence_tier TEXT,                 -- 'HIGH' | 'MEDIUM' | 'LOW'
    sst_input_c     DOUBLE PRECISION,
    chl_input       DOUBLE PRECISION,
    notes           TEXT
);

-- CONVERSATION SESSIONS
CREATE TABLE sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at        TIMESTAMPTZ,
    language_code   CHAR(2),
    turn_count      INTEGER DEFAULT 0,
    vessel_id       UUID REFERENCES vessel_profiles(id)
);

-- CONVERSATION TURNS
CREATE TABLE conversation_turns (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID REFERENCES sessions(id) ON DELETE CASCADE,
    turn_number     INTEGER NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    role            TEXT NOT NULL,        -- 'user' | 'assistant'
    content_text    TEXT NOT NULL,
    language_code   CHAR(2),
    intent          TEXT,
    agents_used     TEXT[],
    tool_calls      JSONB,                -- [{tool, args, result, latency_ms}]
    evidence        JSONB,
    risk_score      DOUBLE PRECISION,
    confidence      DOUBLE PRECISION,
    uncertainty_flags TEXT[],
    query_lat       DOUBLE PRECISION,
    query_lon       DOUBLE PRECISION
);

-- AGENT OUTPUT CACHE
CREATE TABLE agent_output_cache (
    cache_key       TEXT PRIMARY KEY,
    agent_name      TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL,
    output_json     JSONB NOT NULL,
    source_apis     TEXT[],
    freshness_score DOUBLE PRECISION
);

-- ALERT SUBSCRIPTIONS
CREATE TABLE alert_subscriptions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID REFERENCES users(id) ON DELETE CASCADE,
    vessel_id               UUID REFERENCES vessel_profiles(id),
    trip_departure          TIMESTAMPTZ,
    trip_destination_lat    DOUBLE PRECISION,
    trip_destination_lon    DOUBLE PRECISION,
    trip_zone_h3            TEXT,
    risk_threshold          DOUBLE PRECISION DEFAULT 60.0,
    active                  BOOLEAN DEFAULT TRUE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ALERT NOTIFICATIONS LOG
CREATE TABLE alert_notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID REFERENCES alert_subscriptions(id),
    sent_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    alert_type      TEXT,                 -- 'cyclone' | 'high_wave' | 'lightning' | 'risk_threshold'
    severity        TEXT,                 -- 'GREEN' | 'AMBER' | 'RED' | 'CRITICAL'
    message_text    TEXT,
    message_lang    CHAR(2),
    delivered       BOOLEAN DEFAULT FALSE
);

-- GEOSPATIAL BOUNDARIES (PostGIS)
CREATE TABLE eez_boundaries (
    id              SERIAL PRIMARY KEY,
    territory1      TEXT,
    iso_ter1        CHAR(3),
    sovereign1      TEXT,
    geom            GEOMETRY(MultiPolygon, 4326),
    area_km2        DOUBLE PRECISION
);
CREATE INDEX idx_eez_geom ON eez_boundaries USING GIST(geom);

CREATE TABLE marine_protected_areas (
    id              SERIAL PRIMARY KEY,
    wdpa_id         INTEGER UNIQUE,
    name            TEXT,
    desig_type      TEXT,
    iucn_cat        TEXT,
    status          TEXT,
    geom            GEOMETRY(MultiPolygon, 4326),
    area_km2        DOUBLE PRECISION
);
CREATE INDEX idx_mpa_geom ON marine_protected_areas USING GIST(geom);

CREATE TABLE bathymetry_h3 (
    h3_cell         TEXT PRIMARY KEY,
    depth_m         DOUBLE PRECISION,
    resolution      INTEGER DEFAULT 7
);

-- VECTOR STORE FOR HISTORICAL CONDITION RETRIEVAL
CREATE TABLE marine_condition_embeddings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    h3_cell         TEXT NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    feature_vector  vector(27),           -- 27-dim feature vector (matches ML feature table)
    pfz_label       BOOLEAN,
    metadata        JSONB
);
CREATE INDEX idx_marine_embeddings
    ON marine_condition_embeddings USING hnsw (feature_vector vector_cosine_ops);

-- DATA INGESTION JOB LOGS
CREATE TABLE ingestion_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source          TEXT NOT NULL,
    job_name        TEXT NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL,
    completed_at    TIMESTAMPTZ,
    status          TEXT,                 -- 'running' | 'success' | 'failed' | 'partial'
    records_fetched INTEGER,
    records_written INTEGER,
    error_message   TEXT,
    metadata        JSONB
);

-- ML MODEL REGISTRY
CREATE TABLE ml_models (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name      TEXT NOT NULL,
    version         TEXT NOT NULL,
    trained_at      TIMESTAMPTZ NOT NULL,
    training_auc    DOUBLE PRECISION,
    validation_auc  DOUBLE PRECISION,
    test_auc        DOUBLE PRECISION,
    feature_list    TEXT[],
    artifact_path   TEXT,                 -- MinIO path to serialised model
    active          BOOLEAN DEFAULT FALSE,
    notes           TEXT
);
```

---

## 13. STORAGE ARCHITECTURE

### 13.1 Tiered storage model

```
                          RAW DATA ARCHIVE
                          MinIO (S3-compatible)
              ┌─────────────┬──────────────┬──────────────┐
              ↓             ↓              ↓              ↓
         NetCDF files   GeoTIFF files   Zarr stores   CSV/Parquet
         (INCOIS OSF,   (MOSDAC SST,    (ERA5, OISST, (GFW effort,
          Copernicus,    OCM-3 chl,      WOA23)         Argo CSV,
          Argo profiles) GEBCO bath.)                   PFZ archive)

                          PROCESSING LAYER
                     (Airflow DAGs, xarray, rasterio,
                      GeoPandas, H3 indexing, QC)
                              │
                   ┌──────────┼──────────┐
                   ↓          ↓          ↓
              FEATURE     VECTOR      GEO STORE
               STORE       STORE
           TimescaleDB   pgvector    PostGIS
           (H3 marine    (27-dim     (EEZ, MPA,
            state time-   embeddings  boundaries,
            series)       per cell)   routes, ports)

                          REDIS CACHE
                   (Live API results TTL 6h,
                    Session state TTL 24h,
                    Agent output dedup cache)

                          METADATA & LOGS
                          PostgreSQL standard tables
                          (users, sessions, alerts,
                           ingestion logs, ML registry)
```

### 13.2 H3 grid configuration

| Resolution | Cell edge | Use |
|---|---|---|
| 5 | ~86 km | National risk dashboard — coarse overview |
| 7 | ~5 km | Primary operational grid — marine state, route planning |
| 9 | ~0.5 km | Fine grid — nearshore and port approach computations |

### 13.3 H3 cell state vector (JSON schema)

```json
{
  "cell_id": "8928308280fffff",
  "timestamp": "2026-08-25T06:00:00Z",
  "sst_c": 28.4,
  "sst_anomaly_c": 0.9,
  "chlorophyll_mg_m3": 0.92,
  "chlorophyll_anomaly": 0.22,
  "wave_height_m": 1.3,
  "wave_period_s": 8.2,
  "swell_height_m": 0.8,
  "wind_speed_ms": 6.2,
  "wind_direction_deg": 238,
  "current_u_ms": 0.21,
  "current_v_ms": -0.11,
  "tide_height_m": 0.74,
  "sea_level_anomaly_m": 0.04,
  "mixed_layer_depth_m": 42,
  "cyclone_distance_km": 420,
  "lightning_probability": 0.08,
  "pfz_score": 0.84,
  "fishing_suitability_score": 79,
  "fishing_effort_kwh_km2": 0.63,
  "bathymetry_m": 84,
  "inside_mpa": false,
  "inside_restricted": false,
  "inside_eez": true,
  "data_freshness": {
    "sst": "2026-08-25T04:00:00Z",
    "chlorophyll": "2026-08-24T10:00:00Z",
    "wave": "2026-08-25T06:00:00Z"
  }
}
```

### 13.4 Data retention policy

| Data type | Retention | Location |
|---|---|---|
| Live H3 marine state (res-7) | 90 days TimescaleDB; compress to MinIO after | TimescaleDB → MinIO Zarr |
| PFZ advisories | Indefinite (training data) | PostgreSQL + MinIO |
| Conversation turns | 30 days | PostgreSQL |
| Agent output cache | TTL per variable (see Section 7.2) | Redis |
| Raw NetCDF archives | 2 years rolling | MinIO |
| ML model artifacts | All versions retained | MinIO + MLflow |
| Ingestion logs | 6 months | PostgreSQL |

---

## 14. API SPECIFICATIONS

### 14.1a As-built API surface *(built — this is what exists today)*

No `/api/v1` prefix yet; routes are mounted at the root. Every `/marine/*`
endpoint accepts the same four vessel parameters, because the Stage 1 hard
constraints are vessel-relative — a 1.8 m wave vetoes an 8 m open boat and
does not veto a trawler, and depth is checked against draft.

```
GET  /health
       -> { status, env }

POST /chat
       Body: { message, session_id?, client_lat?, client_lon? }
       -> { answer, trace[], data{}, evidence{EvidenceReceipt}, decision_id, session_id }
       Timeout 115s. Omit session_id on the first message; reuse the
       returned one for follow-ups so location context carries over.

GET  /marine/state?lat&lon[&vessel_*]
       -> FusedMarineState: weather, ocean, geo, risk, validation, confidence_note
       Full multi-source fusion. Per-agent timeout 25s.

GET  /marine/quick-check?lat&lon[&vessel_*]
       -> QuickCheckResult: risk_score, risk_level, vetoed, reasons[], explanation[]
       Fast path (Open-Meteo + MPA + bathymetry). Built to be polled every
       ~10-15s from a moving vessel. SAME check_hard_constraints veto logic
       as /state — faster, not less safe. No decision-log write.

GET  /marine/safest-route?lat&lon&range_km[&vessel_*]     -> RouteRecommendation
GET  /marine/optimize-route?lat&lon&range_km[&vessel_*]   -> OptimizedRoute (A*)
GET  /marine/simulate/time-shift?lat&lon&hours_later[&vessel_*]        -> SimulationResult
GET  /marine/simulate/wave-perturbation?lat&lon&wave_multiplier[&...]  -> SimulationResult

vessel_* = vessel_length_m, vessel_max_safe_wave_m,
           vessel_wind_threshold_ms, vessel_operational_range_km
```

**Rate limit:** 60 requests/minute per client IP, in-memory (`slowapi`).
Shared across everything a client does — the live safety watch's poll
interval is chosen against this budget, not independently of it.

**Not yet built:** `/sessions/*`, `/users/*`, `/vessels/*`, `/alerts/*`,
`/map/*`, and the WebSocket channel. Vessel profile currently travels as
query parameters rather than a stored `vessel_id`.

### 14.1 REST API endpoints — target design (Base URL: /api/v1)

```
POST /chat
  Body: { session_id, message, language, lat, lon, vessel_id }
  Returns: { response_text, response_audio_url, evidence, risk_score,
             confidence, uncertainty_flags, zones, route, map_data }

GET /sessions/{session_id}/history
  Returns: list of conversation turns with evidence and tool calls

POST /sessions
  Body: { user_id, vessel_id, language }
  Returns: { session_id, created_at }

GET /marine/state?lat={}&lon={}&resolution={7}
  Returns: current H3 cell state for queried location

GET /marine/pfz?lat={}&lon={}&date={}
  Returns: PFZ advisory GeoJSON + metadata + confidence tier

GET /marine/risk?lat={}&lon={}&vessel_id={}&departure_time={}
  Returns: risk score, tier, breakdown, recommended zones, departure window

GET /marine/route?start_lat={}&start_lon={}&end_lat={}&end_lon={}&vessel_id={}
  Returns: safe route GeoJSON, risk profile, total distance, ETA, rejected route

GET /marine/anomaly?lat={}&lon={}&variable={sst|chl|wave}
  Returns: anomaly score, Z-score, duration, historical trend

GET /marine/simulation?base_query_id={}&overrides={}
  Returns: counterfactual marine state + risk score + recommendation delta

POST /alerts/subscribe
  Body: { user_id, vessel_id, departure_time, destination_lat, destination_lon }
  Returns: { subscription_id }

DELETE /alerts/subscribe/{subscription_id}

GET /alerts/history?user_id={}&limit={50}

WebSocket /ws/alerts/{user_id}
  Server pushes: { alert_type, severity, message, timestamp, zone_geojson }

POST /users
GET /users/{user_id}
POST /vessels
GET /vessels/{vessel_id}
PATCH /vessels/{vessel_id}

GET /map/h3grid?bbox={}&resolution={7}&variable={risk|pfz|chl|sst}
  Returns: H3 cell GeoJSON FeatureCollection with value per cell

GET /map/boundaries?types={eez,mpa,territorial}
GET /map/cyclone/active
GET /map/pfz/overlay?date={}
```

### 14.2 WebSocket protocol

```json
// Client to Server: subscribe
{ "type": "subscribe", "user_id": "uuid", "subscription_id": "uuid" }

// Server to Client: alert push
{
  "type": "alert",
  "alert_id": "uuid",
  "alert_type": "cyclone|high_wave|lightning|risk_threshold",
  "severity": "AMBER|RED|CRITICAL",
  "message": "Cyclone DANA is 380km from your planned zone. Risk increased to 74/100.",
  "message_odia": "ଚକ୍ରବାତ DANA ଆପଣଙ୍କ ଯୋଜିତ ଅଞ୍ଚଳଠୁ ୩୮୦ ଏ ଦୂରରେ।",
  "timestamp": "2026-08-25T04:30:00Z",
  "zone_geojson": {}
}

// Server to Client: data freshness
{
  "type": "data_update",
  "source": "INCOIS",
  "variables_updated": ["wave_height", "current"],
  "timestamp": "2026-08-25T06:00:00Z"
}
```

---

## 15. TOOL REGISTRY — COMPLETE LIVE API LAYER

All tools are deterministic Python functions. The LLM selects by name; Python executes. LLM never computes values.

```python
# WEATHER
get_current_weather(lat, lon)
get_weather_forecast(lat, lon, hours_ahead)
get_cyclone_list()
get_cyclone_track(cyclone_id)
get_cyclone_windfield(cyclone_id, lat, lon)
get_lightning_risk(lat, lon, time_window_hours)
get_rainfall_forecast(lat, lon)
get_weather_historical_baseline(lat, lon, month)

# OCEAN
get_wave_forecast(lat, lon, time)
get_wave_period(lat, lon, time)
get_swell_forecast(lat, lon, time)
get_ocean_current(lat, lon, depth_m, time)
get_ocean_sst(lat, lon)
get_ocean_sst_multi_source(lat, lon)
get_ocean_salinity(lat, lon)
get_sea_level_anomaly(lat, lon)
get_mixed_layer_depth(lat, lon)
get_tide(lat, lon, time)
get_d20(lat, lon)
get_argo_profile(lat, lon, radius_km)

# FISHING
get_pfz(lat, lon, date)
get_chlorophyll(lat, lon, date)
get_chlorophyll_anomaly(lat, lon, month)
get_sst_anomaly(lat, lon, month)
get_fishing_effort(lat, lon, date_range)
get_species_habitat(species, lat, lon, season)
get_bgc_argo_profile(lat, lon, radius_km)
predict_fishing_suitability(feature_vector)
get_historical_pfz_frequency(lat, lon, month)

# GEOSPATIAL
check_eez(lat, lon)
check_territorial_waters(lat, lon)
check_mpa(lat, lon)
check_restricted_zone(lat, lon)
get_bathymetry(lat, lon)
compute_route(start, end, vessel_draft, risk_weights)
analyze_route_risk(route_geojson, vessel_profile)
get_nearest_port(lat, lon)
get_boundary_distance(lat, lon)
get_geofencing_summary(lat, lon)

# SATELLITE DISCOVERY
search_satellite_archive(bbox, date_range, variable, sensor)
search_mosdac_archive(dataset_id, date_range, bbox)
get_latest_chlorophyll_granule(bbox)
get_latest_sst_granule(bbox)
get_cloud_cover_estimate(granule_id)
check_data_availability(lat, lon, variable, date)

# ANOMALY & HISTORICAL
get_historical_marine_state(lat, lon, date_range)
compute_sst_anomaly(lat, lon, current_sst, month)
compute_chlorophyll_anomaly(lat, lon, current_chl, month)
detect_marine_heatwave(lat, lon)
retrieve_similar_conditions(h3_cell_state, k=5)

# RISK & ROUTE
compute_risk_score(ocean, weather, geo, vessel_profile)
compute_route_risk(route, vessel_profile)
optimize_route(start, end, vessel_profile)

# SIMULATION
run_counterfactual(base_query_id, overrides)
```

---

## 16. FRONTEND / PWA DESIGN

### 16.1 Why PWA is the correct platform choice

| Requirement | PWA | Native app | Plain website |
|---|---|---|---|
| Fisherman uses Android at sea | Installable from Chrome, no Play Store | Requires Play Store publish | Cannot install |
| No internet at sea | Service workers + IndexedDB | Requires offline SDK | Breaks completely |
| ISRO judges demo on laptop | Same URL = full dashboard | Separate build needed | Works |
| Proactive alerts at sea | Web Push via service worker | Native push | Not possible offline |
| Build speed (hackathon) | One codebase, one deploy | Two builds | One build |

**Revised in v2.1: the answer is both, and the "Native app" column above was
too pessimistic in one row that turned out to be decisive.**

The PWA remains correct for judges, desk use and zero-install access, and is
still the primary demo surface. But "Proactive alerts at sea" is not actually
a tie. A backgrounded browser tab is throttled and eventually suspended by
Android; Web Push requires a live network connection to a push service, which
is precisely what a boat 20 km offshore does not have. The one feature that
matters most to the primary persona — *continuously re-check where I am and
warn me the moment it stops being safe* — cannot be delivered by a browser.

That capability needs an Android foreground service, so a native client was
built for the fisherman while the PWA continues to serve everyone else. Both
speak the same API and neither holds decision logic (§7.1a). The cost is one
extra build target; the benefit is that the product's central safety promise
is actually deliverable.

An APK also sidesteps a practical problem: installing a PWA from Chrome is a
multi-step flow that assumes a working data connection at install time. An
APK can be sideloaded from a phone that already has it, or shared
device-to-device in a harbour with no connectivity at all.

### 16.2 Dual-panel layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  🐋 ORCA Marine Intelligence     [🌐 ODIA ▼] [🔔 2] [👤 Ramesh]    │
├─────────────────────────────────────┬────────────────────────────────┤
│  MARINE MAP (MapLibre + deck.gl)    │  CONVERSATION PANEL            │
│                                     │                                │
│  H3 hex overlay                     │  🧑 ଆସନ୍ତାକାଲି ସକାଳ ୫ ଟାରେ  │
│  (green = safe+fish)                │     ମାଛ ଧରିବାକୁ ଯିବା ସୁରକ୍ଷ  │
│  (amber = caution)                  │                                │
│  (red = avoid)                      │  🐋 ଜୋନ B ପ୍ରସ୍ତାବ।          │
│                                     │  Risk: 28/100 ✓               │
│  [PFZ Zone B — highlighted]         │  ବିଶ୍ୱ: 89%                    │
│  [Safe route — green]               │                                │
│  [Rejected route — grey dashed]     │  ▼ EVIDENCE PANEL              │
│  [MPA boundary — purple]            │  SST: 28.4°C [INCOIS 47m ago] │
│                                     │  Wave: 1.1m [INCOIS 47m ago]  │
│  Layer controls:                    │  Chl: 0.86 [OCM-3 6h ago]     │
│  [☑ PFZ] [☑ Risk] [☑ Route]        │  Cyclone: 420km [IMD 23m ago] │
│  [☑ Boundaries] [☑ Cyclone]        │  MPA: Clear [Protected Planet] │
│  [☐ Chlorophyll] [☐ Currents]      │  Confidence: 89%               │
│                                     │                                │
│  PREDICTION CARDS:                  │  [What-if: Leave at ___AM?]   │
│  Wave 1.1m | Conf 91% | INCOIS      │  [🎙 Voice] [⌨ Text] [Send]  │
│  Wind 13km/h | Conf 94% | IMD       │                                │
└─────────────────────────────────────┴────────────────────────────────┘
```

### 16.3 Prediction card (per variable)

```
Wave Height Forecast
━━━━━━━━━━━━━━━━━━━━
Value:           1.48 m
Horizon:         18 hours
Confidence:      91%
Expected range:  1.25–1.79 m
Model agreement: ████████░ HIGH
Sources:         INCOIS OSF | Copernicus
Last obs:        47 min ago
Historical MAE:  0.17 m
Physics check:   ✓
━━━━━━━━━━━━━━━━━━━━
```

### 16.4 Evidence graph (visual factor tree)

```
        ZONE B RECOMMENDED
               │
    ┌──────────┼──────────┐
    ↓          ↓          ↓
POSITIVE   POSITIVE   POSITIVE
High Chl   Safe SST   Low wave
0.86mg/m³  28.4°C     1.1m
    │
NEGATIVE (ZONE A): Wave 2.8m > vessel limit 2.0m
NEGATIVE (ZONE C): Overlaps Chilika MPA (WDPA-ID 113289)
REJECTED ROUTE X:  Passes 1.7m shoal (vessel draft 0.8m)
```

### 16.5 Five user mode switcher

| Mode | Primary query | Map default | Evidence emphasis |
|---|---|---|---|
| 🎣 Fisherman | "Where should I fish? Is it safe?" | PFZ + Risk grid | Safety + fishing suitability |
| 🌊 Disaster Mgmt | "Which coast is at risk?" | National risk grid | Risk tier + cyclone track |
| ⚓ Coast Guard | "Vessels near boundary?" | EEZ + vessel AIS | Boundary proximity |
| 🔬 Researcher | "Why has productivity changed?" | Chlorophyll + SST anomaly | Anomaly timeline |
| 🚢 Port / Shipping | "Sea conditions on this route?" | Wave height + route risk | Route risk profile |

### 16.6 Offline mode — service worker strategy

```javascript
// INCOIS live data: NetworkFirst, 12h TTL
registerRoute(
  ({ url }) => url.pathname.startsWith('/api/marine/state'),
  new NetworkFirst({ cacheName: 'marine-state', networkTimeoutSeconds: 5,
                     plugins: [new ExpirationPlugin({ maxAgeSeconds: 43200 })] })
);
// PFZ: NetworkFirst, 24h TTL
registerRoute(
  ({ url }) => url.pathname.startsWith('/api/marine/pfz'),
  new NetworkFirst({ cacheName: 'pfz-data', networkTimeoutSeconds: 5,
                     plugins: [new ExpirationPlugin({ maxAgeSeconds: 86400 })] })
);
// Boundaries: CacheFirst, 7-day TTL
registerRoute(
  ({ url }) => url.pathname.startsWith('/api/map/boundaries'),
  new CacheFirst({ cacheName: 'boundaries-static',
                   plugins: [new ExpirationPlugin({ maxAgeSeconds: 604800 })] })
);
// Map tiles: CacheFirst, 5000 tile limit
registerRoute(
  ({ url }) => url.hostname.includes('tile'),
  new CacheFirst({ cacheName: 'map-tiles',
                   plugins: [new ExpirationPlugin({ maxEntries: 5000 })] })
);
```

---

### 16.7 Android app — screens and behaviour *(built — new in v2.1)*

Four tabs plus settings. Every number shown was computed by a backend agent;
the app renders, it does not calculate.

| Tab | Contents | Endpoint |
|---|---|---|
| **Ask** | Conversational query, session continuity for follow-ups, optional attached GPS position, planner trace, and an expandable **evidence receipt** under every answer | `POST /chat` |
| **Map** | OSM basemap, tap any point to run full fusion for it, route overlay with risk-coloured waypoints, centre-on-me | `GET /marine/state` |
| **Route** | Origin + radius, then either the fast candidate scan or the A* search, with the full "why not" list of vetoed alternatives | `/safest-route`, `/optimize-route` |
| **Watch** | Foreground-service safety monitor; takes the vessel's own position on a fixed interval and warns via OS notification when conditions turn unsafe | `GET /marine/quick-check` |
| **Settings** | Backend base URL with a live connection test, vessel profile, watch interval | `GET /health` |

**Rendering rules that follow from the architecture, not from taste:**

**1. A veto is not a high score.** `RiskLevel.Rejected` gets its own colour
and shows veto reasons — never a numeric badge. Rendering `REJECTED` on the
same 0–100 scale as a scored result would re-introduce exactly the defect the
two-stage pipeline was built to remove (§8.5).

**2. Missing data is shown as missing.** A null measurement renders as
"not available", never `0`. A fabricated `0.0 m` wave height reads as a calm
sea. `missing[]`, `data_gaps[]` and the SST single-year-baseline caveat are
all surfaced verbatim rather than summarised away.

**3. Failures name themselves.** The error card carries the exception type and
message, not a friendly paraphrase — the same discipline that §10.2 records
learning the hard way.

**4. The safety watch never reads the offline cache.** `/marine/state` falls
back to a last-known-good cached answer when the network is gone, always
labelled with its age. The watch deliberately does not: a twenty-minute-old
verdict presented as "you are safe right now" is worse than saying the check
failed.

**5. Two loops in the watch service, not one.** GPS updates write to a
volatile field; a separate timer reads it and calls the backend. Polling
straight from the location callback would tie request rate to GPS jitter and
can exhaust the 60 req/min budget while sitting still.

**Alert throttling:** once already unsafe, a fresh OS notification fires at
most once per 60 s while the condition persists — the in-app banner still
updates every tick. Alarm fatigue is a safety problem, not a UX nicety.

**Language:** English only in this build (§17 remains the target). Navigation
and repeated labels are in `strings.xml`, so a `values-hi/` copy translates
the chrome; longer explanatory paragraphs inside Map, Route, Watch and
Settings are still inline and need extracting first. Voice I/O via Android
`SpeechRecognizer` / `TextToSpeech` is the natural next addition and needs no
backend change.

---

## 17. MULTILINGUAL & VOICE STRATEGY

### 17.1 Languages supported

| Language | ISO | Coastal region | Priority |
|---|---|---|---|
| Hindi | hi | West coast, North India | P0 |
| Odia | or | Odisha — Puri, Paradip, Chilika | P0 |
| Bengali | bn | West Bengal — Digha, Fraserganj | P0 |
| Tamil | ta | Tamil Nadu — Rameswaram, Chennai | P0 |
| Telugu | te | Andhra Pradesh — Visakhapatnam | P1 |
| Kannada | kn | Karnataka — Mangalore, Karwar | P1 |
| Malayalam | ml | Kerala — Kochi, Trivandrum | P1 |
| Marathi | mr | Maharashtra — Ratnagiri, Mumbai | P2 |
| Gujarati | gu | Gujarat — Veraval, Jamnagar | P2 |
| English | en | Researchers, officers, urban | P0 |

### 17.2 Language processing pipeline

```
User speaks / types in regional language
              ↓
   INPUT CHANNEL
   Text: direct UTF-8
   Voice: Web Speech API (English) OR
          Google Cloud STT v2 (Indian languages)
              ↓
   LANGUAGE DETECTION
   langdetect (fast) + LLM verify (ambiguous)
              ↓
   INTENT EXTRACTION
   Gemini prompt in detected language → structured JSON
   (location, time, vessel, query type)
              ↓
   AGENT EXECUTION
   Language-agnostic Python + ML layer
   All data in SI units internally
              ↓
   RESPONSE GENERATION
   Gemini: respond in user's detected language
              ↓
   TTS (if voice mode)
   Google Cloud TTS WaveNet regional voice
```

### 17.3 Example end-to-end (Odia)

**Input (voice):** "ଆସନ୍ତାକାଲି ସକାଳ ୫ ଟାରେ ପୁରୀ ନିକଟ ମାଛ ଧରିବାକୁ ସୁରକ୍ଷିତ କି?"  
**Detected:** Odia (or), intent: safety + fishing, location: Puri, time: tomorrow 05:00  
**Agent output:** Risk=28, Zone B recommended, Wave=1.1m, No cyclone  
**Response (Odia TTS):** "ହଁ, ପୁରୀ ଠାରୁ ୨୩.୮ ଏ ଦୂରରେ ଜୋନ B ଉପଯୁକ୍ତ। ଢ଼େଉ ୧.୧ ମି। ଚକ୍ରବାତ ଆଶଙ୍କା ନାହିଁ। ବିଶ୍ୱ ୮୯%।"

---

## 18. OFFLINE / LOW-BANDWIDTH STRATEGY

### 18.1 Connectivity tiers

| Tier | Condition | ORCA behaviour |
|---|---|---|
| Full online | 4G+ | All agents live, all 15+ APIs queried, real-time map |
| Degraded | 2G / weak 4G | Cached INCOIS OSF (<12h), compressed tiles, simplified responses |
| Minimal | Very weak | Cached PFZ (<24h) + IMD cyclone bulletin + static boundaries + basic risk |
| Offline | No signal | Last-downloaded INCOIS OSF + PFZ + static boundaries + local rule-based risk engine |
| Recovery | Reconnected | Auto background sync; queued queries answered; missed alerts pushed |

### 18.2 Pre-cache policy (triggered 5 AM daily)

- INCOIS OSF for user's home port region (72-hour forecast)
- ISRO PFZ advisory for user's operational area
- IMD cyclone bulletin
- Compressed map tiles for operational range
- EEZ + MPA boundaries (if changed since last check)
- All stored in IndexedDB with freshness timestamps

### 18.3 Offline risk rule engine (no LLM required)

```python
def offline_risk_assessment(cached_state: CachedMarineState,
                             vessel: VesselProfile) -> OfflineRiskResult:
    risk, warnings = 0, []
    if cached_state.age_hours > 12:
        warnings.append(f"Data is {cached_state.age_hours:.0f}h old — use with caution")
    if cached_state.wave_height > vessel.max_safe_wave:
        risk += 40
        warnings.append(f"Wave {cached_state.wave_height}m exceeds vessel limit {vessel.max_safe_wave}m")
    if cached_state.cyclone_distance < 500:
        risk += 35
        warnings.append(f"Cyclone {cached_state.cyclone_name} within 500km")
    if cached_state.lightning_probability > 0.6:
        risk += 15
        warnings.append("High lightning probability")
    return OfflineRiskResult(risk_score=min(risk, 100), warnings=warnings,
                             data_age_hours=cached_state.age_hours, is_cached=True)
```

---

## 19. FUNCTIONAL REQUIREMENTS

### FR-C — Conversational Interface

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-C01 | Accept natural language queries in text | P0 | Any question → response returned |
| FR-C02 | Accept voice queries | P1 | WER < 10% for Odia, Tamil, Hindi |
| FR-C03 | Multi-turn conversation with memory | P0 | "That zone" in turn 3 resolves to zone named in turn 1 |
| FR-C04 | Respond in same language as user input | P0 | Odia in → Odia out; Tamil in → Tamil out |
| FR-C05 | Produce spoken audio responses (TTS) | P1 | Audio playable in < 3s on 4G |
| FR-C06 | Support all 10 Indian languages | P1 | Intent extraction correct in each language test set |
| FR-C07 | Maintain user context across sessions | P1 | Vessel profile and home port remembered next session |

### FR-A — Agent Architecture

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-A01 | Multi-agent orchestration (not monolithic LLM) | P0 | Execution trace shows distinct agents per query |
| FR-A02 | Parallel agent execution where independent | P1 | Weather and Fishing Agents execute simultaneously |
| FR-A03 | Per-agent 10s timeout with graceful degradation | P0 | Slow INCOIS API → partial result + flag, not crash |
| FR-A04 | LLM never computes numeric values | P0 | Code review: all values from tool outputs only |
| FR-A05 | Cycle detection — max 20 tool calls | P0 | System terminates with partial result, not infinite loop |

### FR-D — Data Integration

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-D01 | Ingest INCOIS OSF | P0 | Wave height for any Indian Ocean point within 6h of publication |
| FR-D02 | Ingest ISRO MOSDAC PFZ advisory | P0 | Daily PFZ polygon within 24h of MOSDAC publication |
| FR-D03 | Ingest IMD weather + cyclone + lightning | P0 | Cyclone alert reflects IMD bulletin within 30 minutes |
| FR-D04 | Integrate Copernicus Marine | P1 | Ocean current from Copernicus compared to INCOIS; disagreement flagged |
| FR-D05 | Integrate NOAA OISST for SST baseline | P1 | SST anomaly computed correctly per month/location |
| FR-D06 | Integrate GFW historical fishing effort | P2 | Fishing suitability model uses GFW; feature importance > 5% |
| FR-D07 | Integrate GEBCO bathymetry | P1 | Route avoids cells shallower than vessel draft |
| FR-D08 | Integrate Marine Regions EEZ boundaries | P0 | Geofencing correctly identifies Indian EEZ |
| FR-D09 | Integrate Protected Planet MPA boundaries | P0 | Correctly identifies Chilika, Gulf of Mannar MPAs |
| FR-D10 | Data freshness tracked per variable | P1 | Prediction card shows data age; stale data flagged |

### FR-R — Risk Engine

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-R01 | Risk score on 0–100 scale | P0 | Score for any lat/lon/time/vessel combination |
| FR-R02 | Vessel-aware risk | P0 | Same location → different risk for 8m vs 20m vessel |
| FR-R03 | GREEN / AMBER / RED / CRITICAL tiers | P0 | Correct tier for known past events (cyclone day = RED) |
| FR-R04 | Dominant risk factor identified | P1 | "Wave height is primary risk" when wave > threshold |
| FR-R05 | Multi-source disagreement reduces confidence | P1 | INCOIS vs Copernicus wave differ > 0.5m → confidence < 80% |

### FR-F — Fishing Intelligence

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-F01 | PFZ advisory retrieved and displayed | P0 | PFZ polygon rendered on map for today |
| FR-F02 | Chlorophyll concentration from satellite | P1 | OCM-3 or MODIS value for any queried point |
| FR-F03 | Fishing suitability ML model score | P1 | Score produced and cited in recommendation |
| FR-F04 | Multiple candidate zones ranked | P1 | ≥3 candidate zones returned within operational range |
| FR-F05 | Rejected zones shown with reasons | P1 | "Zone A rejected: wave 2.8m exceeds vessel limit" |

### FR-G — Geospatial & Routing

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-G01 | EEZ geofencing alert near boundary | P0 | Alert within 10km of EEZ boundary |
| FR-G02 | MPA geofencing alert | P0 | Alert when route/zone intersects MPA |
| FR-G03 | Safe maritime route computed | P1 | Route avoids high-risk cells and restricted zones |
| FR-G04 | Rejected shorter route displayed | P1 | Both routes visible; rejected route has risk tooltip |
| FR-G05 | Bathymetric safety check | P1 | Route avoids cells shallower than vessel draft |
| FR-G06 | Nearest safe port identified | P1 | Port name, distance, bearing for any lat/lon |

### FR-S — Simulation (Counterfactual)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-S01 | "What if different departure time?" reruns simulation | P1 | New risk + recommendation within 15s |
| FR-S02 | "What if cyclone moves closer?" reruns simulation | P2 | Risk recalculated with modified cyclone position |
| FR-S03 | "What if different vessel?" reruns simulation | P2 | Risk recalculated with modified vessel profile |
| FR-S04 | Simulation delta clearly shown | P1 | "Risk increased from 28 to 74" with reason |

### FR-AN — Anomaly & Historical

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-AN01 | SST anomaly vs 20-year OISST climatology | P1 | Z-score computed; flag if |Z| > 2.5 |
| FR-AN02 | Chlorophyll anomaly vs OceanColor climatology | P2 | Deviation from 20-year baseline computed |
| FR-AN03 | Marine heatwave detection | P2 | Detected for known 2023 Indian Ocean event in backtest |
| FR-AN04 | Historical productivity trend analysis | P2 | System explains decline with multi-year temporal evidence |

### FR-U — UI & Map

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-U01 | H3 hexagonal grid overlay on map | P0 | Coloured hex cells rendered for risk or PFZ score |
| FR-U02 | PFZ advisory overlay | P0 | PFZ polygon from MOSDAC GeoJSON on map |
| FR-U03 | Cyclone track rendered | P0 | Track + uncertainty cone visible |
| FR-U04 | Safe route rendered | P1 | Route polyline with risk-coloured segments |
| FR-U05 | Prediction card per variable | P1 | Wave, wind, SST each with confidence + data age |
| FR-U06 | Evidence graph rendered | P1 | Positive/negative factor tree on click |
| FR-U07 | Layer toggles | P1 | PFZ / risk / chlorophyll / boundaries toggleable |
| FR-U08 | 5-mode switcher | P2 | Mode changes map layers and query templates |

### FR-AL — Alerts & Proactive

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-AL01 | Proactive push alert for cyclone approaching planned zone | P1 | Push within 5 minutes of IMD cyclone update |
| FR-AL02 | Proactive push when risk crosses RED threshold | P1 | Alert before planned departure time |
| FR-AL03 | Alert delivered when app in background | P1 | Web Push shows in Android notification shade |

### FR-OF — Offline

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-OF01 | App installs as PWA on Android | P0 | Add-to-homescreen prompt; opens without browser chrome |
| FR-OF02 | Cached INCOIS OSF serves offline queries | P1 | Wave height answered offline using <12h cached data |
| FR-OF03 | Static boundaries always available offline | P0 | EEZ / MPA geofencing works offline |
| FR-OF04 | Offline banner with data age shown | P0 | "Offline — data from 6 hours ago" visible |
| FR-OF05 | Offline queries queued and answered on reconnection | P2 | Query answered within 60s of reconnecting |

### FR-H — Constraint Hierarchy *(new in v2.1, built)*

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-H01 | Hard constraints are evaluated before any scoring | P0 | Vetoed candidate returns `risk_level="REJECTED"` with `factor_breakdown={}` and is never scored |
| FR-H02 | A favourable score can never override a veto | P0 | Regression test: MPA-inside point returns REJECTED regardless of all other factors |
| FR-H03 | One shared veto implementation across all paths | P0 | `/state`, `/quick-check`, candidate scan and A* graph all call the same `check_hard_constraints` |
| FR-H04 | A veto is never rendered on the 0–100 scale | P0 | No numeric badge on a REJECTED result in any client |
| FR-H05 | Veto reasons are shown in plain language | P0 | Each reason names the constraint and the measured value that tripped it |

### FR-L — LLM Independence *(new in v2.1, built)*

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-L01 | System answers every query type with no LLM available | P0 | Verified end-to-end with `GROQ_API_KEY` removed |
| FR-L02 | Fallback engages on live failure, not just on missing config | P0 | Quota, network or malformed-JSON failure falls through automatically |
| FR-L03 | Fallback renderer cannot introduce new text | P0 | Template renderer only emits fields present in the evidence receipt |
| FR-L04 | The LLM never computes or estimates a physical value | P0 | Prompt and code review; all numbers originate in deterministic agents |

### FR-N — Native Android Client *(new in v2.1, built)*

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-N01 | Chat with evidence receipt and session continuity | P0 | Follow-up question resolves location from earlier in the session |
| FR-N02 | Tap any map point to run full fusion for it | P0 | Returns risk, weather, ocean and geo for the tapped coordinate |
| FR-N03 | Route planning with the "why not" list of vetoed alternatives | P1 | Rejected candidates shown with the constraint that vetoed each |
| FR-N04 | Live safety watch continues with the screen off | P0 | Foreground service polls own position and warns on transition to unsafe |
| FR-N05 | Repeat alerts throttled while a condition persists | P0 | At most one OS notification per 60s; in-app banner still updates each tick |
| FR-N06 | Backend URL configurable at runtime | P1 | Editable in Settings with a live `/health` test; no rebuild needed |
| FR-N07 | Vessel profile sent with every marine request | P0 | Configured profile is what was actually evaluated, not a server default |
| FR-N08 | Cached data labelled with its age; watch excluded | P0 | Offline banner states age; safety watch reports failure instead of serving stale |
| FR-N09 | Missing measurements never rendered as a number | P0 | Null renders "not available", never `0` |

### FR-P — Latency & Caching *(new in v2.1, built)*

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-P01 | A cold cache never blocks a request on a recomputable quantity | P0 | Uncached tide returns `status:"computing"` immediately; background task populates it |
| FR-P02 | Time-invariant quantities cached as a series, not a snapshot | P0 | Tide caches a 28h prediction; current value interpolated per request |
| FR-P03 | Per-source timeouts, never one wrapped around the whole gather | P0 | A slow source cannot discard fast successful results |
| FR-P04 | Bulk geospatial fetches verified before being saved | P0 | Nonzero-fraction, bounds and distinct-value gates; failures not written |
| FR-P05 | Concurrent verification bounded, not serialised | P1 | Top-3 candidates verified together; caller waits for slowest, not the sum |

---

## 20. NON-FUNCTIONAL REQUIREMENTS

| ID | Category | Requirement | Target | Notes |
|---|---|---|---|---|
| NFR-01 | Latency | End-to-end query response (online) | < 10s P95 | **Met (built).** Measured `/chat` 4.3s, `/marine/state` 2.5s cold / 0.4s warm — see §7.4 |
| NFR-02 | Latency | Simulation (counterfactual) response | < 15s | Partial re-run of affected agents only |
| NFR-03 | Latency | Map tile render (initial) | < 3s on 4G | Vector tiles + deck.gl WebGL |
| NFR-04 | Latency | Offline query response | < 2s | Local cached data, no network |
| NFR-05 | Throughput | Concurrent users | ≥ 50 (demo) | FastAPI async + Redis cache |
| NFR-06 | Availability | System uptime during evaluation | ≥ 99% | Docker + Nginx + health checks |
| NFR-07 | Explainability | Every recommendation cites all data sources | 100% | Enforced at LLM prompt level |
| NFR-08 | Explainability | Confidence score on every recommendation | 100% | Uncertainty Engine required |
| NFR-09 | Reliability | Agent failure degrades gracefully | Partial result, not crash | Per-agent try/except + timeout |
| NFR-10 | Reliability | LLM hallucination prevention | 0 fabricated values | LLM restricted to narrating pre-computed values only |
| NFR-11 | Accuracy | Fishing suitability model | AUC-ROC > 0.82 | Backtest on held-out 2025 PFZ archive |
| NFR-12 | Accuracy | Risk tier for cyclone days | 100% RED on known cyclone landfall dates | Backtest validation |
| NFR-13 | Security | No PII beyond vessel profile and home port | No sensitive personal data | Data minimisation |
| NFR-14 | Security | All API keys server-side only | 0 keys in frontend | Environment variables; Nginx proxy |
| NFR-15 | Security | HTTPS enforced | All endpoints HTTPS | Nginx + Let's Encrypt |
| NFR-16 | Privacy | Location sent only on explicit query | Not tracked passively | Frontend: location read on demand only |
| NFR-17 | Accessibility | Minimum font size on mobile | 16px minimum | Fishermen in bright sunlight |
| NFR-18 | Accessibility | High-contrast risk tier colours | WCAG AA | Red/amber/green distinguishable |
| NFR-19 | Offline | Cached data age always displayed | 100% when serving cached | "Data from X hours ago" label |
| NFR-20 | Multilingual | UI strings translated | 10 languages | i18next lazy-loaded bundles |
| NFR-21 | Performance | PWA Lighthouse score | ≥ 90 Performance, ≥ 90 PWA | Vite optimised build |
| NFR-22 | Performance | H3 grid rendering (10,000 cells) | 60fps on mid-range Android | deck.gl WebGL |
| NFR-23 | Maintainability | Test coverage backend | ≥ 70% | pytest; all agents unit-tested |
| NFR-24 | Maintainability | All env config in .env | No hardcoded config | 12-factor app |
| NFR-25 | Scalability | Horizontal scaling of API | Stateless FastAPI + Redis | docker-compose scale |
| NFR-26 | Freshness | Alert delivery delay from source | ≤ 5 minutes | Cyclone position → push notification |
| NFR-27 | Freshness | INCOIS OSF refresh | Every 6 hours | Celery scheduled task |
| NFR-28 | Freshness | MOSDAC PFZ refresh | Every 24 hours | Celery scheduled task |
| NFR-29 | Freshness | IMD cyclone bulletin refresh | Every 15 minutes during active cyclone | Celery beat conditional escalation |
| NFR-30 | Monitoring | System health visible in Grafana | Key metrics dashboarded | Prometheus scrape from FastAPI |
| NFR-31 | Reliability | System answers with the LLM unavailable | 100% of query types | **Met (built).** Rule-based planner, verified end-to-end with no API key — §8.0 |
| NFR-32 | Correctness | A legal/safety veto can never be outranked by a favourable score | 0 exceptions | **Met (built).** Two-stage pipeline, single shared `check_hard_constraints` — §8.5 |
| NFR-33 | Correctness | A vetoed result is never rendered on the 0–100 scale | 100% of surfaces | **Met (built).** Enforced in both clients — §16.7 |
| NFR-34 | Honesty | An unreported measurement is never rendered as a number | 100% | **Met (built).** Null → "not available", never `0` |
| NFR-35 | Honesty | Cached/stale data always labelled with its age | 100% | **Met (built).** Offline banner in the Android client; watch excluded by design |
| NFR-36 | Reliability | Live safety watch survives screen-off | Continuous while enabled | **Met (built).** Android foreground service — §16.7 |
| NFR-37 | Diagnosability | No exception swallowed without type + message | 0 bare handlers | **Met (built).** Standing rule after the 429 incident — §10.2 |
| NFR-38 | Data integrity | No bulk geospatial fetch accepted without value verification | 100% of tiles | **Met (built).** Three-gate check in `fetch_gebco_regions.py` — §9.2a |
| NFR-39 | Latency | Cold cache never blocks a request on a recomputable quantity | 0 blocking waits | **Met (built).** Background tide computation — §7.4 |
| NFR-40 | Memory | Backend peak RSS during a cold route query | < 2 GB (target) | **NOT met.** Measured ~7.2 GB; see §29 open risk R-08 |

---

## 21. SECURITY & PRIVACY

### 21.1 API key management
All third-party credentials stored as environment variables. Never committed to version control. Accessed via `os.environ`. Rotated every 90 days.

### 21.2 Rate limiting
```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@app.post("/chat")
@limiter.limit("30/minute")
async def chat(request: Request, ...): ...
```

### 21.3 Data minimisation
- No IP addresses logged beyond 24h
- Voice audio not stored after STT transcription (processed in memory only)
- Location accessed only on explicit user query; not tracked passively
- No behavioural analytics beyond query count and session duration

### 21.4 Third-party licence compliance

| Source | Licence | Compliance action |
|---|---|---|
| Protected Planet API | Non-commercial only | Used under research/educational exemption; disclosed in submission |
| GFW API | Research/non-commercial | AIS classifications presented with explicit GFW limitation disclaimer |
| Marine Regions | CC BY 4.0 | Attributed in UI data credits section |
| GEBCO 2026 | Open, all uses | No restriction |
| INCOIS / MOSDAC | Indian government open data | Attributed; MOSDAC registered account compliance |
| Copernicus Marine | Copernicus open licence | Attributed in UI |

---

## 22. EVALUATION & VALIDATION STRATEGY

### 22.1 Fishing Zone Model Backtest

**Setup:** Hold out INCOIS PFZ archive 2025. Feed historical feature table for each advisory date.  
**Metrics:** AUC-ROC, Precision@0.5, Recall@0.5, False negative rate (<5%)  
**Baseline:** "High chlorophyll = PFZ" heuristic for comparison

### 22.2 Risk Score Backtest

**Setup:** 10 known adverse marine events (cyclone landfalls, declared fishing bans) 2020–2025. Run Risk Engine 24h, 48h, 72h before each event.  
**Metric:** Did risk score correctly reach RED tier before the event?

### 22.3 Anomaly Detection Validation

**Setup:** Run SST anomaly detection over 2023 Indian Ocean marine heatwave period.  
**Metric:** Correctly flagged cells vs published affected area.

### 22.4 Route Safety Validation

**Setup:** Safe vs direct routes for 20 historical adverse-condition days.  
**Metric:** Safe route has statistically significantly lower mean risk score (Wilcoxon signed-rank, p < 0.05).

### 22.5 Multilingual Accuracy

**Setup:** 50 test queries per language (5 languages × 10 queries) verified by native speakers.  
**Metric:** Intent classification accuracy ≥ 90% per language.

### 22.6 Uncertainty Calibration

**Setup:** 200 predictions logged with confidence scores. Group by decile. Verify actual accuracy per decile.  
**Metric:** Expected Calibration Error < 0.10. Well-calibrated confidence is a significant differentiator.

---

## 23. TESTING STRATEGY

### 23.1 Unit tests (backend)

**As built: 43 tests, all passing, no network and no running server required.**
```bash
cd backend && python -m pytest tests/ -v
```
Coverage focuses on the parts where a silent regression would be dangerous
rather than merely annoying:
- **`test_risk_agent.py`** — the constraint hierarchy (§8.5). Regression-guards
  the original defect: that a favourable score can never rescue a vetoed
  candidate.
- **`test_rule_based_planner.py`** — the LLM-free path. It is the fallback the
  whole system's availability rests on, so it is tested on its own merits,
  not as "good enough as a backup". Any new hard-coded intent-parsing or
  answer-rendering rule added there needs a test here.
- **`test_circuit_breaker.py`** — per-source failure tracking and cooldown.
- **`test_bathymetry_adapter.py`** — depth/land resolution against a synthetic
  region tile.

**Android: 5 wire-contract tests** (`WireContractTest`) assert the hand-mirrored
Kotlin models against real backend response shapes — that absent measurements
stay `null` instead of defaulting to `0`, that a vetoed point parses as
`REJECTED` with an empty factor breakdown, and that an unknown risk level
degrades instead of throwing. These exist because the app's models are
hand-written from `schemas.py`: without them, a renamed server field fails as
a silently defaulted value on a safety screen.

Each agent and tool function independently tested with mocked API responses:

```python
@pytest.mark.asyncio
async def test_weather_agent_cyclone_detection():
    mock_imd_response = {...}   # cyclone active fixture
    with patch('orca.tools.weather.imd_client.get_cyclone_list',
               return_value=mock_imd_response):
        result = await WeatherAgent().run(lat=19.9, lon=86.0, time=...)
    assert result.cyclone_active == True
    assert result.risk_tier == "RED"
    assert result.cyclone_distance_km < 500
```

### 23.2 Integration tests

Full agent pipeline end-to-end with staging API keys:
- Puri fishing query (standard happy path)
- Offline mode (API mocked to fail; asserts cached response served)
- Multi-turn context (3-turn conversation with reference in turn 3)
- Simulation delta (counterfactual departure time change)

### 23.3 ML model tests

- Feature pipeline: input data → feature vector (deterministic, numeric correctness)
- Output range: all suitability scores in [0, 1]
- Monotonicity: higher chlorophyll → higher suitability (all else equal)
- Null input handling: missing features imputed correctly

### 23.4 Frontend tests

- Map renders H3 cells without blank tiles
- Evidence panel expands on click
- Language switcher updates UI strings and API language parameter
- PWA: Lighthouse CI asserts score ≥ 90
- Offline: Service worker mock; cached data served when network intercepted

### 23.5 Load testing (k6)

- 50 concurrent `/chat` requests; assert P95 latency < 10s
- Redis cache hit rate ≥ 60% on repeated location queries

---

## 24. DEPLOYMENT ARCHITECTURE

### 24.1 Docker Compose services

```yaml
services:
  nginx:
    image: nginx:1.26
    ports: ["80:80", "443:443"]
    volumes: ["./nginx.conf:/etc/nginx/conf.d/default.conf", "./certbot:/etc/letsencrypt"]

  api:
    build: ./backend
    environment:
      DATABASE_URL: postgresql://...
      REDIS_URL: redis://redis:6379
      GOOGLE_API_KEY: ${GOOGLE_API_KEY}
      INCOIS_ERDDAP_BASE: https://erddap.incois.gov.in/erddap
      MOSDAC_API_KEY: ${MOSDAC_API_KEY}
      GFW_API_KEY: ${GFW_API_KEY}
      COPERNICUS_USERNAME: ${COPERNICUS_USERNAME}
      COPERNICUS_PASSWORD: ${COPERNICUS_PASSWORD}
    deploy:
      replicas: 2

  celery_worker:
    build: ./backend
    command: celery -A orca.tasks worker --loglevel=info --concurrency=4

  celery_beat:
    build: ./backend
    command: celery -A orca.tasks beat --loglevel=info
    # Jobs: INCOIS OSF every 6h, PFZ every 24h, IMD cyclone every 15min

  postgres:
    image: postgis/postgis:16-3.4
    volumes: ["pgdata:/var/lib/postgresql/data"]

  redis:
    image: redis:7.2-alpine
    volumes: ["redisdata:/data"]

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    volumes: ["miniodata:/data"]

  prometheus:
    image: prom/prometheus:latest

  grafana:
    image: grafana/grafana:latest

volumes:
  pgdata:
  redisdata:
  miniodata:
```

### 24.2 Network architecture

```
Internet
    │
  Nginx (SSL, gzip, rate limit, proxy)
    ├── /              → Static PWA files (dist/)
    ├── /api/          → FastAPI (uvicorn, 2 replicas)
    ├── /ws/           → WebSocket (FastAPI)
    └── /minio/        → MinIO (internal only in prod)

Internal Docker network:
  FastAPI → PostgreSQL (PostGIS + TimescaleDB + pgvector)
  FastAPI → Redis
  FastAPI → MinIO
  Celery workers → PostgreSQL + Redis + MinIO + external APIs
```

### 24.3 CI/CD pipeline (GitHub Actions)

```yaml
on: [push, pull_request]
jobs:
  test:
    - checkout
    - setup Python 3.11 + uv
    - install dependencies
    - run pytest (backend unit + integration)
    - run Vitest (frontend components)
    - run ruff + ESLint
    - Lighthouse CI (PWA score ≥ 90)
  deploy:
    needs: test
    if: branch == main
    - build Docker images
    - push to registry
    - SSH deploy: docker-compose pull && docker-compose up -d
```

---

## 25. TEAM COMPOSITION & ROLES

| Role | Responsibilities | Required skills |
|---|---|---|
| **Lead / AI Architect** (Shadwal) | Agentic pipeline (LangGraph), RAG/retrieval layer, LLM integration, system design, PRD | LangGraph, FastAPI, Gemini API, Python |
| **Data Engineer** | Ingestion pipeline (Celery/Airflow), INCOIS/MOSDAC/IMD adapters, H3 indexing, PostGIS, MinIO | Python, xarray, GeoPandas, PostgreSQL |
| **ML Engineer** | XGBoost fishing model, anomaly detection, training pipeline, MLflow, feature engineering | scikit-learn, XGBoost, PyTorch basics |
| **Frontend / GIS** | React/TypeScript, MapLibre, deck.gl, H3-js, PWA service workers, Tailwind, i18n | React, TypeScript, MapLibre, deck.gl |
| **Backend / DevOps** | FastAPI endpoints, Docker, Nginx, Prometheus/Grafana, testing | FastAPI, Docker, PostgreSQL, Redis |
| **Domain / QA** | Marine domain knowledge, multilingual query testing, demo rehearsal, presentation | Marine awareness; any tech background |

Maximum team size per SIH rules: 6. All 6 roles map to 6 people.

---

## 26. KPIs & SUCCESS METRICS

### Technical KPIs

| Metric | Target | How measured |
|---|---|---|
| Fishing suitability model AUC-ROC | ≥ 0.82 | Held-out 2025 PFZ backtest |
| Risk score backtest recall (RED tier) | ≥ 90% | 10 known adverse events |
| Anomaly detection on 2023 MHW | Correctly flags affected cells | Comparison to published event |
| Query response time P95 (online) | < 10 seconds | k6 load test |
| PWA Lighthouse Performance | ≥ 90 | Lighthouse CI |
| PWA Lighthouse PWA score | ≥ 90 | Lighthouse CI |
| Offline query from cache | < 2 seconds | Integration test |
| Multilingual intent accuracy | ≥ 90% per language | Manual test 10q × 5 languages |
| Agent cycle-free execution | 100% queries complete | Execution trace logs |
| LLM hallucination rate | 0 fabricated values | Code review + output audit |

### Demo KPIs

| Metric | Target |
|---|---|
| Puri fishing query end-to-end | < 8 seconds |
| Simulation response | < 12 seconds |
| All map layers render (no blank tiles) | 100% |
| Odia voice query correct intent | Demonstrated live |
| Evidence panel citations complete | 100% |
| Offline mode from cache | Demonstrated live |

---

## 27. DEMO SCRIPT

### 27.1 Target demo — full-capability walkthrough

**Setup:** ORCA open on laptop browser. Same URL on phone (PWA installed). Language: Odia. Vessel: 8m boat, 40HP, max safe wave 2m, range 60km.

**Step 1 — Voice query (Odia):**
> "ଆସନ୍ତାକାଲି ସକାଳ ୫ ଟାରେ ପୁରୀ ଉପକୂଳ ଠାରୁ ୪୦ ଏ ମଧ୍ୟରେ ମାଛ ଧରିବାକୁ ଯିବା ସୁରକ୍ଷିତ?"

**Step 2 — Show intent decomposition:**
Language: Odia | Intent: fishing zone + safety | Location: Puri | Time: tomorrow 05:00 | Range: 40km  
Agents dispatching: Weather, Ocean, Fishing, Geo, Risk (parallel)

**Step 3 — Agents complete (execution trace):**
Weather Agent: 2.3s | Ocean: 3.1s | Fishing: 2.8s | Geo: 1.1s | Risk: 0.2s — Total: 4.7s (parallel)

**Step 4 — Map updates:**
H3 grid appears over Bay of Bengal. Green cells (Zone B, 23.8 km SE). Amber (Zone A). Red hatching (Zone C — MPA).

**Step 5 — Spoken recommendation (Odia TTS):**
"ଜୋନ B ପ୍ରସ୍ତାବ। ପୁରୀ ଠାରୁ ୨୩.୮ ଏ। ଢ଼େଉ ୧.୧ ମି। ଚକ୍ରବାତ ଆଶଙ୍କା ନୁହେ। ବିଶ୍ୱ ୮୯%।"

**Step 6 — Open evidence panel:**
```
Zone B — RECOMMENDED
  SST: 28.4°C ✓        [INCOIS, 47 min ago]
  Chlorophyll: 0.86 ✓  [OCM-3, 6h ago]
  Wave: 1.1m ✓         [INCOIS OSF, 47 min ago] — within 8m limit (2.0m)
  Wind: 13 km/h ✓      [IMD, 23 min ago]
  Cyclone: 420 km ✓    [IMD, 23 min ago]
  MPA: Clear ✓         [Protected Planet]
  EEZ: Inside Indian EEZ ✓

Zone A — REJECTED: Wave 2.8m > vessel limit 2.0m
Zone C — REJECTED: Overlaps Chilika Wildlife Sanctuary (WDPA-ID 113289)
Confidence: 89% | Data freshness: chlorophyll 6h old (cloud-free pass)
```

**Step 7 — Route on map:**
Green route (43km, safe). Grey dashed (38km, shorter, rejected). Hover: "Rejected — 2.4m wave by 9 AM."

**Step 8 — Judge: "What if I leave at 8 AM?"**
Simulation Agent reruns: 9.2s. Risk 28 → 41 (AMBER). "Wave rises to 1.8m by 10 AM. 5 AM departure preferred."

**Step 9 — Judge: "What if cyclone moves 100km closer?"**
Counterfactual: cyclone_distance override = 320km. 7.8s. Risk 28 → 74 (RED). Zone switches to Zone D (11km). Alert added.

**Step 10 — Judge: "Why has fishing productivity declined near Chilika?"**
Anomaly Detection Agent + Historical Reasoning. Evidence graph shows:
- SST anomaly +2.4°C above October baseline (NOAA OISST) — sustained 6 weeks
- Chlorophyll declined 40% below 10yr mean (NASA OceanColor)
- GFW fishing effort declined in the area (2024–2025)
Response: "Decline coincides with persistent +2.4°C SST anomaly suppressing chlorophyll by ~40%. Pattern consistent with Indian Ocean marine heatwave."

---

### 27.2 Odisha demo — verified points and scenarios *(built)*

Team ORCA is at KIIT, Bhubaneswar. Demoing on water the judges recognise is
worth more than demoing on water they don't, so these Odisha scenarios are
verified end-to-end against live sources and the tiles in §9.2a. **Every
result below was actually returned by the running system, not composed for
this document.**

| # | Scenario | Request | Result |
|---|---|---|---|
| A | Launch from Puri beach, standard 8 m boat | `lat=19.78 lon=85.83 range_km=40` | Safest zone **20 km E**, MODERATE **28/100** |
| B | **From Bhubaneswar, 12 m boat, 100 km range** | `lat=20.2961 lon=85.8245 range_km=100 vessel_length_m=12 vessel_operational_range_km=100` | Safest zone **50 km NE**, **LOW 10/100** ← best result |
| C | Launch from Paradip port, standard 8 m boat | `lat=20.26 lon=86.68 range_km=40` | Safest zone **20 km NE**, LOW **15/100**, *plus a mid-route grounding warning* |

All three return a ready-to-click Google Maps deep link for the destination.

**Scenario C is the strongest demo moment.** It does not just rate the
destination — it flags a hazard *along the route itself*: "50% along route:
water depth 0.0 m is less than the vessel's draft (0.6 m) plus a 1.0 m safety
margin — grounding risk." A recommendation that is safe at both ends and
dangerous in the middle is precisely the failure mode a fisherman cannot see
from shore, and precisely what a naive "score the destination" system misses.

**Bhubaneswar with a standard 8 m boat correctly returns nothing, and this is
worth demonstrating deliberately.** The city is ~60 km inland; the Stage 1
constraint is distance-from-nearest-port against the vessel's 40 km
operational range. The system refuses rather than inventing a reachable
zone — a good answer to "what does it do when the honest answer is no?"

**Useful contrast points:**
- Geocoding a city *name* ("Puri", "Visakhapatnam") resolves to the city
  centre, which is on land and correctly hard-vetoes. Use offshore
  coordinates for a non-vetoed result — and use the place name on purpose
  when demonstrating the land veto.
- Verified Andhra alternative: **17.65, 83.35** (~40–56 m depth, offshore
  Visakhapatnam).

**Before presenting:** run `python scripts/prewarm_demo.py` 10–15 minutes
ahead. It warms Redis with real (not fabricated) responses for all of the
above, including every point the candidate scans touch. Tide is the exception
to the usual "re-run it if there's a gap" advice — it caches a 12 h predicted
series, so one pass covers a full day of demos.

---

## 28. PHASED ROADMAP

### Phase 0 — Internal Round (now → September 20, 2026)

| Week | Tasks | Owner | Deliverable |
|---|---|---|---|
| Week 1 (Aug 25–31) | PostgreSQL + PostGIS setup, schema migration, INCOIS ERDDAP adapter, IMD adapter, Celery + Redis scheduled ingestion | Data Eng | DB running, INCOIS + IMD data flowing |
| Week 2 (Sep 1–7) | Weather Agent + Ocean Agent (deterministic), FastAPI /chat endpoint, React chat UI | AI Arch + Backend + Frontend | Working query → response via one endpoint |
| Week 3 (Sep 8–14) | Marine Regions EEZ + Protected Planet MPA → PostGIS, Geo Agent, Leaflet map + PFZ overlay, Risk Agent v1 | All | Map shows PFZ, EEZ, risk score returned |
| Week 4 (Sep 15–20) | Evidence panel UI, LangGraph orchestrator replaces hardwired prompt, Hindi + Odia language support, demo recording, PPT | All | Internal round submission complete |

#### Phase 0 status as of 27 August 2026 *(built)*

**10 of the 11 agents in the §8 roster exist and run.** Ahead of the original
Phase 0 plan: several Phase 1 and Phase 2 items landed early.

| Item | Planned phase | Status |
|---|---|---|
| Weather, Ocean, Geo, Risk agents | Phase 0 | ✅ Done |
| LangGraph orchestrator + `/chat` | Phase 0 | ✅ Done |
| React PWA: chat, map, evidence panel | Phase 0 | ✅ Done, production build |
| EEZ + MPA → PostGIS, geofencing | Phase 0 | ✅ Done |
| Satellite Discovery Agent | Phase 1 | ✅ Done |
| Route Agent (candidate scan) | Phase 2 | ✅ Done |
| **Route Optimizer — A* on H3 risk grid** | Phase 2 | ✅ Done (§8.12) |
| **Simulation Agent (counterfactual)** | Phase 2 | ✅ Done — 3 scenario types |
| **Anomaly Detection Agent** | Phase 2 | ✅ Done — single-year 2023 baseline, labelled as such |
| **Uncertainty / confidence scoring** | Phase 2 | ✅ Done — multi-source disagreement + freshness |
| **Validation / Critic Agent** | *unplanned* | ✅ Done (§8.11) |
| **LLM-free rule-based fallback** | *unplanned* | ✅ Done (§8.0) |
| **Native Android client** | *unplanned* | ✅ Builds clean; runtime unverified (§10.7) |
| **Live safety watch** | *unplanned* | ✅ Done — `/quick-check` + foreground service |
| GEBCO bathymetry | Phase 1 | ✅ Done — verified regional tiles (§9.2a) |
| Multilingual (Hindi + Odia) | Phase 0 | ⬜ Not started — English only |
| Voice I/O | Phase 3 | ⬜ Not started |
| **Fishing Agent** | Phase 1 | 🔒 **Blocked on MOSDAC** — see below |
| PWA offline / service worker | Phase 3 | ⬜ Not started (Android has a last-known-good cache) |
| Proactive alerts / WebSocket | Phase 3 | ⬜ Not started |

**The one hard blocker.** The Fishing Agent and the XGBoost suitability model
(§11.1) both depend on the **INCOIS PFZ advisory archive 2003–2025** — the
actual training labels. It is not a bulk public download; it is gated on
MOSDAC/INCOIS access, still pending. Nothing substitutes for it: every other
dataset in §9 is a *feature*, not a *label*.

Consequence, stated plainly because it affects what may be claimed to judges:
**the system currently ranks zones by safety only. It does not claim to find
"productive" fishing zones**, and the Route Agent's own documentation says so.
The ML pipeline distinguishes real labels from synthetic placeholder labels
loudly, and synthetic-label metrics are never to be reported as results.

Also pending, wired but inactive: **MOSDAC**, **IMD** and **Protected
Planet**. Their adapters return an honest `{"status": "unavailable"}` while
unconfigured — dropping a key into `.env` activates them with no other code
change, because the calling agents already have the fallback chain built.

### Phase 1 — Oct (Fishing + ML + Full Orchestration)

- Fishing Agent: MOSDAC PFZ, OCM-3 chlorophyll, NASA OceanColor
- Download INCOIS PFZ archive 2003–2025; train XGBoost suitability model; backtest
- Geo Agent complete: GEBCO bathymetry H3 lookup, Protected Planet MPA, nearest port
- LangGraph multi-agent full orchestration; multi-turn memory; pgvector historical store
- GFW fishing effort API integration

### Phase 2 — Nov (Simulation + Anomaly + Route + UX)

- Simulation Agent (counterfactual "what if" queries)
- Anomaly Detection Agent + historical reasoning (OISST baseline + Isolation Forest)
- Route Optimizer: A* on H3 risk grid; route risk colouring; rejected route display
- Uncertainty Engine: multi-source disagreement + data freshness → confidence score
- Evidence Graph (visual factor tree in UI)
- All 10 languages: Telugu, Kannada, Malayalam, Marathi, Gujarati

### Phase 3 — Late Nov → December (Polish + Demo Prep)

- PWA offline mode: service workers, IndexedDB caching, local risk rules engine
- Voice I/O: Google Cloud STT/TTS for Odia, Tamil, Hindi
- Prediction cards per variable
- Proactive alerts: alert subscription backend + Web Push + WebSocket
- 5-mode switcher (Fisherman / Disaster / Coast Guard / Researcher / Port)
- CesiumJS 3D globe (stretch)
- Full backtest report (Section 22) printed for judges
- Daily demo rehearsal for 2 weeks before finale

---

## 29. RISK ASSESSMENT & MITIGATIONS

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| MOSDAC API registration rejected or slow | Medium | High | Use NASA OceanColor + Copernicus as primary chlorophyll in interim |
| IMD API rate-limited | Medium | Medium | Open-Meteo Marine fallback; ERA5 for historical; Redis cache all responses |
| LLM hallucinating marine data | High (without prevention) | High | LLM never computes values — only narrates pre-computed numbers; mandatory citation in every prompt |
| GFW API access delayed | Medium | Low | Differentiator not core; system works without it with marginally lower suitability model accuracy |
| INCOIS ERDDAP rate limit | Low | Medium | Redis TTL cache; 6-hour refresh reduces live request volume |
| H3 spatial queries too slow | Low | Medium | H3-indexed PostGIS + GIST index; pre-computed H3 state table eliminates per-query joins |
| LangGraph deadlock | Low | Medium | Max 20 steps; per-agent 10s timeout; LangGraph built-in cycle detection |
| Team member unavailable before deadline | Medium | High | Modular architecture — each agent independent; Phase 0 achievable by 2–3 members |
| Demo API failure at grand finale | Medium | High | Pre-cache Puri scenario 48h before; fallback to 100% cached response |
| Multilingual STT accuracy (Odia) | Medium | Medium | Google Cloud STT v2 Odia support; extensive testing; fallback to text input |
| Scope creep toward rebuilding INCOIS | High | High | Section 31 (What We Are Not Building) explicitly prevents this |
| ML model overfits to training years | Medium | Medium | Temporal split validation; cross-year holdout; Isolation Forest robust to drift |

#### Open engineering risks identified 27 August 2026 *(built system)*

These are recorded because they are live, unresolved, and would otherwise be
discovered during a demo.

| ID | Risk | Likelihood | Impact | Status / mitigation |
|---|---|---|---|---|
| **R-08** | **Backend memory: ~7.2 GB peak RSS on a cold route query.** `copernicusmarine.open_dataset` materialises the chunk index of a *global* 1/12° hourly store regardless of how small the requested subset is; route verification opens physics+BGC for up to 3 candidates. | High | **High — killed the server process during a prewarm run** | Partially mitigated: datasets are now closed promptly (−1.2 GB) and concurrent opens are capped. Capping did **not** meaningfully bound peak (measured: cap 1 → 7331 MB / 50.8 s vs cap 2 → 7236 MB / 38.7 s; freed arenas are not returned to the OS). **Real fix, not yet done:** open each dataset once process-wide and subset the cached lazy object under a lock. Prewarming makes the cold path rare, which is why this has not blocked the demo. |
| **R-09** | **Native crash with no traceback.** The process vanished mid-request, nothing in stdout or stderr. Root cause: the HDF5 C library under netCDF4 is not thread-safe, and `network_executor` runs the pyTMD tide reader, Copernicus opens and erddapy decoding concurrently. Latent before v2.1 — the tide call used to be cancelled at 20 s and never got far enough to overlap. | High | **Critical — total loss of service** | A process-wide `netcdf_lock` serialising all off-loop netCDF/HDF5 reads is **implemented but NOT yet verified**. Bathymetry tiles are now eagerly loaded so depth lookups are pure numpy. **This must be confirmed under load before any demo.** |
| **R-10** | **INCOIS ERDDAP is dead weight.** Fails with an SSL certificate-verification error on every call (~0.6 s wasted, uncached), and its `dataset_id` is still an unverified placeholder. It also calls `griddap_initialize()` **on the event loop** with no timeout — as does the NOAA adapter. | Certain | Low–Medium | Wave height falls through to Open-Meteo Marine, so no data is lost — but the latency and the loop-blocking are pure waste. Fix: move initialisation into the executor with a timeout, add a Redis cache, and verify or disable the dataset id. |
| **R-11** | **`erddapy` is broken in the venv** — `cannot import name '_quote_string_constraints'`, which also breaks the argo/ERDDAP xarray backends at import. | Certain | Medium | Version mismatch; needs a pin. NOAA OISST currently succeeds from cache but its live path is suspect. |
| **R-12** | **Android client unverified at runtime.** It compiles clean with passing unit tests, but has never been installed on a device or emulator. | Certain | Medium | "Builds" ≠ "runs". Must be booted against the live backend and each tab screenshotted before it is shown to judges. |

---

## 30. INNOVATION HIGHLIGHTS

| # | Innovation | Why It Wins |
|---|---|---|
| 1 | Marine Digital Twin (H3 Grid) | All marine state as per-cell vector; agents reason spatially over the grid, not over raw API calls |
| 2 | Multi-source consensus + disagreement | INCOIS, Copernicus, HYCOM compared; disagreement surfaces as reduced confidence |
| 3 | Vessel-aware risk scoring | Same ocean state = different risk for different boats — context-aware intelligence |
| 4 | Counterfactual simulation ("what-if") | User changes departure/weather/vessel; system re-executes and returns delta — most memorable demo feature |
| 5 | Evidence graph | Every recommendation shows positive factors, rejected alternatives, data citations — auditable AI |
| 6 | Uncertainty engine | Multi-source std dev + data freshness → per-variable confidence; honest about what it doesn't know |
| 7 | Historical productivity reasoning | Multi-year SST + chlorophyll + GFW investigated to answer "why has fishing declined?" |
| 8 | Proactive AI | Monitors conditions for registered trips; pushes alerts before user asks |
| 9 | Offline mode at sea | Service workers cache 24h INCOIS OSF + PFZ; offline risk rules for zero-connectivity |
| 10 | Voice-first regional language | Odia/Tamil/Hindi fisherman speaks naturally, receives spoken response — actual end user design |
| **11** | **Constraint hierarchy: vetoes vs. ranking** *(built)* | A legal or survivability constraint **cannot be outvoted by a good score**. Most "AI risk scoring" collapses legality and preference onto one number; this system refuses to score a candidate it has already ruled out, and says so — §8.5 |
| **12** | **The LLM is optional, not a dependency** *(built)* | Remove the API key entirely and the system still answers, with a renderer that is *structurally* incapable of hallucinating because it only repeats fields from a receipt. The safety-critical path does not need a model to be reachable — §8.0 |
| **13** | **The evidence receipt is computed before the model sees it** *(built)* | Sources, factor lines, gaps, rejected alternatives and confidence are a deterministic object; the LLM only phrases it. Both clients render the same object, so the explanation cannot drift from the computation — §8.9 |
| **14** | **"We don't know" is a first-class output** *(built)* | `data_gaps`, `INSUFFICIENT_DATA`, `status: "unavailable"` and null-never-zero rendering. Unverifiable adapters return an honest gap rather than a plausible guess; the anomaly baseline carries its own single-year caveat everywhere it appears |
| **15** | **Route hazards, not just destination scores** *(built)* | Intermediate waypoints are scored too, so a route that is safe at both ends and dangerous in the middle is caught — the failure a fisherman cannot see from shore (§27.2, scenario C) |

---

## 31. WHAT WE ARE NOT BUILDING

- NOT replacing INCOIS, IMD, or MOSDAC — ORCA consumes their authoritative outputs; does not reproduce operational numerical models
- NOT an autonomous maneuver or vessel control system — all recommendations require human decision
- NOT training a large satellite vision model (that is PS-26167, not PS-26176)
- NOT building 47 marketing-named "AI agents" — ~10 functionally distinct agents with clear inputs, outputs, boundaries
- NOT connecting to every API — every source has a documented reason; others explicitly excluded
- NOT using LLMs to compute mathematical values — all arithmetic is deterministic Python or ML models
- NOT claiming causal relationships that are merely correlational — evidence graph shows correlation; causal language is qualified
- NOT presenting AIS-derived GFW classifications as ground truth — GFW limitation disclaimer applied throughout
- NOT hardcoding recommendations — all outputs are dynamic, data-driven, reproducible

---

## 32. WINNING PHILOSOPHY

> **You don't win SIH because you have more agents. You don't win because you use the biggest LLM. You don't win because you have the prettiest map.**

> You win if the judges believe: **"This system takes real Indian marine data, independently reasons over it, makes a useful decision for a fisherman who has no other option, knows when it is uncertain, explains why it made that decision, and could realistically be deployed by ISRO tomorrow."**

Every architectural decision in this PRD — from deterministic tool execution, to vessel-aware risk scoring, to offline mode, to Odia voice support, to multi-source disagreement detection — is made in service of that one standard.

**The architecture's innovation is not in replacing INCOIS or IMD. It is in building the intelligent orchestration and decision layer that can consume those authoritative models, compare them, quantify their uncertainty, add targeted ML predictions, validate them, and turn the resulting ensemble into explainable decisions for fishermen and maritime stakeholders.**

---

## 33. APPENDIX A — ADDITIONAL STACK RECOMMENDATIONS

### A.1 ERDDAP protocol layer (`erddapy`)
INCOIS, NOAA, and several global sources expose ERDDAP endpoints. Using `erddapy` Python client gives a unified interface — saves 1–2 weeks of per-source adapter work.
```python
from erddapy import ERDDAP
incois = ERDDAP(server="https://erddap.incois.gov.in/erddap")
incois.dataset_id = "incois_osf_wave"
incois.variables = ["wave_height", "wave_period"]
incois.constraints = {"latitude>=": 10, "latitude<=": 25, "longitude>=": 75,
                       "longitude<=": 95, "time>=": "2026-08-24"}
ds = incois.to_xarray()
```

### A.2 STAC / pystac-client
NASA and Copernicus are increasingly STAC-compliant. `pystac-client` for archive discovery alongside CMR gives cleaner code and standardised metadata across all STAC-compliant sources.

### A.3 Prefect over Airflow (internal round)
For Phase 0, Airflow adds setup overhead. Prefect (Python-native, lightweight, managed free tier) achieves same DAG scheduling with `pip install prefect`. Migrate to Airflow documentation for production.

### A.4 tipg for OGC API Features
For exposing boundary GeoJSON (EEZ, MPA) as OGC-compliant vector tiles to MapLibre frontend, `tipg` (FastAPI-based) is faster to deploy than a custom tile server and produces MVT tiles compatible with MapLibre GL JS.

### A.5 CesiumJS for 3D ocean visualisation (Phase 3 stretch)
Open-source 3D geospatial — renders H3 grid as 3D globe with animated current vectors and cyclone track. Extremely visually impressive at national-level demo.

### A.6 Open-Meteo Marine API
Free, no registration, hourly marine forecast:
`https://api.open-meteo.com/v1/marine?latitude=19.8&longitude=85.8&hourly=wave_height,wave_period`
Third independent wave source for disagreement detection at zero setup cost.

### A.7 h3-pg (PostGIS H3 extension)
Native H3 functions in PostgreSQL:
```sql
SELECT h3_lat_lng_to_cell(ST_Y(geom), ST_X(geom), 7) as h3_cell FROM marine_observations;
```
Eliminates Python-side H3 computation in the ingestion layer.

---

## 34. APPENDIX B — DATA SOURCE REGISTRATION REQUIREMENTS

| Source | Registration | Time to activate | Action |
|---|---|---|---|
| ISRO MOSDAC | Yes (free) | 1–2 business days | **Register immediately** |
| INCOIS ERDDAP | No (public) | Immediate | None |
| IMD API | Yes (free) | 1–3 days | **Register immediately** |
| Copernicus Marine | Yes (free) | Same day | **Register this week** |
| Copernicus CDS (ERA5) | Yes (free) | Same day | **Register this week** |
| NASA Earthdata (CMR/OceanColor) | Yes (free) | Same day | **Register this week** |
| NOAA OISST | No (public ERDDAP) | Immediate | None |
| Argo GDAC | No (public FTP/API) | Immediate | None |
| HYCOM | No (OPeNDAP public) | Immediate | None |
| Marine Regions | No (download) | Immediate | None |
| Protected Planet | Yes (research key) | 2–5 business days | **Register immediately** |
| Global Fishing Watch | Yes (research account) | 3–7 business days | **Register immediately** |
| GEBCO 2026 | No (download) | Immediate | None |
| Open-Meteo Marine | No | Immediate | None |
| GBIF | No (API, rate limits) | Immediate | None |

**Day 1 action:** Register for MOSDAC, IMD, Copernicus Marine, Copernicus CDS, NASA Earthdata, Protected Planet, GFW. All free. Some take 2–5 days to activate — start now.

---

## 35. APPENDIX C — GLOSSARY

| Term | Definition |
|---|---|
| AIS | Automatic Identification System — maritime vessel tracking transponder |
| BGC-Argo | Biogeochemical Argo floats — T/S plus dissolved oxygen, chlorophyll, nitrate |
| Chlorophyll-a | Photosynthetic pigment indicating biological productivity and fish food chain |
| CMR | Common Metadata Repository — NASA's programmatic archive search system |
| D20 | Depth of the 20°C isotherm — indicator of thermocline and oceanographic structure |
| deck.gl | Uber's WebGL-powered geospatial visualisation framework |
| EEZ | Exclusive Economic Zone — 200 nautical mile sovereign resource zone |
| ERDDAP | Environmental Research Division's Data Access Program — unified oceanographic data access |
| ERA5 | ECMWF Reanalysis v5 — global hourly atmospheric reanalysis from 1940 |
| GFW | Global Fishing Watch — historical fishing effort and vessel tracking data |
| GEBCO | General Bathymetric Chart of the Oceans — global 15-arc-second bathymetry |
| H3 | Uber's Hierarchical Hexagonal Geospatial Indexing System |
| HYCOM | Hybrid Coordinate Ocean Model — US Navy global ocean prediction |
| IMD | India Meteorological Department — India's national weather service |
| INCOIS | Indian National Centre for Ocean Information Services — India's ocean forecast service |
| LangGraph | Framework for stateful multi-agent LLM workflows as explicit state machines |
| MHW | Marine Heatwave — period of anomalously high SST relative to climatology |
| MLD | Mixed Layer Depth — depth of wind-mixed surface ocean layer |
| MOSDAC | Meteorological and Oceanographic Satellite Data Archival Centre (ISRO) |
| MPA | Marine Protected Area — legally protected ocean area |
| NCMRWF | National Centre for Medium Range Weather Forecasting |
| OISST | Optimum Interpolation SST — NOAA's daily global SST dataset |
| OSF | Ocean State Forecast — INCOIS operational 5–7 day ocean forecast |
| PFZ | Potential Fishing Zone — ISRO advisory combining SST, chlorophyll, currents |
| PostGIS | Spatial extension for PostgreSQL enabling geographic queries |
| PWA | Progressive Web App — web app installable on mobile with offline capability |
| SARAL | Satellite with ARgos and ALtiKa — ISRO-CNES ocean altimetry satellite |
| SCATSAT-1 | Scatterometer Satellite — ISRO ocean wind vectors |
| SLA | Sea Level Anomaly — deviation of sea surface height from mean |
| SST | Sea Surface Temperature — temperature of the ocean's surface layer |
| STAC | SpatioTemporal Asset Catalog — open standard for geospatial data |
| TimescaleDB | Time-series database extension for PostgreSQL |
| TFT | Temporal Fusion Transformer — multi-horizon probabilistic forecasting model |
| WDPA | World Database on Protected Areas |
| WOA | World Ocean Atlas — NOAA's climatological ocean atlas |
| XGBoost | eXtreme Gradient Boosting — high-performance gradient boosted tree library |

---

*End of Product Requirements Document*  
*ORCA — Agentic Marine Intelligence System*  
*Smart India Hackathon 2026 | SIH26176 | KIIT University, Bhubaneswar*  
*PRD Version 2.0 | August 2026*
