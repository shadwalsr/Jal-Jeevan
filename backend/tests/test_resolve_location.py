"""
Tests for app/planner/graph.py's resolve_location node — specifically the
priority order between a place named in the message, conversation memory,
and the browser's own geolocation (client_lat/client_lon).

Real feature (26 Aug 2026): "where can I go to fish?" has no place name at
all — without a fallback, that question was unanswerable except by asking
the user to somehow supply coordinates themselves. client_lat/client_lon
(sent by the frontend from navigator.geolocation, when granted) fixes that,
but must be the LAST resort: a named place, or a place already established
earlier in the same conversation, must still win over "where I happen to
be right now" — someone asking about a place a friend is at, or continuing
a conversation about a specific spot, shouldn't get silently redirected to
their own live position.
"""
import pytest

from app.planner import graph


@pytest.mark.asyncio
async def test_uses_client_location_when_nothing_else_resolves(monkeypatch):
    async def fake_get_last_location(session_id):
        return None

    monkeypatch.setattr(graph, "get_last_location", fake_get_last_location)

    state = {
        "user_message": "where can I go to fish?",
        "session_id": "s1",
        "intent": {"intent_type": "safest_zone", "lat": None, "lon": None, "location_name": None},
        "client_lat": 17.65,
        "client_lon": 83.35,
        "trace": [],
    }
    result = await graph.resolve_location(state)

    assert result["lat"] == 17.65
    assert result["lon"] == 83.35
    assert any("browser" in line.lower() for line in result["trace"])


@pytest.mark.asyncio
async def test_named_place_wins_over_client_location(monkeypatch):
    async def fake_geocode(place_name):
        return {"status": "success", "lat": 13.08, "lon": 80.27, "display_name": "Chennai"}

    monkeypatch.setattr(graph, "geocode", fake_geocode)

    state = {
        "user_message": "is it safe near Chennai?",
        "session_id": "s2",
        "intent": {"intent_type": "current_conditions", "lat": None, "lon": None, "location_name": "Chennai"},
        "client_lat": 17.65,  # user is physically elsewhere — must not override the named place
        "client_lon": 83.35,
        "trace": [],
    }
    result = await graph.resolve_location(state)

    assert result["lat"] == 13.08
    assert result["lon"] == 80.27


@pytest.mark.asyncio
async def test_session_memory_wins_over_client_location(monkeypatch):
    async def fake_get_last_location(session_id):
        return {"lat": 20.0, "lon": 85.0, "location_name": "Puri", "from_message": "is it safe near Puri?"}

    monkeypatch.setattr(graph, "get_last_location", fake_get_last_location)

    state = {
        "user_message": "what about tomorrow?",
        "session_id": "s3",
        "intent": {"intent_type": "current_conditions", "lat": None, "lon": None, "location_name": None},
        "client_lat": 17.65,
        "client_lon": 83.35,
        "trace": [],
    }
    result = await graph.resolve_location(state)

    assert result["lat"] == 20.0
    assert result["lon"] == 85.0


@pytest.mark.asyncio
async def test_no_location_at_all_when_nothing_resolves(monkeypatch):
    async def fake_get_last_location(session_id):
        return None

    monkeypatch.setattr(graph, "get_last_location", fake_get_last_location)

    state = {
        "user_message": "where can I go to fish?",
        "session_id": "s4",
        "intent": {"intent_type": "safest_zone", "lat": None, "lon": None, "location_name": None},
        "client_lat": None,
        "client_lon": None,
        "trace": [],
    }
    result = await graph.resolve_location(state)

    assert result["lat"] is None
    assert result["lon"] is None
