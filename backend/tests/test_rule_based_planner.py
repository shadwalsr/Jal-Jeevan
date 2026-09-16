"""
Tests for the LLM-free fallback path (app/planner/rule_based.py) — pure
logic, no network, no LLM, runs in milliseconds. This is what the planner
falls back to whenever Groq isn't configured or a live call fails, so it
needs to be trustworthy on its own, not just "good enough as a fallback."
"""
from app.planner.rule_based import parse_intent_rule_based, synthesize_answer_rule_based


class TestIntentParsing:
    def test_safety_question_with_location_and_radius(self):
        intent = parse_intent_rule_based("is it safe to fish 20km from Visakhapatnam?")
        assert intent["intent_type"] == "current_conditions"
        assert intent["location_name"] == "Visakhapatnam"
        assert intent["radius_km"] == 20.0

    def test_safest_zone_request(self):
        intent = parse_intent_rule_based("where should I fish near Puri?")
        assert intent["intent_type"] == "safest_zone"
        assert intent["location_name"] == "Puri"

    def test_route_request(self):
        intent = parse_intent_rule_based("what's the safest route from Kochi?")
        assert intent["intent_type"] == "route"
        assert intent["location_name"] == "Kochi"

    def test_explicit_coordinates(self):
        intent = parse_intent_rule_based("conditions at 17.65, 83.35")
        assert intent["lat"] == 17.65
        assert intent["lon"] == 83.35

    def test_vessel_length_extracted(self):
        intent = parse_intent_rule_based("is it safe for a 5 metre boat near Chennai?")
        assert intent["vessel_length_m"] == 5.0

    def test_defaults_when_nothing_specified(self):
        intent = parse_intent_rule_based("hello")
        assert intent["intent_type"] == "general"
        assert intent["location_name"] is None
        assert intent["radius_km"] == 40.0
        assert intent["vessel_length_m"] == 8.0

    def test_no_location_named_returns_none_not_a_guess(self):
        intent = parse_intent_rule_based("is it safe to fish 20 kms from the port?")
        assert intent["location_name"] is None  # "the port" isn't a known place — must not fabricate one


class TestAnswerSynthesis:
    def test_empty_evidence_gives_honest_message(self):
        answer = synthesize_answer_rule_based({})
        assert "don't have enough information" in answer

    def test_renders_risk_and_factors(self):
        evidence = {
            "recommendation_summary": "MODERATE risk (29/100)",
            "risk_level": "MODERATE",
            "risk_score": 29,
            "factor_lines": ["Wave height 1.78m vs safe threshold 1.5m -> +21"],
            "sources_used": ["Open-Meteo Marine"],
            "data_freshness": {"Open-Meteo Marine": "2026-08-26T10:00:00Z"},
        }
        answer = synthesize_answer_rule_based(evidence)
        assert "MODERATE" in answer
        assert "29/100" in answer
        assert "Wave height 1.78m" in answer
        assert "Open-Meteo Marine" in answer

    def test_never_invents_a_value_not_in_evidence(self):
        # The whole point of this path: it can only ever repeat fields that
        # are literally present in the receipt, never generate new text.
        evidence = {"risk_level": "LOW", "risk_score": 10}
        answer = synthesize_answer_rule_based(evidence)
        assert "LOW" in answer and "10/100" in answer
        # no fabricated wave/wind claims when factor_lines is absent
        assert "wave" not in answer.lower()

    def test_surfaces_exact_coordinates_and_maps_link_when_present(self):
        # Real bug (26 Aug 2026): a "safest zone" answer told a user "20km
        # at bearing 45 deg" with no way to find it without doing that
        # trig themselves — the receipt never carried the actual lat/lon.
        # Once evidence_agent.py adds them, this renderer must show them.
        evidence = {
            "recommendation_summary": "Safest zone: 20.0km at bearing 45 deg",
            "risk_level": "LOW",
            "risk_score": 18,
            "location_lat": 17.83,
            "location_lon": 83.42,
            "location_maps_url": "https://www.google.com/maps/search/?api=1&query=17.83,83.42",
        }
        answer = synthesize_answer_rule_based(evidence)
        assert "17.83" in answer and "83.42" in answer
        assert "https://www.google.com/maps/search/?api=1&query=17.83,83.42" in answer

    def test_no_coordinates_line_when_location_missing(self):
        evidence = {"risk_level": "LOW", "risk_score": 10}
        answer = synthesize_answer_rule_based(evidence)
        assert "Coordinates:" not in answer
        assert "Google Maps" not in answer


class TestVesselClassAndPassageParsing:
    """
    Sailor/trader coverage for the LLM-free parser. This path has to be
    trustworthy on its own merits, not just as a backup (CLAUDE.md's
    convention for rule_based.py): if the Groq quota is out, this is what
    decides whether a trader asking about a tanker gets scored as a tanker
    or, silently, as an 8m fishing boat.
    """

    def test_vessel_class_extracted_from_plain_language(self):
        assert parse_intent_rule_based("is it safe in my yacht")["vessel_class"] == "sailing_yacht"
        assert parse_intent_rule_based("conditions for a trawler")["vessel_class"] == "fishing_mechanized"
        assert parse_intent_rule_based("taking the tanker out")["vessel_class"] == "tanker"
        assert parse_intent_rule_based("my dhow is loaded")["vessel_class"] == "dhow"

    def test_longer_alias_wins_over_a_shorter_one_it_contains(self):
        # "bulk carrier" must not be parsed as "bulk"-then-something-else,
        # and "sailing boat" must not collapse to bare "sail".
        assert parse_intent_rule_based("a bulk carrier from Kandla")["vessel_class"] == "bulk_carrier"
        assert parse_intent_rule_based("a container ship at Mumbai")["vessel_class"] == "container_ship"

    def test_exact_registry_key_round_trips(self):
        # The frontend and API hand back exact class keys; those must parse
        # to themselves, not fall through the alias table to something else.
        for key in ("sailing_yacht", "coastal_trader", "passenger_ferry", "general_cargo"):
            assert parse_intent_rule_based(f"check {key} conditions")["vessel_class"] == key

    def test_no_vessel_mentioned_returns_none_not_a_guess(self):
        # None means "the caller should use the documented default" — this
        # function must not invent a vessel the user never mentioned.
        assert parse_intent_rule_based("is it safe to fish near Puri")["vessel_class"] is None

    def test_from_to_gives_both_endpoints(self):
        intent = parse_intent_rule_based("sail from Kochi to Tuticorin")
        assert intent["intent_type"] == "passage"
        assert intent["origin_name"] == "Kochi"
        assert intent["destination_name"] == "Tuticorin"

    def test_bare_destination_is_still_a_passage(self):
        intent = parse_intent_rule_based("Kochi to Kollam")
        assert intent["intent_type"] == "passage"
        assert intent["destination_name"] == "Kollam"

    def test_origin_becomes_the_resolved_location_not_the_destination(self):
        # The location the marine agents query must be where the vessel IS,
        # not where it's going — getting this backwards would report the
        # destination's weather as the departure conditions.
        intent = parse_intent_rule_based("take my cargo ship from Chennai to Visakhapatnam")
        assert intent["location_name"] == "Chennai"
        assert intent["destination_name"] == "Visakhapatnam"

    def test_fisherman_queries_are_not_reclassified_as_passages(self):
        # The regression that would matter most: the original user group
        # must keep getting the radial search, not a port-to-port plan.
        for message in (
            "is it safe to fish near Puri",
            "find the safest fishing zone within 30km",
            "what are the conditions off Visakhapatnam",
        ):
            assert parse_intent_rule_based(message)["intent_type"] != "passage"

    def test_passage_keywords_work_without_a_named_destination(self):
        assert parse_intent_rule_based("planning a voyage next week")["intent_type"] == "passage"

    def test_unknown_place_is_not_invented_as_a_destination(self):
        # Only ports with real harbour-entrance coordinates can be planned
        # to; matching an unknown name would just defer the failure.
        intent = parse_intent_rule_based("sail to Atlantis")
        assert intent["destination_name"] is None
