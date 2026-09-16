"""
LangGraph planner — the conversational front door described in the PRD
(Section 1: "the chatbot is only the front door"). The LLM here does two
things ONLY: (1) parse intent from natural language into structured
parameters, (2) phrase the final answer from tool outputs it is given.
It never computes a number itself (PRD Section 6) — all physics/GIS/risk
math happens in the deterministic agents already built.

Graph:
    parse_intent -> resolve_location -> execute_tools -> synthesize_answer

Each node appends a human-readable line to `trace`, so the caller (the
/chat endpoint) can show the planning process, not just the final answer —
PRD Section 4 ("make agentic behaviour visible").

Context & Memory Agent (app/agents/memory_agent.py) lets resolve_location
fall back to the last location mentioned in this SAME session if the
current message doesn't name one — "what about tomorrow?" without
repeating the place. Evidence Agent (app/agents/evidence_agent.py) builds
a structured receipt from tool_results before synthesis, so the LLM
phrases from an already-organized evidence trail instead of raw nested
JSON, and that receipt travels with the response for a UI evidence panel.
"""
import asyncio
import json
from typing import TypedDict

from groq import Groq
from langgraph.graph import END, StateGraph

from app.agents.evidence_agent import build_receipt_for_passage, build_receipt_for_route, build_receipt_for_state
from app.core.maps import google_maps_url
from app.planner.rule_based import parse_intent_rule_based, synthesize_answer_rule_based
from app.tools._executor import network_executor
from app.agents._timeout import AGENT_TIMEOUT_S, run_with_timeout
from app.agents.geo_agent import run_geo_agent
from app.agents.memory_agent import append_turn, get_last_location
from app.agents.ocean_agent import run_ocean_agent
from app.agents.risk_agent import assess_risk
from app.agents.route_agent import find_safest_zone
from app.agents.satellite_discovery_agent import discover_sources, variables_for_intent
from app.agents.validation_agent import validate
from app.agents.weather_agent import run_weather_agent
from app.core.config import settings
from app.agents.passage_agent import plan_passage
from app.agents.vessel_profiles import VESSEL_CLASSES, resolve_vessel
from app.models.schemas import FusedMarineState, GeoState, OceanState, PassagePlan, RouteRecommendation, VesselProfile, WeatherState
from app.tools.geocode_adapter import geocode
from datetime import datetime, timezone

_client = Groq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None

# Switched from Gemini to Groq (26 Aug 2026) — Gemini's free-tier daily
# quota (20 requests/day for gemini-3.6-flash) was exhausted by testing
# across two sessions, and every "hang" we spent hours chasing turned out
# to be an instant 429 RESOURCE_EXHAUSTED we were silently swallowing, not
# a real timeout. Groq hosts open models (this uses openai/gpt-oss-120b)
# with a much more generous free tier and genuinely fast inference
# (~0.6s measured for a trivial call). The SDK call is still
# synchronous/blocking though, so it's wrapped in the same dedicated
# executor + wait_for pattern as every other external adapter (CLAUDE.md
# gotcha #2) — don't remove that wrapping just because Groq is fast; a
# future slow response should still fail gracefully, not block the loop.
LLM_TIMEOUT_S = 20

# Synthesis gets its own, shorter budget. Intent parsing has no fully
# equivalent fallback in terms of nuance (rule_based's regex parser can miss
# a phrasing the LLM would catch), so it's worth waiting the full 20s and
# retrying once. Synthesis is different: synthesize_answer_rule_based reads
# the SAME EvidenceReceipt fields the LLM prompt is given and is already a
# perfectly safe, correct answer (see core philosophy — it cannot
# hallucinate by construction). Waiting up to 2x20s+0.5s for a strictly
# "nicer-sounding" phrasing before falling back to an equally correct
# template was the single biggest contributor to "the answer takes forever"
# reports (28 Aug 2026) — most of that wait bought nothing, because the
# eventual answer was the template anyway. A tighter budget and no retry
# means a genuinely slow/hung Groq call surfaces the good fallback in ~8s
# instead of ~40s, and a healthy call (measured ~0.6-2s) is unaffected.
SYNTHESIS_LLM_TIMEOUT_S = 8

# Ceiling for the two multi-step searches (radial route, port-to-port
# passage). Each internally bounds its own expensive work — route_agent caps
# full-detail verification at two phases, passage_agent budgets its H3 cell
# count — but neither had an outer ceiling on the /chat path, so a slow
# source could still park the request until the endpoint's own 115s fired.
# Raised from 60s (5 Sep 2026): the fast scan is quick (~1-7s) but
# verification runs the full Ocean Agent (Copernicus login + dataset open)
# for the best candidate, and that consistently takes 30-40s cold. 60s left
# zero margin for Phase 2 expansion or slightly slow networks — measured
# timeouts on every "safest zone" query for Puri. 90s fits alongside the
# worst-case LLM stages (~20s parse + 90s here + 8s synthesis = 118s) with
# the endpoint's 115s ceiling — but the per-agent 40s cap inside
# verification already bounds the real work, so 90s is headroom, not a
# licence for slow calls.
SEARCH_TIMEOUT_S = 90


async def _call_llm(prompt: str, retries: int = 1, timeout_s: float = LLM_TIMEOUT_S) -> tuple[str | None, str | None]:
    """Returns (response_text, None) on success, or (None, reason) on failure — reason is
    always a real, specific string (e.g. "404 model_not_found: ..."), never silently dropped."""
    if not _client:
        return None, "GROQ_API_KEY not configured"
    loop = asyncio.get_running_loop()
    last_reason = None
    for attempt in range(retries + 1):
        try:
            resp = await asyncio.wait_for(
                loop.run_in_executor(
                    network_executor,
                    lambda: _client.chat.completions.create(
                        model=settings.GROQ_MODEL, messages=[{"role": "user", "content": prompt}]
                    ),
                ),
                timeout=timeout_s,
            )
            return resp.choices[0].message.content, None
        except asyncio.TimeoutError:
            last_reason = f"no response within {timeout_s}s"
        except Exception as exc:
            last_reason = f"{type(exc).__name__}: {exc}"
        if attempt < retries:
            await asyncio.sleep(0.5)
    return None, last_reason


class PlannerState(TypedDict, total=False):
    user_message: str
    session_id: str | None
    client_lat: float | None  # browser geolocation, last-resort fallback — see resolve_location
    client_lon: float | None
    intent: dict
    lat: float | None
    lon: float | None
    location_name: str | None
    tool_results: dict
    evidence: dict
    trace: list[str]
    answer: str


INTENT_PROMPT = """You are the intent parser for JalJeev, a marine decision-support system for
Indian fishermen, sailors and maritime traders. Extract structured parameters from the user's
message.

Respond with ONLY a JSON object, no other text, matching this schema:
{{
  "intent_type": "safest_zone" | "current_conditions" | "route" | "passage" | "general",
  "location_name": string or null,
  "lat": number or null,
  "lon": number or null,
  "radius_km": number (default 40),
  "vessel_length_m": number or null,
  "vessel_class": string or null,
  "origin_name": string or null,
  "destination_name": string or null
}}

- "safest_zone": user wants to know where it's safe to fish / go out
- "current_conditions": user wants current weather/sea state at a location
- "route": user wants a route but names no destination (a search outward
  from where they are)
- "passage": user wants to get from one named place to another — "sail from
  Kochi to Tuticorin", "take the cargo to Chennai". Set origin_name and
  destination_name. This is the sailor's and trader's question; "route" is
  the fisherman's.
- "general": anything else (greetings, out-of-scope questions, or a
  follow-up like "what about tomorrow?" that doesn't name a new place —
  leave location_name/lat/lon null in that case, the planner will reuse
  the last location from this conversation if there is one)

"vessel_class" must be EXACTLY one of these keys, or null if the user did
not say what they are sailing. Do not invent a class, do not guess from
context, and do not translate it into your own words — an unrecognised
value is discarded and replaced by the default small fishing boat:
{vessel_classes}

Set "vessel_length_m" only if the user actually states a length. Null
otherwise — the vessel class already carries a representative length, and
a length you invented would override it.

User message: {message}
"""

SYNTHESIS_PROMPT = """You are JalJeev, a marine safety assistant for Indian fishermen, sailors and
maritime traders. Match your language to who is asking: a fisherman wants plain, practical words;
a sailor or a ship's officer expects the normal terms of their trade (bearings, nautical miles,
legs, ETA, under-keel clearance) and is not helped by having them avoided. Answer the
user's question using ONLY the evidence receipt below — do not invent or estimate any number that
isn't in it. If a value is missing, say so plainly instead of guessing. Cite the data source and
how recent it is when giving a specific number. Keep the answer concise, practical, and in plain
language the person asking would use themselves.

If the receipt describes a passage (leg-by-leg factor lines with bearings and ETAs), give the
legs in order, state the total distance and ETA, and name the WORST leg explicitly — a passage is
judged on its worst hours, not its average. If any leg is marked BEYOND FORECAST HORIZON you must
say plainly that that part of the passage is not forecast and has to be re-planned en route.
Never smooth that over.

If the evidence receipt includes location_lat and location_lon, you MUST state those exact
coordinates in your answer (e.g. "Coordinates: 17.7936, 83.3629") — never describe the location
only as a distance and bearing ("20km at 45 deg") when the exact coordinates are available in the
receipt. These coordinates are the point the recommendation is ABOUT (the recommended/destination
zone for a route question, or the queried point for a conditions question) — NOT the user's
current position, so label them accordingly (e.g. "Recommended spot: ..." not "Current spot: ...").
Do not compute or estimate coordinates yourself if they are not in the receipt.

User's question: {message}

Evidence receipt (JSON) — sources, factor breakdown, gaps, confidence, and rejected alternatives if any:
{evidence}

Answer:
"""


async def parse_intent(state: PlannerState) -> PlannerState:
    trace = state.get("trace", [])
    trace.append("Planner: parsing intent from user message")

    if not _client:
        trace.append("Planner: GROQ_API_KEY not configured — using rule-based intent parser")
        intent = parse_intent_rule_based(state["user_message"])
    else:
        text, reason = await _call_llm(
            INTENT_PROMPT.format(
                message=state["user_message"],
                vessel_classes=", ".join(sorted(VESSEL_CLASSES)),
            )
        )
        if text is None:
            trace.append(f"Planner: LLM call failed ({reason}) — falling back to rule-based intent parser")
            intent = parse_intent_rule_based(state["user_message"])
        else:
            raw = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            try:
                intent = json.loads(raw)
            except json.JSONDecodeError:
                trace.append("Planner: LLM returned unparseable JSON — falling back to rule-based intent parser")
                intent = parse_intent_rule_based(state["user_message"])

    # Whatever produced this intent (LLM or rule-based), the vessel class is
    # passed through resolve_vessel before it can affect any threshold — an
    # invented class degrades to the documented default rather than silently
    # scoring, say, a tanker against an 8m boat's numbers.
    variables = variables_for_intent(intent.get("intent_type", "general"))
    if variables:
        trace.append(f"Planner: this question needs {', '.join(variables)} (Satellite Discovery Agent)")

    trace.append(f"Planner: intent = {intent.get('intent_type')}, location = {intent.get('location_name') or (intent.get('lat'), intent.get('lon'))}")
    return {**state, "intent": intent, "trace": trace}


async def resolve_location(state: PlannerState) -> PlannerState:
    trace = state.get("trace", [])
    intent = state["intent"]
    lat, lon = intent.get("lat"), intent.get("lon")
    location_name = intent.get("location_name")

    if lat is None and location_name:
        trace.append(f"Geocoding '{location_name}' (Nominatim/OpenStreetMap)")
        geo = await geocode(location_name)
        if geo.get("status") == "success":
            lat, lon = geo["lat"], geo["lon"]
            trace.append(f"Resolved to {lat:.4f}, {lon:.4f} ({geo.get('display_name')})")
        else:
            trace.append(f"Geocoding failed: {geo.get('status')}")

    # Context & Memory Agent: no location in THIS message — check whether
    # this session mentioned one earlier ("what about tomorrow?").
    if lat is None and state.get("session_id"):
        remembered = await get_last_location(state["session_id"])
        if remembered:
            lat, lon = remembered["lat"], remembered["lon"]
            location_name = remembered.get("location_name")
            trace.append(
                f"Context & Memory Agent: no location in this message — reusing "
                f"{lat:.4f}, {lon:.4f} from earlier in this conversation ('{remembered['from_message']}')"
            )

    # Last resort: the browser's own geolocation, when granted — this is
    # what makes "where can I go to fish?" (no place named, nothing said
    # earlier in this session either) actually answerable, instead of
    # bouncing the question back asking the user to somehow supply their
    # own coordinates. Named-place and remembered-conversation location
    # both still win over this — it only fires when neither said anything.
    if lat is None and state.get("client_lat") is not None and state.get("client_lon") is not None:
        lat, lon = state["client_lat"], state["client_lon"]
        trace.append(f"No location named — using the browser's reported current position ({lat:.4f}, {lon:.4f})")

    return {**state, "lat": lat, "lon": lon, "location_name": location_name, "trace": trace}


async def execute_tools(state: PlannerState) -> PlannerState:
    trace = state.get("trace", [])
    intent = state["intent"]
    lat, lon = state.get("lat"), state.get("lon")

    if lat is None or lon is None:
        trace.append("No location resolved — cannot call marine agents")
        return {**state, "tool_results": {"error": "No location provided or resolved"}, "evidence": {}, "trace": trace}

    vessel = resolve_vessel(intent.get("vessel_class"), length_m=intent.get("vessel_length_m"))
    intent_type = intent.get("intent_type", "current_conditions")
    if vessel.vessel_class != "fishing_small":
        trace.append(f"Vessel: {vessel.vessel_name} ({vessel.propulsion}, {vessel.draft_m:.1f}m draft)")

    if intent_type == "passage":
        destination_name = intent.get("destination_name")
        if not destination_name:
            trace.append("Passage intent but no destination resolved — cannot plan a port-to-port passage")
            return {
                **state,
                "tool_results": {"error": "No destination named. Tell me which port you're heading to."},
                "evidence": {},
                "trace": trace,
            }
        trace.append(
            f"Executing plan: Passage Agent (A* over an H3 corridor to {destination_name}), "
            f"Risk Agent per cell, re-scored per leg against arrival-hour forecast"
        )
        # The origin is where the vessel IS — already resolved into lat/lon
        # by resolve_location (from a named place, session memory, or the
        # browser's position), so the passage always departs from a real
        # resolved point rather than re-resolving a name here.
        try:
            passage: PassagePlan = await asyncio.wait_for(
                plan_passage(
                    vessel,
                    origin_lat=lat,
                    origin_lon=lon,
                    destination_name=destination_name,
                ),
                timeout=SEARCH_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            trace.append(f"Passage Agent: timed out after {SEARCH_TIMEOUT_S}s")
            return {
                **state,
                "tool_results": {
                    "error": f"Planning the passage to {destination_name} took longer than "
                             f"{SEARCH_TIMEOUT_S}s. Try a nearer destination, or ask again shortly."
                },
                "evidence": {},
                "trace": trace,
            }
        trace.append(
            f"Passage Agent: {'planned' if passage.found_route else 'could not plan'} "
            f"{len(passage.legs)} legs over {passage.cells_evaluated} evaluated cells "
            f"({passage.cells_viable} viable after hard constraints)"
        )
        evidence = build_receipt_for_passage(passage)
        trace.append("Evidence Agent: built reasoning receipt (legs, worst leg, diversion ports, forecast horizon)")
        return {**state, "tool_results": passage.model_dump(), "evidence": evidence.model_dump(), "trace": trace}

    if intent_type == "safest_zone" or intent_type == "route":
        trace.append(f"Executing plan: Weather Agent, Ocean Agent, Geo Agent, Risk Agent x N candidates, Route Agent (range={intent.get('radius_km', 40)}km)")
        try:
            result: RouteRecommendation = await asyncio.wait_for(
                find_safest_zone(lat, lon, intent.get("radius_km", 40), vessel),
                timeout=SEARCH_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            trace.append(f"Route Agent: timed out after {SEARCH_TIMEOUT_S}s")
            return {
                **state,
                "tool_results": {
                    "error": f"Searching for a safe zone took longer than {SEARCH_TIMEOUT_S}s. "
                             "Try again shortly — the ocean data sources may be slow right now."
                },
                "evidence": {},
                "trace": trace,
            }
        trace.append(f"Route Agent: evaluated {len(result.candidates_evaluated)} candidates, {'found' if result.found_safe_zone else 'did not find'} a safe zone")
        evidence = build_receipt_for_route(result)
        trace.append("Evidence Agent: built reasoning receipt (sources, factors, rejected alternatives)")
        return {**state, "tool_results": result.model_dump(), "evidence": evidence.model_dump(), "trace": trace}

    trace.append("Executing plan: Weather Agent, Ocean Agent, Geo Agent, Risk Agent, Validation Agent")
    # Per-agent ceilings, NOT a bare gather (CLAUDE.md gotcha #3). This used
    # to be an unbounded `asyncio.gather(...)`, which is why /chat returned a
    # 504 on coordinates that /marine/state answered fine in 25s: the REST
    # path wrapped each agent in this timeout and the planner did not, so a
    # hung Copernicus fetch or stalled Postgres connection took down the
    # whole request instead of degrading to "that source is missing".
    weather, ocean, geo = await asyncio.gather(
        run_with_timeout(run_weather_agent(lat, lon), "Weather Agent", WeatherState()),
        run_with_timeout(run_ocean_agent(lat, lon), "Ocean Agent", OceanState()),
        run_with_timeout(run_geo_agent(lat, lon), "Geo Agent", GeoState()),
    )
    for _state, _name in ((weather, "Weather"), (ocean, "Ocean"), (geo, "Geo")):
        if any("timed out" in m for m in (_state.missing or [])):
            trace.append(f"{_name} Agent: timed out after {AGENT_TIMEOUT_S}s — reported as a data gap")
    risk = assess_risk(weather, ocean, geo, vessel)
    validation = validate(weather, ocean, geo, risk)
    trace.append(f"Risk Agent: {risk.risk_level} ({risk.risk_score}/100)")
    if validation.issues:
        trace.append(f"Validation Agent: FLAGGED — {'; '.join(validation.issues)}")
    else:
        trace.append("Validation Agent: passed")

    gaps = weather.missing + ocean.missing + geo.missing
    confidence_note = ("VALIDATION FAILED — " + "; ".join(validation.issues)) if validation.issues else (
        f"Partial data — missing: {', '.join(gaps)}" if gaps else "All queried sources responded successfully."
    )
    fused = FusedMarineState(
        lat=lat, lon=lon, maps_url=google_maps_url(lat, lon), queried_at=datetime.now(timezone.utc),
        weather=weather, ocean=ocean, geo=geo, risk=risk, validation=validation,
        confidence_note=confidence_note,
    )
    evidence = build_receipt_for_state(fused)
    trace.append("Evidence Agent: built reasoning receipt (sources, factors, confidence)")

    return {**state, "tool_results": fused.model_dump(), "evidence": evidence.model_dump(), "trace": trace}


async def synthesize_answer(state: PlannerState) -> PlannerState:
    trace = state.get("trace", [])
    trace.append("Planner: synthesizing natural-language answer from the evidence receipt")

    evidence = state.get("evidence") or state.get("tool_results", {})

    # append_turn (a Redis write) and the LLM phrasing call are independent
    # of each other — the memory write doesn't need the LLM's answer, and
    # the LLM prompt doesn't need memory to have been written yet. They used
    # to be sequential awaits, which serialized a real (if usually small)
    # Redis round-trip in front of every synthesis call for no reason.
    memory_write = (
        append_turn(
            state["session_id"],
            user_message=state["user_message"],
            resolved_lat=state.get("lat"),
            resolved_lon=state.get("lon"),
            location_name=state.get("location_name"),
            intent_type=state.get("intent", {}).get("intent_type"),
        )
        if state.get("session_id")
        else None
    )

    if not _client:
        if memory_write is not None:
            await memory_write
        trace.append("Planner: GROQ_API_KEY not configured — using template-based answer synthesis")
        return {**state, "answer": synthesize_answer_rule_based(evidence if isinstance(evidence, dict) else {}), "trace": trace}

    llm_call = _call_llm(
        SYNTHESIS_PROMPT.format(message=state["user_message"], evidence=json.dumps(evidence, default=str)),
        retries=0,
        timeout_s=SYNTHESIS_LLM_TIMEOUT_S,
    )
    if memory_write is not None:
        (text, reason), _ = await asyncio.gather(llm_call, memory_write)
    else:
        text, reason = await llm_call
    if text is None:
        trace.append(f"Planner: LLM call failed for synthesis ({reason}) — falling back to template-based answer")
        return {**state, "answer": synthesize_answer_rule_based(evidence if isinstance(evidence, dict) else {}), "trace": trace}

    return {**state, "answer": text.strip(), "trace": trace}


def build_graph():
    graph = StateGraph(PlannerState)
    graph.add_node("parse_intent", parse_intent)
    graph.add_node("resolve_location", resolve_location)
    graph.add_node("execute_tools", execute_tools)
    graph.add_node("synthesize_answer", synthesize_answer)

    graph.set_entry_point("parse_intent")
    graph.add_edge("parse_intent", "resolve_location")
    graph.add_edge("resolve_location", "execute_tools")
    graph.add_edge("execute_tools", "synthesize_answer")
    graph.add_edge("synthesize_answer", END)

    return graph.compile()


_compiled_graph = None


async def run_planner(
    user_message: str,
    session_id: str | None = None,
    client_lat: float | None = None,
    client_lon: float | None = None,
) -> PlannerState:
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return await _compiled_graph.ainvoke(
        {
            "user_message": user_message,
            "session_id": session_id,
            "client_lat": client_lat,
            "client_lon": client_lon,
            "trace": [],
        }
    )
