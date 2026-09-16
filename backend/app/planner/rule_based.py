"""
Rule-based fallback for the planner's two LLM jobs — intent parsing and
answer synthesis (app/planner/graph.py). Deterministic, zero external
dependency: no quota, no network call, no variance between runs.

Used automatically whenever the LLM isn't configured OR a live call to it
fails (quota exhausted, network down, etc. — exactly the failure modes hit
repeatedly during development, see CLAUDE.md). This makes the LLM a
genuinely optional enhancement layer for richer free-form phrasing, not a
hard dependency for the system to answer a question at all — consistent
with the project's own rule that the LLM never computes anything; here it
doesn't even have to be present for the system to work.

Coverage is intentionally scoped to the query shapes this system actually
supports (safety check, route request, current conditions) — not general
NLU. An unmatched or ambiguous message falls through to "general" honestly
rather than guessing.
"""
import re

from app.agents.vessel_profiles import CLASS_ALIASES, VESSEL_CLASSES

# Same curated port list as infra/sql/002_ports_seed.sql — kept in sync
# manually since this needs to be synchronous/importable without a DB
# round-trip during intent parsing.
KNOWN_PLACES = [
    "Puri", "Paradip", "Visakhapatnam", "Vizag", "Kakinada", "Chennai",
    "Nagapattinam", "Rameswaram", "Tuticorin", "Kochi", "Cochin", "Kollam",
    "Mangalore", "Goa", "Mormugao", "Mumbai", "Veraval", "Porbandar",
    "Kandla", "Port Blair",
]

_ROUTE_WORDS = ("route", "path", "way to", "how do i get", "navigate")
# A passage is a route with a DESTINATION — the sailor/trader question
# ("sail from Kochi to Colombo"), as opposed to the fisherman's radial
# "find me a safe zone within 40km". Checked before _ROUTE_WORDS because
# "how do I get to Chennai" matches both, and the more specific reading
# (it names where you're going) is the right one.
_PASSAGE_WORDS = ("passage", "voyage", "sail to", "sail from", "crossing", "deliver", "cargo to", "bound for")
_SAFEST_ZONE_WORDS = ("safest", "safe zone", "where should i fish", "best place", "find a")
_CURRENT_CONDITIONS_WORDS = ("safe to fish", "safe to go", "conditions", "weather", "wave", "wind", "is it safe")

_COORD_RE = re.compile(r"(-?\d{1,2}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)")
_RADIUS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:km|kms|kilometers?|kilometres?)\b", re.IGNORECASE)
_VESSEL_LEN_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:m|metre|meter)s?\s*(?:boat|vessel|yacht|ship)", re.IGNORECASE)

# "from X to Y" / "X to Y" — the origin/destination pair a passage needs.
# Anchored on the known-ports list rather than free text: an unknown place
# name can't be planned to anyway (it has no harbour-entrance coordinates),
# so matching one would only produce a confident failure later.
_PLACES_ALT = "|".join(re.escape(p) for p in KNOWN_PLACES)
_FROM_TO_RE = re.compile(
    r"\bfrom\s+(?:the\s+)?(" + _PLACES_ALT + r")\b.*?\bto\s+(?:the\s+)?(" + _PLACES_ALT + r")\b",
    re.IGNORECASE | re.DOTALL,
)
_TO_RE = re.compile(r"\bto\s+(?:the\s+)?(" + _PLACES_ALT + r")\b", re.IGNORECASE)

# Longest alias first so "bulk carrier" wins over "bulk", and "sailing boat"
# over "sail" — a shorter alias matching first would silently pick a
# different vessel class than the user named.
_SORTED_ALIASES = sorted(CLASS_ALIASES.items(), key=lambda kv: -len(kv[0]))
_CLASS_KEY_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(VESSEL_CLASSES, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def _parse_vessel_class(lower: str) -> str | None:
    """
    Deterministic vessel-class extraction. Exact registry keys first (a
    caller echoing back a class the API gave it), then the free-text alias
    table. Returns None when nothing matches — the caller then falls through
    to the documented default rather than this function guessing.
    """
    key_match = _CLASS_KEY_RE.search(lower)
    if key_match:
        return key_match.group(1).lower()
    for alias, class_key in _SORTED_ALIASES:
        if re.search(r"\b" + re.escape(alias) + r"\b", lower):
            return class_key
    return None
_PLACE_RE = re.compile(
    r"\b(?:near|off|offshore|at|from|around)\s+(?:the\s+)?(" + "|".join(re.escape(p) for p in KNOWN_PLACES) + r")\b",
    re.IGNORECASE,
)
_PLACE_ANYWHERE_RE = re.compile("|".join(re.escape(p) for p in KNOWN_PLACES), re.IGNORECASE)


def parse_intent_rule_based(message: str) -> dict:
    lower = message.lower()

    destination_name = None
    origin_name = None
    from_to = _FROM_TO_RE.search(message)
    if from_to:
        origin_name, destination_name = from_to.group(1), from_to.group(2)
    else:
        to_match = _TO_RE.search(message)
        if to_match:
            destination_name = to_match.group(1)

    # A named destination IS the passage signal, with or without a keyword:
    # "Kochi to Tuticorin" is unambiguously a passage request even though it
    # contains no verb at all.
    if destination_name or any(w in lower for w in _PASSAGE_WORDS):
        intent_type = "passage"
    elif any(w in lower for w in _ROUTE_WORDS):
        intent_type = "route"
    elif any(w in lower for w in _SAFEST_ZONE_WORDS):
        intent_type = "safest_zone"
    elif any(w in lower for w in _CURRENT_CONDITIONS_WORDS):
        intent_type = "current_conditions"
    else:
        intent_type = "general"

    lat = lon = None
    coord_match = _COORD_RE.search(message)
    if coord_match:
        lat, lon = float(coord_match.group(1)), float(coord_match.group(2))

    location_name = None
    place_match = _PLACE_RE.search(message) or _PLACE_ANYWHERE_RE.search(message)
    if place_match:
        location_name = place_match.group(1) if place_match.re is _PLACE_RE else place_match.group(0)

    radius_match = _RADIUS_RE.search(message)
    radius_km = float(radius_match.group(1)) if radius_match else 40.0

    vessel_match = _VESSEL_LEN_RE.search(message)
    vessel_length_m = float(vessel_match.group(1)) if vessel_match else 8.0

    # On a passage, the place named after "from" is the origin — don't let
    # the generic place matcher report the destination as the location.
    if origin_name:
        location_name = origin_name

    return {
        "intent_type": intent_type,
        "location_name": location_name,
        "lat": lat,
        "lon": lon,
        "radius_km": radius_km,
        "vessel_length_m": vessel_length_m,
        "vessel_class": _parse_vessel_class(lower),
        "origin_name": origin_name,
        "destination_name": destination_name,
    }


def synthesize_answer_rule_based(evidence: dict) -> str:
    """Renders the EvidenceReceipt (already fully structured — see evidence_agent.py)
    into readable text directly, no LLM. Cannot hallucinate: every line is a
    direct field read, nothing is generated or inferred."""
    if not evidence:
        return "I don't have enough information to answer that — no location was resolved for this question."

    lines = []
    summary = evidence.get("recommendation_summary")
    if summary:
        lines.append(summary)

    risk_level = evidence.get("risk_level")
    risk_score = evidence.get("risk_score")
    if risk_level and risk_score is not None:
        lines.append(f"Risk: {risk_level} ({risk_score}/100)")

    # Exact coordinates, not just distance/bearing — a real answer once told
    # a user "the safest zone is 20km at bearing 45 deg" with no way to
    # actually find it without doing that math themselves. Always surface
    # this when the evidence has it (see evidence_agent.py).
    lat, lon = evidence.get("location_lat"), evidence.get("location_lon")
    if lat is not None and lon is not None:
        lines.append(f"Coordinates: {lat}, {lon}")
        maps_url = evidence.get("location_maps_url")
        if maps_url:
            lines.append(f"Open in Google Maps: {maps_url}")

    factor_lines = evidence.get("factor_lines") or []
    if factor_lines:
        lines.append("Why:")
        lines.extend(f"  - {f}" for f in factor_lines)

    gaps = evidence.get("data_gaps") or []
    if gaps:
        lines.append(f"Missing data: {', '.join(gaps)}")

    rejected = evidence.get("rejected_alternatives") or []
    if rejected:
        lines.append("Other spots considered and rejected:")
        lines.extend(f"  - {r}" for r in rejected)

    sources = evidence.get("sources_used") or []
    freshness = evidence.get("data_freshness") or {}
    if sources:
        source_bits = [f"{s} ({freshness[s]})" if s in freshness else s for s in sources]
        lines.append(f"Sources: {', '.join(source_bits)}")

    confidence = evidence.get("confidence_statement")
    if confidence and confidence != summary:
        lines.append(confidence)

    validation_note = evidence.get("validation_note")
    if validation_note:
        lines.append(f"NOTE: {validation_note}")

    return "\n".join(lines) if lines else "No details available for this query."
