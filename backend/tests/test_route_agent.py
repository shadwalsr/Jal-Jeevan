"""
Tests for app/agents/route_agent.py's candidate-scan hard-constraint check.

Real bug (26 Aug 2026): _score_point (the fast Open-Meteo-only scoring used
by find_safest_zone's 16-candidate scan) built its GeoState without ever
calling the bathymetry adapter — depth_m stayed None and is_land stayed its
default False for every candidate, no matter what. check_hard_constraints
can only veto on-land/insufficient-depth points using those two fields, so
the fast scan could never catch a candidate that was actually on land; it
would score as ordinary LOW/MODERATE risk instead of REJECTED. The "detailed
recheck on the winner" sometimes caught it after the fact, but
find_safest_zone still returned found_safe_zone=True with the destination's
STALE fast-scan score, not the verified one — confirmed live with a query
whose fast-scan winner was an on-land point 7.5km due west of Visakhapatnam
that the full recheck immediately rejected.

These mock out the network/DB calls (Open-Meteo, MPA lookup) so the test is
fast and deterministic, and only fake bathymetry — the one piece of real
plumbing this bug was about.
"""
import pytest

from app.agents import route_agent
from app.models.schemas import VesselProfile


@pytest.fixture
def vessel():
    return VesselProfile()


def _ok(**overrides):
    base = {"status": "success"}
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_score_point_vetoes_a_point_the_bathymetry_adapter_says_is_land(vessel, monkeypatch):
    async def fake_marine_forecast(lat, lon, hour_offset=0):
        return _ok(wave_height_m=0.5, wave_period_s=6.0)

    async def fake_weather_forecast(lat, lon, hour_offset=0):
        return _ok(wind_speed_ms=2.0, wind_gust_ms=3.0, wind_direction_deg=180.0)

    async def fake_check_mpa(lat, lon):
        return _ok(inside_mpa=False)

    async def fake_get_depth(lat, lon):
        return _ok(depth_m=0.0, is_land=True)

    monkeypatch.setattr(route_agent.open_meteo_adapter, "get_marine_forecast", fake_marine_forecast)
    monkeypatch.setattr(route_agent.open_meteo_adapter, "get_weather_forecast", fake_weather_forecast)
    monkeypatch.setattr(route_agent, "check_mpa", fake_check_mpa)
    monkeypatch.setattr(route_agent, "get_depth", fake_get_depth)

    risk = await route_agent._score_point(10.0, 80.0, vessel, distance_from_origin_km=5.0)

    assert risk.risk_level == "REJECTED"
    assert risk.hard_constraints.vetoed is True
    assert any("land" in r.lower() for r in risk.hard_constraints.reasons)


@pytest.mark.asyncio
async def test_score_point_scores_normally_when_bathymetry_says_water(vessel, monkeypatch):
    async def fake_marine_forecast(lat, lon, hour_offset=0):
        return _ok(wave_height_m=0.5, wave_period_s=6.0)

    async def fake_weather_forecast(lat, lon, hour_offset=0):
        return _ok(wind_speed_ms=2.0, wind_gust_ms=3.0, wind_direction_deg=180.0)

    async def fake_check_mpa(lat, lon):
        return _ok(inside_mpa=False)

    async def fake_get_depth(lat, lon):
        return _ok(depth_m=40.0, is_land=False)

    monkeypatch.setattr(route_agent.open_meteo_adapter, "get_marine_forecast", fake_marine_forecast)
    monkeypatch.setattr(route_agent.open_meteo_adapter, "get_weather_forecast", fake_weather_forecast)
    monkeypatch.setattr(route_agent, "check_mpa", fake_check_mpa)
    monkeypatch.setattr(route_agent, "get_depth", fake_get_depth)

    risk = await route_agent._score_point(10.0, 80.0, vessel, distance_from_origin_km=5.0)

    assert risk.risk_level != "REJECTED"
    assert risk.hard_constraints.vetoed is False


# ---------------------------------------------------------------------------
# Range-expansion timing bound.
#
# Real bug (28 Aug 2026): when find_safest_zone gained the ability to reach
# past the requested range rather than dead-ending, the rings were walked
# SEQUENTIALLY — each one paying a full scan-plus-verify round (~25s cold on
# Copernicus). Up to 7 rings meant ~175s, which blew /chat's 115s ceiling and
# returned `504 The request took too long to process` instead of an answer.
#
# The fix fans every expansion ring out into ONE concurrent fast scan and caps
# full-detail verification per PHASE rather than per ring, so at most two
# phases (and 6 verifications) ever run no matter how far the search reaches.
# These lock that bound in: the cost that matters is verification rounds, and
# there must never be more than two.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expansion_runs_at_most_two_verification_phases(vessel, monkeypatch):
    """Nothing verifiable anywhere — the pathological case that caused the 504."""
    phases = []

    async def fake_score_candidate(plat, plon, dist, bearing, v):
        from app.models.schemas import RouteCandidate
        return RouteCandidate(lat=plat, lon=plon, distance_from_origin_km=round(dist, 1),
                              bearing_deg=bearing, risk_score=10, risk_level="LOW",
                              rejected=False, rejection_reason=None)

    async def fake_verify_best(cands, v):
        phases.append(len(cands))
        return None, None, None, None, None, ["rejected on full detail"]

    monkeypatch.setattr(route_agent, "_score_candidate", fake_score_candidate)
    monkeypatch.setattr(route_agent, "_verify_best", fake_verify_best)

    result = await route_agent.find_safest_zone(17.65, 83.35, 40.0, vessel)

    assert len(phases) <= 2, f"expansion must not verify per-ring; got {len(phases)} phases"
    assert result.found_safe_zone is False


@pytest.mark.asyncio
async def test_expansion_returns_nearest_zone_beyond_requested_range(vessel, monkeypatch):
    """Nothing inside 40km, something at 72km: answer with it, flagged as over range."""
    async def fake_score_candidate(plat, plon, dist, bearing, v):
        from app.models.schemas import RouteCandidate
        inside = dist <= 40.0
        return RouteCandidate(lat=plat, lon=plon, distance_from_origin_km=round(dist, 1),
                              bearing_deg=bearing, risk_score=10, risk_level="LOW",
                              rejected=inside,
                              rejection_reason="on land" if inside else None)

    async def fake_verify_best(cands, v):
        from app.models.schemas import RiskAssessment, HardConstraintResult
        c = cands[0]
        risk = RiskAssessment(risk_score=12, risk_level="LOW", factor_breakdown={},
                              explanation=[],
                              hard_constraints=HardConstraintResult(vetoed=False, reasons=[]))
        return c, risk, None, None, None, []

    async def fake_score_point(plat, plon, v, **kw):
        from app.models.schemas import RiskAssessment, HardConstraintResult
        return RiskAssessment(risk_score=12, risk_level="LOW", factor_breakdown={},
                              explanation=[],
                              hard_constraints=HardConstraintResult(vetoed=False, reasons=[]))

    monkeypatch.setattr(route_agent, "_score_candidate", fake_score_candidate)
    monkeypatch.setattr(route_agent, "_verify_best", fake_verify_best)
    monkeypatch.setattr(route_agent, "_score_point", fake_score_point)

    result = await route_agent.find_safest_zone(17.65, 83.35, 40.0, vessel)

    assert result.found_safe_zone is True
    assert result.exceeded_requested_range is True
    assert result.requested_range_km == 40.0
    assert result.distance_km > 40.0
    # the nearest expansion ring wins, not the farthest
    assert result.distance_km < 140.0
    assert "exceeds your requested" in result.recommendation
