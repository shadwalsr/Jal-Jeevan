"""
Tests for the Risk Agent's two-stage decision pipeline — the single most
critical piece of logic in the system (a bug here means a wrong safety
recommendation reaches a fisherman). No network needed: risk_agent.py is
pure deterministic logic over already-fetched state, so these are fast
unit tests, not integration tests.

Every case here corresponds to a real bug found and fixed during
development (26 Aug 2026) — see risk_agent.py's module docstring. These
tests exist specifically so that bug can't silently come back.
"""
import pytest

from app.agents.risk_agent import assess_risk, check_hard_constraints
from app.models.schemas import GeoState, OceanState, VesselProfile, WeatherState


@pytest.fixture
def vessel():
    return VesselProfile()  # 8m boat, 1.5m safe wave, 0.6m draft, 40km range


@pytest.fixture
def calm_weather():
    return WeatherState(wind_speed_ms=2.0, wind_gust_ms=3.0)


@pytest.fixture
def calm_ocean():
    return OceanState(significant_wave_height_m=0.3)


class TestHardConstraintVeto:
    """The core bug this whole file exists to prevent: a candidate with
    excellent conditions but a legal/safety violation must be REJECTED,
    never scored as low-risk."""

    def test_mpa_violation_vetoes_regardless_of_conditions(self, calm_weather, calm_ocean, vessel):
        geo = GeoState(inside_mpa=True, mpa_name="Test MPA", nearest_port_distance_km=5.0)
        result = assess_risk(calm_weather, calm_ocean, geo, vessel)
        assert result.risk_level == "REJECTED"
        assert result.hard_constraints.vetoed is True
        assert "MPA" in result.hard_constraints.reasons[0] or "Test MPA" in result.hard_constraints.reasons[0]
        # A vetoed candidate must not carry a soft score — the whole point
        # of the two-stage design is that Stage 2 never runs on a reject.
        assert result.factor_breakdown == {}

    def test_same_conditions_clear_water_scores_normally(self, calm_weather, calm_ocean, vessel):
        geo = GeoState(inside_mpa=False, nearest_port_distance_km=5.0, depth_m=50.0)
        result = assess_risk(calm_weather, calm_ocean, geo, vessel)
        assert result.risk_level != "REJECTED"
        assert result.hard_constraints.vetoed is False
        assert result.risk_score < 25  # LOW, since conditions are genuinely calm

    def test_certain_capsize_wave_height_vetoes(self, calm_weather, vessel):
        # 2x+ the vessel's stated safe wave threshold -> not survivable, not just risky
        ocean = OceanState(significant_wave_height_m=3.5)  # vessel default max_safe_wave_m=1.5
        geo = GeoState(inside_mpa=False, nearest_port_distance_km=5.0, depth_m=50.0)
        result = assess_risk(calm_weather, ocean, geo, vessel)
        assert result.risk_level == "REJECTED"
        assert any("not survivable" in r for r in result.hard_constraints.reasons)

    def test_wave_just_under_capsize_threshold_does_not_veto(self, calm_weather, vessel):
        ocean = OceanState(significant_wave_height_m=2.9)  # just under 2x of 1.5m
        geo = GeoState(inside_mpa=False, nearest_port_distance_km=5.0, depth_m=50.0)
        result = assess_risk(calm_weather, ocean, geo, vessel)
        assert result.risk_level != "REJECTED"

    def test_out_of_range_distance_vetoes(self, calm_weather, calm_ocean, vessel):
        geo = GeoState(inside_mpa=False, nearest_port_distance_km=100.0, depth_m=50.0)  # vessel range=40km
        result = assess_risk(calm_weather, calm_ocean, geo, vessel)
        assert result.risk_level == "REJECTED"
        assert any("exceeds" in r for r in result.hard_constraints.reasons)

    def test_insufficient_depth_vetoes(self, calm_weather, calm_ocean, vessel):
        geo = GeoState(inside_mpa=False, nearest_port_distance_km=5.0, depth_m=0.5)  # vessel draft=0.6m + 1m margin
        result = assess_risk(calm_weather, calm_ocean, geo, vessel)
        assert result.risk_level == "REJECTED"
        assert any("grounding" in r for r in result.hard_constraints.reasons)

    def test_land_point_vetoes(self, calm_weather, calm_ocean, vessel):
        geo = GeoState(inside_mpa=False, nearest_port_distance_km=5.0, depth_m=0.0, is_land=True)
        result = assess_risk(calm_weather, calm_ocean, geo, vessel)
        assert result.risk_level == "REJECTED"
        assert any("land" in r.lower() for r in result.hard_constraints.reasons)

    def test_multiple_violations_all_reported(self, calm_weather, vessel):
        # Out of range AND too shallow — both should show up, not just the first
        ocean = OceanState(significant_wave_height_m=0.3)
        geo = GeoState(inside_mpa=False, nearest_port_distance_km=100.0, depth_m=0.2)
        result = assess_risk(calm_weather, ocean, geo, vessel)
        assert result.risk_level == "REJECTED"
        assert len(result.hard_constraints.reasons) >= 2


class TestSoftScoring:
    """Stage 2 — only reached when Stage 1 passes."""

    def test_higher_wave_scores_higher_risk(self, calm_weather, vessel):
        geo = GeoState(inside_mpa=False, nearest_port_distance_km=5.0, depth_m=50.0)
        low = assess_risk(calm_weather, OceanState(significant_wave_height_m=0.5), geo, vessel)
        high = assess_risk(calm_weather, OceanState(significant_wave_height_m=1.4), geo, vessel)
        assert high.risk_score > low.risk_score

    def test_gust_scored_separately_from_sustained_wind(self, calm_ocean, vessel):
        geo = GeoState(inside_mpa=False, nearest_port_distance_km=5.0, depth_m=50.0)
        weather_no_gust = WeatherState(wind_speed_ms=3.0, wind_gust_ms=None)
        weather_high_gust = WeatherState(wind_speed_ms=3.0, wind_gust_ms=15.0)
        low = assess_risk(weather_no_gust, calm_ocean, geo, vessel)
        high = assess_risk(weather_high_gust, calm_ocean, geo, vessel)
        assert high.risk_score > low.risk_score
        assert high.factor_breakdown["wind_gust"] > 0

    def test_insufficient_data_when_too_much_missing(self, vessel):
        # No wave, no wind, no distance — all 3 core inputs missing
        weather = WeatherState(wind_speed_ms=None, missing=["wind"])
        ocean = OceanState(significant_wave_height_m=None, missing=["wave height"])
        geo = GeoState(nearest_port_distance_km=None, missing=["port distance"])
        result = assess_risk(weather, ocean, geo, vessel)
        assert result.risk_level == "INSUFFICIENT_DATA"
        assert result.insufficient_confidence is True

    def test_insufficient_data_at_exactly_two_missing(self, vessel):
        # Regression test for a real bug (26 Aug 2026): the threshold used
        # to be mathematically unreachable (`> 3` when only 3 inputs exist),
        # so INSUFFICIENT_DATA could never fire regardless of how much was
        # missing. This pins the now-correct boundary: 2 of 3 missing is
        # already enough to refuse a confident score.
        weather = WeatherState(wind_speed_ms=None, missing=["wind"])
        ocean = OceanState(significant_wave_height_m=None, missing=["wave height"])
        geo = GeoState(nearest_port_distance_km=5.0, depth_m=50.0)  # distance IS known
        result = assess_risk(weather, ocean, geo, vessel)
        assert result.risk_level == "INSUFFICIENT_DATA"

    def test_scores_normally_with_only_one_missing(self, calm_weather, vessel):
        ocean = OceanState(significant_wave_height_m=None, missing=["wave height"])
        geo = GeoState(nearest_port_distance_km=5.0, depth_m=50.0)
        result = assess_risk(calm_weather, ocean, geo, vessel)
        assert result.risk_level != "INSUFFICIENT_DATA"


class TestHardConstraintFunctionDirectly:
    """check_hard_constraints() is called directly by route_agent.py's
    candidate scan too — test it standalone, not only through assess_risk."""

    def test_returns_not_vetoed_for_clean_input(self, calm_weather, calm_ocean, vessel):
        geo = GeoState(inside_mpa=False, nearest_port_distance_km=5.0, depth_m=50.0)
        result = check_hard_constraints(calm_weather, calm_ocean, geo, vessel)
        assert result.vetoed is False
        assert result.reasons == []

    def test_missing_optional_fields_dont_crash(self, vessel):
        # A candidate with no geo/depth data at all shouldn't raise, just
        # skip the checks it can't evaluate.
        weather = WeatherState()
        ocean = OceanState()
        geo = GeoState()
        result = check_hard_constraints(weather, ocean, geo, vessel)
        assert result.vetoed is False
