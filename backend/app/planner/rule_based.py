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

# Port aliases across Indian regional scripts (Devanagari, Odia, Tamil, Telugu, Bengali, Gujarati, Malayalam, Kannada)
PORT_ALIASES: dict[str, str] = {
    # Visakhapatnam
    "विशाखापट्टनम": "Visakhapatnam",
    "विशाखापत्तनम": "Visakhapatnam",
    "विशाखा": "Visakhapatnam",
    "వైజాగ్": "Visakhapatnam",
    "విశాఖపట్నం": "Visakhapatnam",
    "విశాఖ": "Visakhapatnam",
    "விசாகப்பட்டினம்": "Visakhapatnam",
    "விசாகா": "Visakhapatnam",
    "বিশাখাপত্তনম": "Visakhapatnam",
    "ବିଶାଖାପାଟଣା": "Visakhapatnam",
    "વિશાખાપટ્ટનમ": "Visakhapatnam",
    "ವಿಶಾಖಪಟ್ಟಣ": "Visakhapatnam",
    "വിശാഖപട്ടണം": "Visakhapatnam",
    "vizag": "Visakhapatnam",

    # Paradip
    "पारादीप": "Paradip",
    "पारदीप": "Paradip",
    "ପାରାଦୀପ": "Paradip",
    "பாராதிப்": "Paradip",
    "పారదీప్": "Paradip",
    "প্যারাডিপ": "Paradip",
    "પારાદીપ": "Paradip",
    "ಪಾರಾದೀಪ್": "Paradip",
    "പാരാദീപ്": "Paradip",
    "para deep": "Paradip",
    "para dip": "Paradip",

    # Puri
    "पुरी": "Puri",
    "ପୁରୀ": "Puri",
    "பூரி": "Puri",
    "పూరీ": "Puri",
    "পুরী": "Puri",
    "પુરી": "Puri",
    "ಪುರಿ": "Puri",
    "പൂരി": "Puri",

    # Kochi
    "कोच्चि": "Kochi",
    "कोचीन": "Kochi",
    "കൊച്ചി": "Kochi",
    "கொச்சி": "Kochi",
    "కొచ్చి": "Kochi",
    "কোচি": "Kochi",
    "କୋଚି": "Kochi",
    "કોચી": "Kochi",
    "ಕೊಚ್ಚಿ": "Kochi",
    "cochin": "Kochi",

    # Chennai
    "चेन्नई": "Chennai",
    "சென்னை": "Chennai",
    "చెన్నై": "Chennai",
    "ചെന്നൈ": "Chennai",
    "ચેન્નઈ": "Chennai",
    "ଚେନ୍ନାଇ": "Chennai",
    "চেন্নাই": "Chennai",
    "ಚೆನ್ನೈ": "Chennai",
    "madras": "Chennai",

    # Mumbai
    "मुंबई": "Mumbai",
    "மும்பை": "Mumbai",
    "ముంబై": "Mumbai",
    "മുംബൈ": "Mumbai",
    "મુંબઈ": "Mumbai",
    "ମୁମ୍ବାଇ": "Mumbai",
    "মুম্বাই": "Mumbai",
    "ಮುಂಬೈ": "Mumbai",
    "bombay": "Mumbai",

    # Goa
    "गोवा": "Goa",
    "ગોવા": "Goa",
    "கோவா": "Goa",
    "గోవా": "Goa",
    "ഗോവ": "Goa",
    "ଗୋଆ": "Goa",
    "গোয়া": "Goa",
    "ಗೋವಾ": "Goa",

    # Veraval
    "वेरावल": "Veraval",
    "વેરાવળ": "Veraval",
    "வேராவல்": "Veraval",
    "వేరావల్": "Veraval",
    "ଭେରାଭାଲ": "Veraval",

    # Porbandar
    "पोरबंदर": "Porbandar",
    "પોરબંદર": "Porbandar",
    "போர்பந்தர்": "Porbandar",
    "పోర్బందర్": "Porbandar",

    # Tuticorin / Thoothukudi
    "तूतीकोरिन": "Tuticorin",
    "தூத்துக்குடி": "Tuticorin",
    "తూత్తుకుడి": "Tuticorin",
    "തൂത്തുക്കുടി": "Tuticorin",
    "ତୁତିକୋରିନ": "Tuticorin",
    "thoothukudi": "Tuticorin",

    # Kakinada
    "काकीनाडा": "Kakinada",
    "కాకినాడ": "Kakinada",
    "காக்கிநாடா": "Kakinada",
    "କାକିନାଡ଼ା": "Kakinada",

    # Haldia
    "हल्दिया": "Haldia",
    "হলদিয়া": "Haldia",
    "ஹால்டியா": "Haldia",
    "హల్దియా": "Haldia",
    "ହଳଦିଆ": "Haldia",

    # Kolkata
    "कोलकाता": "Kolkata",
    "কলকাতা": "Kolkata",
    "கொல்கத்தா": "Kolkata",
    "కోల్‌కతా": "Kolkata",
    "କୋଲକାତା": "Kolkata",
    "calcutta": "Kolkata",

    # Mangalore / Mangaluru
    "मंगलौर": "Mangalore",
    "मंगलोर": "Mangalore",
    "ಮಂಗಳೂರು": "Mangalore",
    "மங்களூர்": "Mangalore",
    "మంగళూరు": "Mangalore",
    "മംഗലാപുരം": "Mangalore",
    "mangaluru": "Mangalore",

    # Rameswaram
    "रामेश्वरम": "Rameswaram",
    "ராமேஸ்வரம்": "Rameswaram",
    "రామేశ్వరం": "Rameswaram",
    "രാമേശ്വരം": "Rameswaram",
}

_ROUTE_WORDS = (
    "route", "path", "way to", "how do i get", "navigate",
    "मार्ग", "रास्ता", "दूरी", "दिशा", "जाना",
    "பாதை", "வழி", "செல்ல",
    "దారి", "మార్గం", "వెళ్ళాలి",
    "ମାର୍ଗ", "ରାସ୍ତା", "ଯିବା",
    "পথ", "রাস্তা",
    "માર્ગ", "રસ્તો",
    "വഴി", "പാത",
    "ದಾರಿ", "ಮಾರ್ಗ",
)

_PASSAGE_WORDS = (
    "passage", "voyage", "sail to", "sail from", "crossing", "deliver", "cargo to", "bound for"
)

_SAFEST_ZONE_WORDS = (
    "safest", "safe zone", "where should i fish", "best place", "find a",
    "कहाँ मछली", "सुरक्षित जगह", "எங்கு மீன்", "సురక్షిత ప్రాంతం", "କେଉଁଠାରେ ମାଛ", "কোথায় মাছ"
)

_CURRENT_CONDITIONS_WORDS = (
    "safe to fish", "safe to go", "conditions", "weather", "wave", "wind", "is it safe",
    # Hindi / Marathi
    "मौसम", "सुरक्षित", "मछली", "हवा", "लहर", "लहरें", "तूफान", "चक्रवात", "बारिश", "कैसा है",
    # Tamil
    "பாதுகாப்பான", "வானிலை", "மீன்", "அலை", "காற்று", "புயல்", "மழை", "எப்படி",
    # Telugu
    "సురక్షిత", "వాతావరణం", "చేపలు", "అలలు", "గాలి", "తుఫాను", "వర్షం", "ఎలా ఉంది",
    # Odia
    "ସୁରକ୍ଷିତ", "ପାଣିପାଗ", "ମାଛ", "ଢେଉ", "ତରଙ୍ଗ", "ପବନ", "ବାତ୍ୟା", "ବର୍ଷା", "କିପରି",
    # Bengali
    "নিরাপদ", "আবহাওয়া", "মাছ", "ঢেউ", "বাতাস", "ঝড়", "বৃষ্টি", "কেমন",
    # Gujarati
    "સુરક્ષિત", "હવામાન", "માછલી", "મોજા", "પવન", "વાવાઝોડું", "વરસાદ",
    # Malayalam
    "സുരക്ഷിതം", "കാലാവസ്ഥ", "മത്സ്യം", "മീൻ", "തിരമാല", "കാറ്റ്", "ചുഴലിക്കാറ്റ്", "മഴ",
    # Kannada
    "ಸುರಕ್ಷಿತ", "ಹವಾಮಾನ", "ಮೀನು", "ಅಲೆಗಳು", "ಗಾಳಿ", "ಚಂಡಮಾರುತ", "ಮಳೆ",
)

_COORD_RE = re.compile(r"(-?\d{1,2}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)")
_RADIUS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:km|kms|kilometers?|kilometres?)\b", re.IGNORECASE)
_VESSEL_LEN_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:m|metre|meter)s?\s*(?:boat|vessel|yacht|ship)", re.IGNORECASE)

# "from X to Y" / "X to Y" — the origin/destination pair a passage needs.
_PLACES_ALT = "|".join(re.escape(p) for p in KNOWN_PLACES)
_FROM_TO_RE = re.compile(
    r"\bfrom\s+(?:the\s+)?(" + _PLACES_ALT + r")\b.*?\bto\s+(?:the\s+)?(" + _PLACES_ALT + r")\b",
    re.IGNORECASE | re.DOTALL,
)
_TO_RE = re.compile(r"\bto\s+(?:the\s+)?(" + _PLACES_ALT + r")\b", re.IGNORECASE)

_SORTED_ALIASES = sorted(CLASS_ALIASES.items(), key=lambda kv: -len(kv[0]))
_CLASS_KEY_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(VESSEL_CLASSES, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def _parse_vessel_class(lower: str) -> str | None:
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
    # 1. First check regional Indian script port names & aliases
    for alias, canon in PORT_ALIASES.items():
        if alias in message or alias.lower() in lower:
            location_name = canon
            break

    # 2. If not matched, fallback to English regex
    if not location_name:
        place_match = _PLACE_RE.search(message) or _PLACE_ANYWHERE_RE.search(message)
        if place_match:
            location_name = place_match.group(1) if place_match.re is _PLACE_RE else place_match.group(0)

    radius_match = _RADIUS_RE.search(message)
    radius_km = float(radius_match.group(1)) if radius_match else 40.0

    vessel_match = _VESSEL_LEN_RE.search(message)
    vessel_length_m = float(vessel_match.group(1)) if vessel_match else 8.0

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
