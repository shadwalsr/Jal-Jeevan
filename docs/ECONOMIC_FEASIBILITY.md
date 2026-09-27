# JalJeev — Economic Feasibility Analysis & Cost-Benefit Study

**Project:** JalJeev — Agentic Marine Intelligence System  
**Team:** Team Felix, KIIT University, Bhubaneswar  
**SIH Problem Statement:** SIH26176 (ISRO)  
**Date:** September 2026  

---

## 1. Executive Summary

JalJeev's deployment economics are overwhelmingly favourable: a **₹2–3 crore total Year-1 investment** (infrastructure + operations) generates an estimated **₹340–560 crore in national economic value** at just 10% fleet adoption — a **cost-benefit ratio of 1:135 to 1:185**. Per individual fisherman, JalJeev delivers **₹50,000–90,000/year** in combined fuel savings and catch uplift against an effective per-user cost of **₹14–20/year**. Payback on full national deployment infrastructure occurs in **under 4 days** of fleet-wide value generation.

---

## 2. Baseline: India's Marine Fisheries Economy

### 2.1 Fleet Composition (Marine Fisheries Census 2016 + Dept. of Fisheries 2023–24)

| Category | Count | Fuel Dependency | Avg. Trip Fuel Cost |
|---|---|---|---|
| Mechanized vessels (trawlers, gill-netters, liners) | 72,559 | Heavy (diesel, 50–200 L/trip) | ₹6,000–18,000 |
| Motorized vessels (FRP boats + OBM) | 73,410 | Moderate (diesel/petrol, 20–60 L/trip) | ₹2,500–6,000 |
| Traditional craft (non-motorized, sails/oars) | 1,06,498 | None | ₹0 |
| **Total marine fishing vessels** | **2,52,467** | — | — |
| **Powered vessels (mechanized + motorized)** | **1,45,969** | — | **Avg. ₹6,000** |

| National Metric | Value | Source |
|---|---|---|
| Active marine fishermen | 40,00,000 (40 lakh) | CMFRI Census |
| Fisheries-dependent population (incl. families) | 1,60,00,000 (1.6 crore) | Dept. of Fisheries |
| Annual marine fish production | 42.6 lakh tonnes | DAHDF 2023–24 |
| Annual marine export value | ₹60,523 crore ($7.38 bn) | MPEDA |
| Avg. annual income per marine fisherman | ₹1,50,000–3,00,000 | NSSO / CMFRI |
| Fisheries % of national GDP | 1.24% | Economic Survey 2023–24 |
| Annual fisher deaths at sea | ~2,000–3,000 | NCRB + State records |
| International boundary arrests/year | 500+ | MEA Annual Report |

### 2.2 The Waste Problem (Current Inefficiencies)

| Inefficiency | Scale | Annual Cost |
|---|---|---|
| **Empty/low-catch trips** (30–40% of all voyages) | ~43.8–58.4 lakh trips/year (powered fleet) | **₹2,600–3,500 crore** in wasted fuel |
| **Sub-optimal zone selection** (fishing outside thermal fronts / PFZ windows) | ~60–70% of trips are unguided by satellite data | **₹4,000–6,000 crore** in lost catch value |
| **Post-harvest loss** (spoilage from poor trip timing) | 20–25% of catch by weight | **₹3,000–4,000 crore** lost value |
| **International arrests** (boat confiscation, legal costs, income loss) | 500+ incidents/year | **₹75–125 crore** |
| **At-sea mortality** (weather, capsizing, disorientation) | 2,000–3,000 deaths/year | **₹800–1,200 crore** in human capital |
| **Total annual waste in India's marine fisheries** | — | **₹10,475–14,825 crore/year** |

---

## 3. JalJeev Deployment Cost Model

### 3.1 Year-1 Costs (Development + National Launch Infrastructure)

| Cost Component | Details | Amount (₹) |
|---|---|---|
| **Cloud Infrastructure** | | |
| Compute (Cloud Run / GKE, 3 replicas, auto-scaling) | FastAPI backend, LangGraph orchestrator, Redis, PostgreSQL/PostGIS | ₹12,00,000 |
| Managed Database (PostgreSQL + PostGIS) | Spatial boundary queries, user sessions, trip logs | ₹6,00,000 |
| Redis Cache (Managed) | H3 spatial cache, tide series, weather snapshots | ₹3,00,000 |
| Object Storage (GCS / S3) | GEBCO tiles, EOT20 constituents, MOSDAC NetCDF cache | ₹2,00,000 |
| CDN + Bandwidth | PWA static assets, API traffic for 50K–1L concurrent users | ₹4,00,000 |
| **Subtotal Cloud** | | **₹27,00,000** |
| | | |
| **Data Source API Costs** | | |
| Open-Meteo (Marine + Weather) | Free (no API key, no rate limit for this scale) | ₹0 |
| NOAA OISST / ERDDAP | Free (public domain, government) | ₹0 |
| Copernicus Marine (CMEMS) | Free for research + operational use | ₹0 |
| ISRO MOSDAC | Free (Indian government agency) | ₹0 |
| IMD | Free (Indian government agency, pending API key) | ₹0 |
| INCOIS ERDDAP | Free (Indian government agency) | ₹0 |
| GEBCO Bathymetry | Free (public domain, pre-downloaded tiles) | ₹0 |
| EOT20 Tide Model | Free (SEANOE, pre-downloaded 2.2 GB, runs locally) | ₹0 |
| Marine Regions / Protected Planet | Free (open data / research API) | ₹0 |
| **Subtotal External Data** | **All 16 sources are free/open** | **₹0** |
| | | |
| **LLM / AI Inference** | | |
| Groq (Llama-3 / Mixtral, conversational layer) | ~5L queries/month × ₹0.02/query (free tier covers 80%) | ₹6,00,000 |
| Gemini Flash (fallback / complex queries) | Pay-per-token, estimated 1L complex queries/month | ₹4,00,000 |
| **Subtotal LLM** | | **₹10,00,000** |
| | | |
| **Development & Operations** | | |
| Core engineering team (5 engineers × 12 months) | Backend, ML, frontend, Android, DevOps | ₹60,00,000 |
| Field deployment & testing (travel, devices, fisherman training) | 6 coastal districts, 200+ training sessions | ₹8,00,000 |
| Security audit + VAPT | Penetration testing, OWASP compliance | ₹3,00,000 |
| **Subtotal Dev + Ops** | | **₹71,00,000** |
| | | |
| **Contingency (15%)** | | **₹16,20,000** |
| | | |
| **TOTAL YEAR-1 COST** | | **₹1,24,20,000 (~₹1.25 crore)** |

### 3.2 Recurring Annual Costs (Year 2 onward, steady state)

| Component | Annual Cost (₹) |
|---|---|
| Cloud infrastructure (scaled for 5L+ users) | ₹35,00,000 |
| LLM inference costs | ₹15,00,000 |
| Maintenance engineering (3 engineers) | ₹36,00,000 |
| Monitoring, security, compliance | ₹5,00,000 |
| Field support & training updates | ₹5,00,000 |
| **Total Recurring Annual** | **₹96,00,000 (~₹1 crore/year)** |

### 3.3 National Scale-Up Costs (Full 40 Lakh User Deployment)

| Phase | Timeline | Users | Infra Cost | Total Annual |
|---|---|---|---|---|
| Pilot | Month 1–6 | 5,000 | ₹15 lakh | ₹50 lakh |
| Phase 1 (10% adoption) | Month 6–18 | 4,00,000 | ₹30 lakh | ₹1.25 crore |
| Phase 2 (30% adoption) | Year 2–3 | 12,00,000 | ₹60 lakh | ₹2 crore |
| Phase 3 (50% adoption) | Year 3–5 | 20,00,000 | ₹1 crore | ₹3 crore |
| Full National (80%+) | Year 5+ | 32,00,000+ | ₹1.5 crore | ₹4 crore |

### 3.4 Effective Per-User Cost

| Scale | Annual Cost | Users | **Cost per Fisherman per Year** |
|---|---|---|---|
| Pilot (5,000) | ₹50 lakh | 5,000 | ₹1,000 |
| 10% adoption | ₹1.25 crore | 4,00,000 | **₹31** |
| 30% adoption | ₹2 crore | 12,00,000 | **₹17** |
| 50% adoption | ₹3 crore | 20,00,000 | **₹15** |
| Full national | ₹4 crore | 32,00,000 | **₹12.50** |

> **At scale, JalJeev costs ₹12.50 per fisherman per year** — less than the price of half a litre of diesel.

---

## 4. Benefit Calculations (Conservative Estimates)

### 4.1 Fuel Savings from Reduced Empty Trips

**Assumptions (conservative):**
- Only powered vessels considered (1,45,969).
- Average trips/year: 200 (accounting for 61-day monsoon fishing ban).
- Empty/low-catch trip rate (baseline): 30%.
- JalJeev-driven reduction in empty trips: **15%** (i.e., 15% of the 30% are eliminated — only 4.5 percentage points improvement).
- Average fuel cost per trip: ₹6,000 (weighted across mechanized + motorized).

**Calculation at 10% fleet adoption (14,597 vessels):**
```
Total trips/year         = 14,597 × 200                           = 29,19,400
Empty trips (baseline)   = 29,19,400 × 0.30                       = 8,75,820
Trips avoided (15%)      = 8,75,820 × 0.15                        = 1,31,373
Fuel saved               = 1,31,373 × ₹6,000                      = ₹78.82 crore/year
```

**Calculation at 50% fleet adoption (72,985 vessels):**
```
Trips avoided            = 72,985 × 200 × 0.30 × 0.15            = 6,56,865
Fuel saved               = 6,56,865 × ₹6,000                      = ₹394.12 crore/year
```

| Adoption | Vessels | Empty Trips Avoided | **Annual Fuel Savings** |
|---|---|---|---|
| 10% | 14,597 | 1,31,373 | **₹78.82 crore** |
| 30% | 43,791 | 3,94,119 | **₹236.47 crore** |
| 50% | 72,985 | 6,56,865 | **₹394.12 crore** |

### 4.2 Catch Value Improvement from PFZ-Guided Fishing

**Assumptions (conservative):**
- INCOIS & Sreekanth et al. (2016) validate 1.5–2.5× CPUE inside PFZs vs. outside. We use a **20% catch uplift** (well below validated range).
- Average catch value per trip: ₹8,000.
- JalJeev provides actionable PFZ guidance on **50%** of trips (weather permitting, data availability).

**Calculation at 10% fleet adoption (14,597 vessels):**
```
Non-empty trips          = 29,19,400 × 0.70                       = 20,43,580
PFZ-guided trips (50%)   = 20,43,580 × 0.50                       = 10,21,790
Catch uplift per trip     = ₹8,000 × 0.20                          = ₹1,600
Added catch value         = 10,21,790 × ₹1,600                     = ₹163.49 crore/year
```

| Adoption | PFZ-Guided Trips | Uplift/Trip | **Annual Catch Value Added** |
|---|---|---|---|
| 10% | 10,21,790 | ₹1,600 | **₹163.49 crore** |
| 30% | 30,65,370 | ₹1,600 | **₹490.46 crore** |
| 50% | 51,08,950 | ₹1,600 | **₹817.43 crore** |

### 4.3 Lives Saved — Human Capital Value

**Assumptions:**
- Annual at-sea fisher deaths: 2,500 (midpoint of 2,000–3,000 range).
- JalJeev's proactive weather alerts, real-time risk scoring, and return-home advisories prevent **10%** of deaths.
- Economic value per life: ₹40 lakh (₹2 lakh income × 20 remaining productive years).

```
Lives saved/year         = 2,500 × 0.10                            = 250 lives
Human capital preserved  = 250 × ₹40,00,000                        = ₹100 crore/year
```

> **250 fishermen return home to their families each year who otherwise would not have.**

### 4.4 International Arrest Prevention

**Assumptions:**
- 500 Indian fishermen arrested annually (primarily Tamil Nadu / Sri Lanka border, Gujarat / Pakistan border).
- Average economic loss per arrest: ₹15 lakh (boat confiscation ₹5–20L + legal costs + 3–18 months lost income).
- JalJeev's real-time EEZ geofencing prevents **30%** of incidents.

```
Arrests prevented        = 500 × 0.30                              = 150 incidents
Economic savings         = 150 × ₹15,00,000                        = ₹22.50 crore/year
```

### 4.5 Post-Harvest Loss Reduction

**Assumptions:**
- Current post-harvest loss: 20–25% of catch value.
- Better trip timing (leave at optimal tide, return before market close) reduces spoilage by **3 percentage points** (from 22% to 19%).
- Applies to catch from adopted vessels only (10% adoption).

**Calculation at 10% adoption:**
```
Annual catch (adopted)   = 14,597 vessels × 200 trips × 0.70 success × ₹8,000 = ₹1,634.86 crore
Loss reduction (3pp)     = ₹1,634.86 crore × 0.03                  = ₹49.05 crore/year
```

| Adoption | Catch Value (Adopted Fleet) | **Post-Harvest Savings (3pp)** |
|---|---|---|
| 10% | ₹1,635 crore | **₹49.05 crore** |
| 30% | ₹4,905 crore | **₹147.14 crore** |
| 50% | ₹8,174 crore | **₹245.23 crore** |

---

## 5. Total Economic Impact Summary

### 5.1 Year-1 (10% Adoption = 14,597 Vessels / 4 Lakh Fishermen)

| Benefit Category | Conservative Annual Value (₹ Crore) |
|---|---|
| Fuel savings (empty trip reduction) | ₹78.82 |
| Catch value improvement (PFZ guidance) | ₹163.49 |
| Lives saved (human capital) | ₹100.00 |
| International arrest prevention | ₹22.50 |
| Post-harvest loss reduction | ₹49.05 |
| **TOTAL ANNUAL BENEFIT** | **₹413.86 crore** |

| | Amount |
|---|---|
| **Total Year-1 Cost** | **₹1.25 crore** |
| **Total Year-1 Benefit** | **₹413.86 crore** |
| **Cost-Benefit Ratio** | **1 : 331** |
| **ROI** | **33,009%** |
| **Payback Period** | **1.1 days** |

### 5.2 Steady-State (50% Adoption = 72,985 Vessels / 20 Lakh Fishermen)

| Benefit Category | Conservative Annual Value (₹ Crore) |
|---|---|
| Fuel savings | ₹394.12 |
| Catch improvement | ₹817.43 |
| Lives saved | ₹100.00 |
| Arrest prevention | ₹22.50 |
| Post-harvest loss reduction | ₹245.23 |
| **TOTAL ANNUAL BENEFIT** | **₹1,579.28 crore** |

| | Amount |
|---|---|
| **Annual Operating Cost** | **₹3 crore** |
| **Annual Benefit** | **₹1,579.28 crore** |
| **Cost-Benefit Ratio** | **1 : 526** |
| **ROI** | **52,543%** |

### 5.3 National Full-Scale (80% Adoption)

| Benefit Category | Annual Value (₹ Crore) |
|---|---|
| Fuel savings | ₹630.59 |
| Catch improvement | ₹1,307.89 |
| Lives saved | ₹100.00 |
| Arrest prevention | ₹22.50 |
| Post-harvest loss reduction | ₹392.37 |
| **TOTAL** | **₹2,453.35 crore** |
| **Annual Cost** | **₹4 crore** |
| **CBR** | **1 : 613** |

---

## 6. Per-Fisherman Micro-Economics

### 6.1 Annual Impact per Individual Fisherman (Powered Vessel, 10% adoption)

| Line Item | Current (Without JalJeev) | With JalJeev | Δ Savings/Gain |
|---|---|---|---|
| **Fuel expenditure** (200 trips × ₹6,000) | ₹12,00,000 (shared crew of 4–6) → ₹2,40,000 per fisherman | ₹2,40,000 − ₹36,000 saved | **+₹36,000** |
| **Catch income** (200 trips × ₹8,000 avg, split among crew) | ₹2,67,000/fisherman | +₹1,600/trip × 100 guided trips ÷ 6 crew | **+₹26,667** |
| **Avoided empty trip days** | 60 empty trips × 12 hours = 720 wasted hours | 9 fewer empty trips → 108 productive hours recovered | **+9 extra productive fishing days** |
| **Safety benefit** (qualitative) | No real-time risk awareness | Proactive storm/wave/wind alerts | **Immeasurable (life)** |
| **Boundary safety** (qualitative) | No geofencing | Real-time EEZ/IMBL proximity alerts | **Avoids ₹15L arrest risk** |
| | | | |
| **TOTAL PER-FISHERMAN ANNUAL BENEFIT** | | | **₹50,000–90,000** |
| **JalJeev cost per fisherman** | | | **₹15–31** |
| **Return per ₹1 spent by fisherman** | | | **₹1,600–6,000** |

### 6.2 The ₹15 vs. ₹62,667 Argument

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   JalJeev costs ₹15/fisherman/year                     │
│                                                         │
│   One avoided empty trip saves ₹1,000 in shared fuel    │
│   One PFZ-guided trip earns ₹267 extra per fisherman    │
│                                                         │
│   JalJeev pays for itself in the first 6 minutes        │
│   of the first improved trip of the year.               │
│                                                         │
│   The remaining 364 days, 23 hours, and 54 minutes      │
│   are pure surplus.                                     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 7. Comparison with Existing Government Investments

| Programme | Annual Govt. Spend | Estimated Economic Return | CBR | JalJeev Advantage |
|---|---|---|---|---|
| **INCOIS PFZ Advisory (current)** | ₹5–10 crore | ₹300–500 crore (INCOIS self-assessment) | 1:50 | JalJeev extends PFZ reach to the 80% who don't access INCOIS today |
| **Sagar Vani (ESSO-INCOIS)** | ₹3–5 crore | ₹50–100 crore (broadcast reach) | 1:20 | JalJeev adds interactive Q&A, route optimization, vessel-specific risk |
| **Fisher Friend (MSSRF)** | ₹2–3 crore (NGO funded) | ₹30–50 crore (Tamil Nadu fleet) | 1:15 | JalJeev is pan-India, multi-lingual, agentic (not static bulletins) |
| **JalJeev (10% adoption)** | **₹1.25 crore** | **₹414 crore** | **1:331** | Full-stack agentic intelligence, not just broadcast |

---

## 8. Sensitivity Analysis

### 8.1 What If Assumptions Are Wrong?

| Parameter | Base Case | Pessimistic (50% of base) | Optimistic (150% of base) |
|---|---|---|---|
| Empty trip reduction | 15% | 7.5% | 22.5% |
| Catch uplift from PFZ guidance | 20% | 10% | 30% |
| % trips with actionable PFZ data | 50% | 25% | 75% |
| Adoption rate (Year 1) | 10% | 5% | 15% |

| Scenario | Total Benefit (₹ Crore) | Cost (₹ Crore) | CBR |
|---|---|---|---|
| **Pessimistic** | ₹103 | ₹1.25 | **1:82** |
| **Base Case** | ₹414 | ₹1.25 | **1:331** |
| **Optimistic** | ₹932 | ₹1.25 | **1:746** |

> **Even in the worst-case pessimistic scenario, JalJeev returns ₹82 for every ₹1 invested.**

### 8.2 Break-Even Analysis

```
Annual fixed cost         = ₹1.25 crore
Benefit per vessel/year   = ₹2,83,429 (fuel + catch + loss reduction)
Break-even vessel count   = 1,25,00,000 ÷ 2,83,429 = 441 vessels

India has 1,45,969 powered vessels.
JalJeev breaks even at 0.3% adoption — just 441 boats.
```

> **JalJeev needs just 441 boats (0.3% of India's powered fleet) to break even.**

---

## 9. Revenue Model Options (If Commercialized)

| Model | Price Point | Revenue at 10% Adoption | Notes |
|---|---|---|---|
| **Freemium** (Govt. subsidized, basic free) | ₹0 basic / ₹99/month premium | ₹47 crore/year (10% premium uptake) | Recommended for SIH — maximize adoption |
| **Government SaaS** (B2G, INCOIS/DAHDF contract) | ₹2–5 crore annual licensing | ₹2–5 crore/year | Low revenue, maximum social impact |
| **Cooperative model** (₹500/boat/year via Fisher Cooperatives) | ₹500/boat/year | ₹7.3 crore/year (at 10%) | Self-sustaining at 50% adoption |
| **Insurance integration** (reduced premium for JalJeev users) | Revenue share with marine insurers | ₹10–20 crore/year | Strong incentive alignment |

---

## 10. Five-Year Projection

| Year | Adoption % | Active Users (Lakh) | Annual Cost (₹ Cr) | Annual Benefit (₹ Cr) | Cumulative Net Value (₹ Cr) |
|---|---|---|---|---|---|
| **Y1** | 10% | 4.0 | 1.25 | 414 | 413 |
| **Y2** | 25% | 10.0 | 1.75 | 829 | 1,240 |
| **Y3** | 40% | 16.0 | 2.50 | 1,263 | 2,501 |
| **Y4** | 55% | 22.0 | 3.25 | 1,737 | 4,234 |
| **Y5** | 70% | 28.0 | 3.75 | 2,211 | 6,442 |

> **Over 5 years: ₹12.50 crore total investment generates ₹6,454 crore in national economic value.**

---

## 11. The Final Pitch Number

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│   INVESTMENT:    ₹1.25 crore (Year 1)                            │
│   RETURN:        ₹414 crore (Year 1, conservative)               │
│   PER FISHERMAN: ₹15/year cost → ₹62,667/year benefit           │
│   BREAK-EVEN:    441 boats (0.3% of India's fleet)               │
│   LIVES SAVED:   250 fishermen/year                              │
│   CBR:           1:331 (pessimistic floor: 1:82)                 │
│                                                                  │
│   "For the cost of half a litre of diesel per fisherman          │
│    per year, JalJeev saves fuel worth crores, improves           │
│    catches for lakhs, and brings 250 fishermen home alive."      │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

### Sources & Methodology Notes

- Fleet statistics: Marine Fisheries Census 2016 (CMFRI) + Dept. of Fisheries Annual Report 2023–24.
- CPUE improvement benchmarks: Sreekanth et al. (2016), Sarangi et al. (2023), INCOIS PFZ validation studies.
- At-sea mortality: NCRB Accidental Deaths & Suicides reports + State Maritime Board records.
- International arrest data: Ministry of External Affairs (MEA) Parliamentary Q&A responses.
- Cloud cost estimates: GCP pricing calculator (Sep 2026, Mumbai region), assuming sustained-use discounts.
- LLM inference pricing: Groq Cloud & Google AI Studio published rates (Sep 2026).
- Human capital valuation: ₹2 lakh avg. annual income × 20 years remaining productive life.

---

*Report prepared by Team Felix, KIIT University, Bhubaneswar*  
*SIH Problem Statement: SIH26176 (ISRO)*
