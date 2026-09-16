"""
Vessel-class registry + class-aware risk.

The point of these tests is the thing that was structurally impossible
before the registry existed: the SAME conditions must produce DIFFERENT,
correct verdicts for a fishing boat, a sailing yacht and a cargo ship. A
regression here doesn't look like a crash — it looks like a container ship
being told a 2m sea is dangerous, or a yacht being told a flat calm is
perfect, which is exactly the kind of quietly-wrong answer this project
treats as worse than no answer.
"""
import pytest

from app.agents.risk_agent import (
    _angular_difference_deg,
    assess_risk,
    check_hard_constraints,
    required_under_keel_m,
    squat_m,
)
from app.agents.vessel_profiles import (
    CLASS_ALIASES,
    DEFAULT_VESSEL_CLASS,
    VESSEL_CLASSES,
    classes_for_group,
    resolve_vessel,
)
from app.models.schemas import GeoState, OceanState, WeatherState


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

def test_every_alias_points_at_a_real_class():
    for alias, key in CLASS_ALIASES.items():
        assert key in VESSEL_CLASSES, f"alias '{alias}' points at unknown class '{key}'"


def test_every_class_key_matches_its_own_vessel_class_field():
    # The key is what the API, parser and frontend all speak — a mismatch
    # would make a round-tripped selection silently resolve to something else.
    for key, profile in VESSEL_CLASSES.items():
        assert profile.vessel_class == key


def test_unknown_class_falls_back_to_documented_default_not_an_error():
    vessel = resolve_vessel("interstellar_barge")
    assert vessel.vessel_class == DEFAULT_VESSEL_CLASS


def test_aliases_resolve():
    assert resolve_vessel("yacht").vessel_class == "sailing_yacht"
    assert resolve_vessel("tanker").vessel_class == "tanker"
    assert resolve_vessel("Cargo Ship").vessel_class == "general_cargo"
    assert resolve_vessel("bulk-carrier").vessel_class == "bulk_carrier"


def test_length_override_does_not_reshape_the_class():
    # Stating a length must not silently invent a draft or a wave threshold.
    base = VESSEL_CLASSES["sailing_yacht"]
    vessel = resolve_vessel("sailing_yacht", length_m=15.0)
    assert vessel.length_m == 15.0
    assert vessel.draft_m == base.draft_m
    assert vessel.max_safe_wave_m == base.max_safe_wave_m


def test_only_sailing_classes_carry_sail_fields():
    for profile in VESSEL_CLASSES.values():
        if profile.propulsion == "motor":
            assert profile.min_working_wind_ms is None
            assert profile.no_go_angle_deg is None
        else:
            assert profile.min_working_wind_ms is not None
            assert profile.no_go_angle_deg is not None


def test_all_three_user_groups_have_classes():
    for group in ("fisherman", "sailor", "trader"):
        assert classes_for_group(group), f"no vessel classes for {group}"


# --------------------------------------------------------------------------
# Depth: squat and under-keel clearance
# --------------------------------------------------------------------------

def test_squat_is_negligible_for_a_small_boat_and_material_for_a_bulker():
    small = squat_m(resolve_vessel("fishing_small"))
    bulker = squat_m(resolve_vessel("bulk_carrier"))
    assert small < 0.3
    assert bulker > 1.0
    assert bulker > small


def test_commercial_vessels_get_proportional_under_keel_clearance():
    tanker = resolve_vessel("tanker")
    small = resolve_vessel("fishing_small")
    # 10% of a 14m draft is a much bigger absolute margin than the
    # small-boat fixed 1m — that asymmetry is the whole point.
    assert required_under_keel_m(tanker) > required_under_keel_m(small)


def test_depth_that_is_fine_for_a_fishing_boat_vetoes_a_tanker():
    ocean = OceanState(significant_wave_height_m=0.5)
    weather = WeatherState(wind_speed_ms=4.0)
    geo = GeoState(depth_m=6.0, nearest_port_distance_km=10.0)

    fishing = check_hard_constraints(weather, ocean, geo, resolve_vessel("fishing_small"))
    tanker = check_hard_constraints(weather, ocean, geo, resolve_vessel("tanker"))

    assert not fishing.vetoed
    assert tanker.vetoed
    assert any("grounding" in r for r in tanker.reasons)


def test_falling_tide_is_subtracted_from_charted_depth():
    weather = WeatherState(wind_speed_ms=4.0)
    # coastal_trader: 3.5m draft + 0.58m squat + 0.6m margin = 4.7m needed.
    geo = GeoState(depth_m=5.4, nearest_port_distance_km=10.0)
    trader = resolve_vessel("coastal_trader")

    slack = check_hard_constraints(weather, OceanState(), geo, trader)
    low_water = check_hard_constraints(weather, OceanState(tide_height_m=-1.2), geo, trader)

    # Same seabed, different water over it — and the low-water case must be
    # the one that gets vetoed, not the other way round.
    assert not slack.vetoed
    assert low_water.vetoed


def test_tide_is_never_assumed_when_absent():
    # No tide value must behave as "charted depth only", never as a helpful
    # positive assumption.
    geo = GeoState(depth_m=5.4, nearest_port_distance_km=10.0)
    trader = resolve_vessel("coastal_trader")
    no_tide = check_hard_constraints(WeatherState(), OceanState(), geo, trader)
    high_tide = check_hard_constraints(WeatherState(), OceanState(tide_height_m=1.5), geo, trader)
    assert not no_tide.vetoed
    assert not high_tide.vetoed


# --------------------------------------------------------------------------
# The same sea, three vessels
# --------------------------------------------------------------------------

def _moderate_sea():
    return (
        WeatherState(wind_speed_ms=11.0, wind_gust_ms=14.0, wind_direction_deg=180.0),
        OceanState(significant_wave_height_m=3.2),
        GeoState(depth_m=60.0, nearest_port_distance_km=30.0),
    )


def test_same_sea_is_a_veto_for_a_small_boat_and_routine_for_a_cargo_ship():
    weather, ocean, geo = _moderate_sea()

    small = assess_risk(weather, ocean, geo, resolve_vessel("fishing_small"))
    cargo = assess_risk(weather, ocean, geo, resolve_vessel("general_cargo"))

    # 3.2m is >2x an 8m open boat's 1.5m threshold — the capsize veto.
    assert small.risk_level == "REJECTED"
    # The same sea against a general cargo ship's 6m threshold is unremarkable.
    assert cargo.risk_level in ("LOW", "MODERATE")
    assert cargo.risk_score < 50


# --------------------------------------------------------------------------
# Sail: wind as a resource, not only a hazard
# --------------------------------------------------------------------------

def test_flat_calm_penalises_a_sailing_yacht_and_not_a_motor_boat():
    weather = WeatherState(wind_speed_ms=0.8, wind_gust_ms=1.2, wind_direction_deg=90.0)
    ocean = OceanState(significant_wave_height_m=0.3)
    geo = GeoState(depth_m=40.0, nearest_port_distance_km=15.0)

    yacht = assess_risk(weather, ocean, geo, resolve_vessel("sailing_yacht"))
    trawler = assess_risk(weather, ocean, geo, resolve_vessel("fishing_mechanized"))

    assert yacht.factor_breakdown["becalmed"] > 0
    assert trawler.factor_breakdown["becalmed"] == 0
    assert yacht.risk_score > trawler.risk_score
    assert any("becalmed" in line.lower() for line in yacht.explanation)


def test_auxiliary_engine_halves_the_becalmed_penalty():
    weather = WeatherState(wind_speed_ms=0.5, wind_direction_deg=90.0)
    ocean = OceanState(significant_wave_height_m=0.3)
    geo = GeoState(depth_m=40.0, nearest_port_distance_km=15.0)

    pure_sail = assess_risk(weather, ocean, geo, resolve_vessel("sailing_yacht"))
    with_engine = assess_risk(weather, ocean, geo, resolve_vessel("sailing_yacht_aux"))

    assert pure_sail.factor_breakdown["becalmed"] > with_engine.factor_breakdown["becalmed"] > 0


def test_becalmed_is_never_a_veto():
    # Being becalmed is delaying and uncomfortable, not fatal — it must rank,
    # never reject, or the planner would refuse to route a yacht in light airs.
    weather = WeatherState(wind_speed_ms=0.0, wind_direction_deg=90.0)
    ocean = OceanState(significant_wave_height_m=0.2)
    geo = GeoState(depth_m=40.0, nearest_port_distance_km=15.0)
    yacht = assess_risk(weather, ocean, geo, resolve_vessel("sailing_yacht"))
    assert yacht.risk_level != "REJECTED"


def test_point_of_sail_only_applies_when_a_course_is_known():
    weather = WeatherState(wind_speed_ms=8.0, wind_direction_deg=0.0)
    ocean = OceanState(significant_wave_height_m=1.0)
    geo = GeoState(depth_m=40.0, nearest_port_distance_km=15.0)
    yacht = resolve_vessel("sailing_yacht")

    no_course = assess_risk(weather, ocean, geo, yacht)
    assert no_course.factor_breakdown["point_of_sail"] == 0


def test_sailing_into_the_wind_costs_more_than_sailing_across_it():
    weather = WeatherState(wind_speed_ms=8.0, wind_direction_deg=0.0)  # wind FROM the north
    ocean = OceanState(significant_wave_height_m=1.0)
    geo = GeoState(depth_m=40.0, nearest_port_distance_km=15.0)
    yacht = resolve_vessel("sailing_yacht")

    dead_upwind = assess_risk(weather, ocean, geo, yacht, course_bearing_deg=0.0)
    beam_reach = assess_risk(weather, ocean, geo, yacht, course_bearing_deg=90.0)
    dead_downwind = assess_risk(weather, ocean, geo, yacht, course_bearing_deg=180.0)

    assert dead_upwind.factor_breakdown["point_of_sail"] == 14
    assert beam_reach.factor_breakdown["point_of_sail"] == 0  # the ideal point of sail
    assert 0 < dead_downwind.factor_breakdown["point_of_sail"] < 14  # gybe risk, but sailable


def test_point_of_sail_never_applies_to_a_motor_vessel():
    weather = WeatherState(wind_speed_ms=8.0, wind_direction_deg=0.0)
    ocean = OceanState(significant_wave_height_m=1.0)
    geo = GeoState(depth_m=60.0, nearest_port_distance_km=15.0)
    cargo = resolve_vessel("general_cargo")
    # A ship under power does not care which way the wind is relative to
    # its head — scoring it as though it did would be inventing a hazard.
    assert assess_risk(weather, ocean, geo, cargo, course_bearing_deg=0.0).factor_breakdown["point_of_sail"] == 0


@pytest.mark.parametrize(
    "a,b,expected",
    [(0.0, 0.0, 0.0), (0.0, 350.0, 10.0), (350.0, 0.0, 10.0), (90.0, 270.0, 180.0), (10.0, 200.0, 170.0)],
)
def test_angular_difference_wraps_correctly(a, b, expected):
    assert _angular_difference_deg(a, b) == pytest.approx(expected)


# --------------------------------------------------------------------------
# Backwards compatibility — the fisherman path must be untouched
# --------------------------------------------------------------------------

def test_default_vessel_is_still_the_original_eight_metre_boat():
    vessel = resolve_vessel()
    assert vessel.length_m == 8.0
    assert vessel.draft_m == 0.6
    assert vessel.max_safe_wave_m == 1.5
    assert vessel.wind_threshold_ms == 12.0
    assert vessel.operational_range_km == 40.0
