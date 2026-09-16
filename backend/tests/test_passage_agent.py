"""
Passage Agent — the deterministic geometry and corridor-sizing underneath
port-to-port planning. No network, no DB: `plan_passage` itself needs live
sources, but everything it computes with is pure and must be provably right,
because an ETA or a bearing that is quietly wrong is worse than one that is
obviously missing.
"""
import pytest

from app.agents.passage_agent import (
    KM_PER_NM,
    MAX_CELLS,
    _plan_corridor,
    _resolution_for,
    _sailed_distance_from_verdict,
    haversine_km,
    initial_bearing_deg,
)
from app.agents.vessel_profiles import resolve_vessel
from app.models.schemas import RiskAssessment

# Harbour entrances from infra/sql/002_ports_seed.sql.
KOCHI = (9.9312, 76.2673)
TUTICORIN = (8.7642, 78.1348)
CHENNAI = (13.0827, 80.2907)
VIZAG = (17.6868, 83.2185)


def test_haversine_matches_a_known_distance():
    # Kochi (9.9312, 76.2673) to Tuticorin (8.7642, 78.1348) is ~242km great
    # circle — cross-checked against the equirectangular approximation at
    # this latitude (129.7km north-south, 204.9km east-west -> 242.5km).
    km = haversine_km(*KOCHI, *TUTICORIN)
    assert 235 < km < 250


def test_haversine_is_symmetric_and_zero_on_itself():
    assert haversine_km(*KOCHI, *KOCHI) == pytest.approx(0.0)
    assert haversine_km(*KOCHI, *VIZAG) == pytest.approx(haversine_km(*VIZAG, *KOCHI))


def test_bearing_cardinal_directions():
    assert initial_bearing_deg(0.0, 0.0, 10.0, 0.0) == pytest.approx(0.0, abs=0.5)      # north
    assert initial_bearing_deg(0.0, 0.0, 0.0, 10.0) == pytest.approx(90.0, abs=0.5)     # east
    assert initial_bearing_deg(0.0, 0.0, -10.0, 0.0) == pytest.approx(180.0, abs=0.5)   # south
    assert initial_bearing_deg(0.0, 0.0, 0.0, -10.0) == pytest.approx(270.0, abs=0.5)   # west


def test_bearing_is_always_a_compass_bearing():
    for a, b in ((KOCHI, VIZAG), (VIZAG, KOCHI), (CHENNAI, TUTICORIN)):
        assert 0.0 <= initial_bearing_deg(*a, *b) < 360.0


def test_resolution_coarsens_with_distance():
    # Finer cells on a coastal hop, coarser on an ocean crossing — the
    # budget control that stops a long passage becoming hundreds of live
    # source calls.
    assert _resolution_for(50.0) == 5
    assert _resolution_for(300.0) == 4
    assert _resolution_for(2000.0) == 3
    assert _resolution_for(120.0) >= _resolution_for(600.0)


@pytest.mark.parametrize(
    "origin,destination",
    [(KOCHI, TUTICORIN), (KOCHI, VIZAG), (CHENNAI, VIZAG), (VIZAG, KOCHI)],
)
def test_corridor_always_stays_inside_the_cell_budget(origin, destination):
    # This is the guard that keeps a passage request from silently taking
    # minutes — every real port pair must come back under the ceiling.
    distance = haversine_km(*origin, *destination)
    resolution, rings, o, d, cells = _plan_corridor(
        _resolution_for(distance), *origin, *destination
    )
    assert len(cells) <= MAX_CELLS
    assert rings >= 1
    assert o in cells and d in cells


def test_corridor_contains_both_endpoints_even_for_a_very_short_hop():
    resolution, rings, o, d, cells = _plan_corridor(5, 9.9312, 76.2673, 9.9500, 76.2000)
    assert o in cells
    assert d in cells


def _risk(point_of_sail: int) -> RiskAssessment:
    return RiskAssessment(
        risk_score=10,
        risk_level="LOW",
        factor_breakdown={"point_of_sail": point_of_sail},
        explanation=[],
    )


def test_upwind_leg_costs_extra_distance():
    direct, tack = _sailed_distance_from_verdict(100.0, _risk(14))
    assert tack is True
    assert direct > 100.0


def test_reaching_leg_costs_nothing_extra():
    distance, tack = _sailed_distance_from_verdict(100.0, _risk(0))
    assert tack is False
    assert distance == 100.0


def test_a_motor_vessel_never_pays_a_tacking_penalty():
    # A motor vessel's RiskAssessment has no point_of_sail entry at all —
    # the lookup must default to "no tacking", not raise.
    risk = RiskAssessment(risk_score=10, risk_level="LOW", factor_breakdown={}, explanation=[])
    distance, tack = _sailed_distance_from_verdict(100.0, risk)
    assert (distance, tack) == (100.0, False)


def test_nautical_mile_conversion_is_the_real_one():
    assert KM_PER_NM == pytest.approx(1.852)


def test_eta_arithmetic_is_consistent_for_a_representative_passage():
    # Not testing plan_passage (needs live sources) — testing that the
    # numbers it composes an ETA from agree with each other, since a wrong
    # ETA is the failure a trader would actually act on.
    km = haversine_km(*KOCHI, *TUTICORIN)
    nm = km / KM_PER_NM
    trader = resolve_vessel("coastal_trader")  # 9 kn
    hours = nm / trader.cruise_speed_kn
    assert 12 < hours < 18  # ~131nm at 9kn is a bit over half a day
