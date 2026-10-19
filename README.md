# JalJeev — Marine Decision Support System

JalJeev is an agentic marine decision-support system I built for Smart India Hackathon 2026 (Problem Statement SIH26176, issued by ISRO). The project was originally known under the working title "ORCA".

The goal of JalJeev is straightforward: transform complex, fragmented oceanographic, atmospheric, and satellite data into direct, explainable, and safety-critical decisions for small-craft fishermen, sailors, and coastal commercial operators. Instead of forcing seafarers to decode raw meteorology bulletins or land-focused weather apps, JalJeev evaluates conditions against the physical constraints of their specific vessel and answers questions like:

- "Is it safe to venture out near Kochi today?"
- "Where within a 20 km radius can I fish safely right now?"
- "Plan a passage from Kochi to Kakinada and show me where weather hazards, shallow water, or protected zones intersect my route."

Every recommendation comes with a verifiable evidence receipt detailing the data sources, physical measurements, and hard safety limits that shaped the verdict.

---

## My Design Principles

When I started building this system, I established several non-negotiable architectural rules to ensure that the system remains safe, reliable, and grounded in physics:

1. **The LLM never calculates physical numbers.**
   Wave heights, tidal shifts, vessel squat, collision distances, and risk indices are calculated strictly through deterministic Python algorithms and PostGIS spatial queries. I restrict the LLM (Groq / Llama 3) to two specific tasks: parsing natural language queries into structured search parameters, and formatting final responses from the evidence receipt.

2. **The LLM is strictly optional.**
   Safety-critical marine tools cannot fail when internet connectivity drops or API quotas run out. I wrote a dedicated rule-based engine (`backend/app/planner/rule_based.py`) with regex-based intent parsing and template-driven response generation. If the LLM provider fails, times out, or has no API key configured, the system falls back seamlessly to deterministic rules with zero downtime and zero hallucinations.

3. **Two-stage risk evaluation: hard constraints veto, soft constraints rank.**
   Earlier versions used an additive risk score where legal violations or catastrophic hazards only added points to a total, which sometimes allowed a vessel inside a restricted marine sanctuary to still receive a "Moderate" rating. I redesigned the risk pipeline into two distinct stages:
   - **Stage 1 (Hard Vetoes):** Hard limits (Marine Protected Area violations, water depth less than vessel draft plus squat and tide margins, land intersection, and wave heights exceeding the vessel capsize threshold) trigger an immediate `REJECTED` status.
   - **Stage 2 (Additive Scoring):** Only candidates surviving Stage 1 receive an additive risk score (0 to 100) based on wind, swell, currents, visibility, and thermal anomalies.

4. **Vessel-specific physical profiles.**
   A light chop that is harmless to a 200-meter cargo vessel can overturn an 8-meter wooden canoe. Similarly, low wind is ideal for an engine-driven trawler but leaves a pure sailing vessel stranded. JalJeev models 11 distinct vessel classes across three user categories:
   - **Fishermen:** Small unmotorized craft (8m), mechanized trawlers (18m).
   - **Sailors:** Cruising yachts (12m), motor-sailers, traditional dhows (20m). Evaluates point-of-sail angles, tacking penalties, and becalmed conditions.
   - **Commercial Operators:** Coastal cargo, bulk carriers, tankers, and container ships. Computes dynamic vessel squat via the Barrass formula and enforces under-keel clearance (UKC) against EOT20 tidal models.

5. **Honest degradation over synthetic certainty.**
   If an external data source is unreachable or still pending official authorization (such as IMD credentials), the system reports the source as `unavailable` and lists the gap in the evidence receipt. I never synthesize fake oceanographic numbers.

---

## System Architecture

The project consists of three main application layers and supporting data infrastructure:

```
+-----------------------------------------------------------------------+
|                            Client Interfaces                          |
|  - Web UI: React 19 + TypeScript + Vite + MapLibre GL                |
|  - Android App: Native Kotlin + Jetpack Compose + Foreground Watch    |
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------+
|                         FastAPI Core Backend                          |
|                                                                       |
|  +------------------------+             +--------------------------+  |
|  |   LangGraph Planner    |  Fallback   |    Rule-Based Planner    |  |
|  |  (Groq / Llama 3 LLM)  | ----------> |   (Regex + Templates)    |  |
|  +------------------------+             +--------------------------+  |
|                                                                       |
|  +-----------------------------------------------------------------+  |
|  |                         Agent Network                           |  |
|  |  Weather Agent    Ocean Agent       Geo Agent     Risk Agent    |  |
|  |  Route Agent      Passage Agent     Anomaly Agent Simulation    |  |
|  +-----------------------------------------------------------------+  |
|                                                                       |
|  +-----------------------------------------------------------------+  |
|  |                   Tool Adapters & Connectors                    |  |
|  |  Open-Meteo       Copernicus        NASA Earthdata  EOT20 Tides |  |
|  |  GEBCO Bathymetry Marine Regions    ProtectedPlanet ISRO MOSDAC |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------+
|                       Data & Storage Infrastructure                   |
|  - PostgreSQL + PostGIS (Port 5433): EEZ, MPAs, Ports, Vessel Registry|
|  - Redis (Port 6379): Low-latency cache with variable-specific TTLs   |
|  - MinIO: Satellite tiles and raster archive storage                  |
+-----------------------------------------------------------------------+
```

### Backend Agents (`backend/app/agents/`)
- **Weather & Ocean Agents:** Ingest atmospheric and hydrographic parameters (wind speed/gust, wave height, swell period, sea surface temperature, currents, barometric trends).
- **Geo Agent:** Performs spatial boundary checks against territorial waters, Exclusive Economic Zones (EEZ), and World Database on Protected Areas (WDPA).
- **Risk Agent:** Executes Stage 1 hard vetoes and Stage 2 multi-factor scoring against the requested vessel profile.
- **Route Agent (Radial Scan):** Evaluates 16 directional candidate waypoints within a specified radius around the user to find the safest nearby fishing grounds.
- **Passage Agent (Port-to-Port):** Calculates marine transit corridors along great-circle arcs between ports, evaluating dynamic weather conditions indexed to the exact forecasted hour of arrival at each waypoint.
- **Route Optimizer:** Runs A* search across an H3 hexagonal grid, routing around high-risk zones, shallow bathymetry, and protected reserves.
- **Anomaly Agent:** Identifies thermal marine heatwaves and abnormal current variations against historical baseline distributions.

### Frontend Web Client (`frontend/`)
- Built with React 19, TypeScript, and Vite.
- Interactive map rendering using MapLibre GL for spatial exploration, risk overlays, candidate fishing sectors, and transit routes.
- Slide-out Evidence Panel displaying raw sensor values, confidence metrics, and attribution chains for every recommendation.
- Vessel profile selector to test how recommendations change between small boats, sailing yachts, and commercial ships.

### Android Native Client (`android/`)
- Built with Kotlin, Jetpack Compose, Material 3, and MapLibre Native.
- Designed for field operations on fishing vessels and coastal craft.
- Features a background foreground service ("Watch Mode") that monitors the vessel's live GPS coordinates against nearby marine hazards and triggers OS-level alerts when local conditions deteriorate, even with the screen off.

---

## Data Sources & Integration Status

| Provider / Dataset | Scope & Measurements | Fetch Method | Integration Status |
| --- | --- | --- | --- |
| **Open-Meteo Marine** | Wind, waves, swell, pressure, precipitation forecasts (7-day horizon) | REST API | Live (Primary real-time feed) |
| **Copernicus Marine** | Physical ocean reanalysis, biogeochemistry, altimetry, waves | Python Toolbox | Live (2023 baseline archive ingested) |
| **ERA5 (ECMWF / CDS)** | Atmospheric reanalysis parameters | `cdsapi` | Live (Full 12-month reanalysis dataset) |
| **NASA Earthdata** | Satellite ocean color and sea surface temperature | Bearer Token / API | Live |
| **Global Fishing Watch (GFW)** | Commercial vessel activity and monthly fishing effort | CSV / API | Live |
| **EOT20** | Empirical Ocean Tide model (harmonic tidal elevations) | Precomputed arrays | Live |
| **GEBCO** | Global marine bathymetry and depth contours | Regional OPeNDAP tiles | Live (Curated regional tiles) |
| **Marine Regions** | Maritime boundaries and Exclusive Economic Zones (EEZ v12) | PostGIS spatial layer | Live |
| **Protected Planet (WDPA)** | Marine Protected Areas (MPAs) and OECMs | API v4 + PostGIS | Live |
| **ISRO MOSDAC** | EOS-06 OCM-3 Level-4 chlorophyll and ocean color | Download API | Live |
| **IMD** | Official Indian meteorological cyclone tracks and coastal bulletins | Direct ingest | Adapter ready (Awaiting official key) |
| **INCOIS PFZ Archive** | Potential Fishing Zone advisories (2003-2025) | Portal archive | Blocked on portal credential approval |

---

## Project Structure

```
Jaljeev/
├── backend/
│   ├── app/
│   │   ├── agents/          # Domain agent nodes (Weather, Ocean, Geo, Risk, Passage, etc.)
│   │   ├── api/             # FastAPI routers (marine, chat, map, speech)
│   │   ├── core/            # App settings, Redis caching layer, decision logging
│   │   ├── db/              # SQLAlchemy async database models and session setup
│   │   ├── ml/              # Feature engineering and model training pipelines
│   │   ├── models/          # Shared Pydantic schemas and response contracts
│   │   ├── planner/         # LangGraph state machine and rule-based fallback
│   │   └── tools/           # External API adapters, thread pool executors, circuit breakers
│   ├── tests/               # Pytest suite (93 offline tests covering risks, routing, fallback)
│   └── requirements.txt     # Python backend dependencies
├── frontend/
│   ├── src/                 # React components (MarineMap, ChatPanel, EvidencePanel, etc.)
│   ├── package.json         # Vite and frontend dependencies
│   └── vite.config.ts       # Frontend build configuration
├── android/
│   ├── app/                 # Kotlin Android application source code
│   └── build.gradle.kts     # Android Gradle build configuration
├── infra/
│   └── sql/                 # PostGIS initial schemas, tables, and port seed data
├── scripts/                 # Data acquisition, bathymetry ingestion, and demo prewarm scripts
├── docker-compose.yml       # Container services (PostGIS, Redis, MinIO)
├── CONTEXT.md               # Detailed architectural context and engineering history
├── DESIGN.md                # Component design, UI specifications, and user flows
└── README.md                # Project documentation
```

---

## Local Development & Setup

### Prerequisites
- Docker Desktop
- Python 3.11+
- Node.js 18+ and npm
- Android Studio Ladybug+ with JDK 17 (optional, only needed for Android development)

### 1. Environment Configuration
Clone the repository and set up your local environment file:

```bash
cp .env.example .env
```

Open `.env` and fill in your keys. The system functions out-of-the-box using Open-Meteo, local PostGIS boundaries, and rule-based processing even without external API credentials. If you want LLM query parsing, add your `GROQ_API_KEY`.

### 2. Start Data Infrastructure
Launch the local PostgreSQL/PostGIS, Redis, and MinIO instances:

```bash
docker compose up -d postgres redis minio
```

*Note on ports:* PostgreSQL is mapped to host port **5433** (rather than default 5432) to prevent conflicts with existing local PostgreSQL instances. Redis runs on standard port 6379.

### 3. Run the Backend API
Set up a Python virtual environment and run the server locally:

```bash
cd backend
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Verify that the backend is responding:
- Health check: `http://localhost:8000/health`
- Interactive API documentation: `http://localhost:8000/docs`

### 4. Run the Frontend Application
In a separate terminal, install dependencies and launch Vite:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser to access the web interface.

### 5. Running the Test Suite
I built a comprehensive test suite of 93 unit and integration tests. All tests run locally without making network calls or requiring active external servers:

```bash
cd backend
pytest tests/ -v
```

These tests validate:
- Stage 1 hard-constraint veto enforcement (MPAs, grounding, capsize waves).
- Vessel class parameter isolation (ensuring sail-specific rules never alter motor vessels).
- Barrass squat and under-keel clearance calculations.
- Circuit breaker trip and recovery behavior.
- Complete end-to-end functionality of the zero-dependency rule-based fallback.

---

## Running Demos

Before presenting or running live interactive demos, run the cache prewarm script:

```bash
python scripts/prewarm_demo.py
```

This populates Redis with verified real-world oceanographic and weather data for key coastal test points (such as offshore Visakhapatnam at `17.65, 83.35`). Subsequent queries for these zones will return cached evidence in under 500 milliseconds instead of waiting for live satellite or reanalysis requests.

*Important testing note:* When testing queries, use actual offshore marine coordinates (e.g., 10-20 km offshore) rather than city names. A geocoded city name resolves to the city center on dry land, which the Stage 1 safety filter correctly flags as a hard constraint violation.

---

## Engineering Notes & Gotchas

During the development of JalJeev, I ran into several non-obvious technical challenges:

- **Concurrent Async Execution:** Calling external adapters sequentially (`await x()`, `await y()`) created unbearable latency. All independent data feeds in the agent pipeline are gathered concurrently via `asyncio.gather` with strict per-adapter timeouts, ensuring a slow third-party service never stalls the entire decision engine.
- **Dedicated Thread Pool for Blocking I/O:** Standard `asyncio.to_thread` shares the default loop executor. Under heavy concurrent load, blocking scientific library calls and network requests would queue up and cause false timeouts. I implemented a dedicated, isolated thread pool (`app/tools/_executor.py`) to manage blocking adapter operations.
- **OPeNDAP Bathymetry Truncation:** Large single-bounding-box requests to GEBCO OPeNDAP endpoints can silently truncate and return zero-filled arrays without raising an HTTP error, which downstream code would misinterpret as sea level (0 meters / land). I mitigated this by writing an ingestion utility that downloads compact 1x1 degree regional tiles and enforces a minimum 85% non-zero validation check prior to saving.
- **Coastline Bathymetric Profiles:** In regions like the Mahanadi delta near Puri, shallow water (under 2 meters) extends far out into the Bay of Bengal, which legitimately triggers shallow-water warnings for vessels with deeper drafts. By contrast, the continental shelf off Visakhapatnam drops off quickly to 40-50 meters within a few kilometers of the coast.
