"""
Normalized state dataclasses returned by each agent — PRD Section 8.
Every field that comes from external data carries provenance via
`sources_used` / `data_freshness` so nothing is presented without a citation.
"""
from datetime import datetime

from pydantic import BaseModel


class WeatherState(BaseModel):
    wind_speed_ms: float | None = None
    wind_gust_ms: float | None = None
    wind_direction_deg: float | None = None
    precipitation_probability: float | None = None
    precipitation_mm_hr: float | None = None
    rainfall_mm_24h: float | None = None
    pressure_msl_hpa: float | None = None
    pressure_trend_hpa_3h: float | None = None  # negative = falling (storm precursor)
    temperature_2m_c: float | None = None
    dew_point_2m_c: float | None = None
    fog_risk: bool = False
    visibility_m: float | None = None
    cyclone_active: bool = False
    lightning_probability: float | None = None
    sources_used: list[str] = []
    data_freshness: dict[str, str] = {}
    partial: bool = False
    missing: list[str] = []


class OceanState(BaseModel):
    significant_wave_height_m: float | None = None
    wave_period_s: float | None = None
    swell_height_m: float | None = None
    swell_period_s: float | None = None
    swell_direction_deg: float | None = None
    wind_wave_height_m: float | None = None
    wind_wave_direction_deg: float | None = None
    cross_swell: bool = False  # swell and wind-wave arriving from meaningfully different directions
    current_speed_ms: float | None = None
    tide_height_m: float | None = None  # EOT20 harmonic prediction (astronomical tide only)
    tide_state: str | None = None  # "rising" | "falling" | "high" | "low"
    salinity_psu: float | None = None
    mixed_layer_depth_m: float | None = None
    chlorophyll_mg_m3: float | None = None
    hab_risk: bool = False  # harmful algal bloom proxy — chlorophyll spike vs. regional baseline
    sst_anomaly: bool = False
    sst_anomaly_z_score: float | None = None
    sst_anomaly_note: str | None = None
    sst_c: float | None = None
    sst_sources: dict[str, float] = {}
    sst_consensus: float | None = None
    sst_disagreement: float | None = None
    sources_used: list[str] = []
    data_freshness: dict[str, str] = {}
    partial: bool = False
    missing: list[str] = []


class GeoState(BaseModel):
    inside_indian_eez: bool = False
    eez_territory: str | None = None
    inside_mpa: bool = False
    mpa_name: str | None = None
    nearest_port_name: str | None = None
    nearest_port_distance_km: float | None = None
    depth_m: float | None = None  # GEBCO — positive, meters underwater
    is_land: bool = False
    missing: list[str] = []


class VesselProfile(BaseModel):
    """
    Defaults still match a typical small Indian fishing boat (PRD demo case:
    '8-metre boat at Puri') so every existing caller keeps its old behaviour
    unchanged. The named classes live in app/agents/vessel_profiles.py —
    fishing boats, sailing yachts and cargo/trade vessels — and that module's
    `resolve_vessel` is the only thing that should be constructing these
    from user input.
    """

    vessel_class: str = "fishing_small"
    vessel_name: str = "Generic 8m boat"
    user_group: str = "fisherman"  # fisherman | sailor | trader — who this class serves
    propulsion: str = "motor"  # motor | sail | motor_sail
    length_m: float = 8.0
    draft_m: float = 0.6  # typical small open fishing boat
    block_coefficient: float = 0.45  # hull fullness, used only for the squat estimate
    max_safe_wave_m: float = 1.5
    wind_threshold_ms: float = 12.0
    operational_range_km: float = 40.0
    cruise_speed_kn: float = 7.0  # passage-planning ETA only, never a safety threshold

    # --- Sail-only fields. None on a motor vessel, and every sail-specific
    # risk factor is skipped outright when they are None, so a motor vessel
    # can never accidentally pick up a becalmed or upwind penalty. ---
    min_working_wind_ms: float | None = None  # below this, a sailing vessel has no drive
    no_go_angle_deg: float | None = None  # cannot sail closer than this to the true wind

    # --- Trade-only. Commercial vessels get the stricter IMO/PIANC-style
    # under-keel clearance rule rather than the small-boat fixed margin. ---
    commercial: bool = False


class HardConstraintResult(BaseModel):
    """
    Stage 1 of the decision pipeline: things that VETO a candidate outright,
    independent of how good everything else looks. Evaluated before any
    scoring happens — a vetoed candidate is never scored, per the
    constraint-hierarchy design (26 Aug 2026): "some constraints must be
    able to veto a decision, others should only influence ranking."
    Only implements vetoes backed by real data the system actually has —
    see the constraint-taxonomy audit for what's still missing (legal
    boundary crossing, restricted zones, bathymetry/draft) and therefore
    NOT enforced as a hard veto yet.
    """

    vetoed: bool = False
    reasons: list[str] = []


class RiskAssessment(BaseModel):
    risk_score: int  # 0-100
    risk_level: str  # LOW / MODERATE / HIGH / EXTREME / REJECTED / INSUFFICIENT_DATA
    factor_breakdown: dict[str, int]  # factor name -> points contributed
    explanation: list[str]
    hard_constraints: HardConstraintResult = HardConstraintResult()
    insufficient_confidence: bool = False
    confidence_reason: str | None = None


class RouteCandidate(BaseModel):
    lat: float
    lon: float
    distance_from_origin_km: float
    bearing_deg: float
    risk_score: int
    risk_level: str
    rejected: bool = False
    rejection_reason: str | None = None


class PassageLeg(BaseModel):
    """
    One segment of a planned port-to-port passage. A leg is several H3 cells
    collapsed into a single steerable instruction — a skipper steers a
    heading for a distance, not a list of hexagons.
    """

    from_lat: float
    from_lon: float
    to_lat: float
    to_lon: float
    bearing_deg: float
    distance_nm: float
    sailed_distance_nm: float  # >= distance_nm when a sailing vessel must tack this leg
    eta_hours_from_departure: float  # cumulative, at the END of this leg
    risk_score: int
    risk_level: str
    forecast_hour_offset: int  # which forecast hour this leg was scored against
    beyond_forecast_horizon: bool = False
    must_tack: bool = False
    explanation: list[str] = []


class DiversionPort(BaseModel):
    """Nearest bolt-hole from a point on the passage, for when it goes wrong."""

    name: str
    lat: float
    lon: float
    distance_km: float
    from_leg_index: int


class PassagePlan(BaseModel):
    """
    A→B voyage plan — the primitive sailors and traders need, as opposed to
    the radius-based "safest zone near me" search that serves fishermen
    (route_agent.py / route_optimizer.py). Same A* machinery, same Risk
    Agent edge weights, different objective: get from this port to that one
    at acceptable risk, and tell me when I arrive.
    """

    origin_name: str | None = None
    origin_lat: float
    origin_lon: float
    destination_name: str | None = None
    destination_lat: float
    destination_lon: float

    vessel_class: str
    vessel_name: str

    found_route: bool
    reason: str | None = None

    legs: list[PassageLeg] = []
    waypoints: list["RouteWaypointRisk"] = []  # full cell-level path, for the map
    diversion_ports: list[DiversionPort] = []

    direct_distance_nm: float | None = None  # great circle, for comparison
    routed_distance_nm: float | None = None  # what the risk-avoiding path actually costs
    sailed_distance_nm: float | None = None  # routed distance plus tacking, for sail
    total_eta_hours: float | None = None
    max_leg_risk_score: int | None = None
    max_leg_risk_level: str | None = None

    h3_resolution: int | None = None
    cells_evaluated: int = 0
    cells_viable: int = 0
    forecast_note: str | None = None  # honesty: how much of this passage is real forecast
    destination_maps_url: str | None = None


class RouteWaypointRisk(BaseModel):
    lat: float
    lon: float
    risk_score: int


class OptimizedRoute(BaseModel):
    """A* result over the H3 risk-weighted graph — see app/agents/route_optimizer.py."""

    origin_lat: float
    origin_lon: float
    found_route: bool
    reason: str | None = None
    waypoints: list[RouteWaypointRisk] = []
    destination_maps_url: str | None = None  # Google Maps deep link for the final waypoint
    total_risk_cost: float | None = None  # sum of A*'s edge weights along the path
    cells_evaluated: int = 0
    cells_viable: int = 0  # cells_evaluated minus hard-constraint-vetoed cells


class RouteRecommendation(BaseModel):
    origin_lat: float
    origin_lon: float
    destination_lat: float | None = None
    destination_lon: float | None = None
    destination_maps_url: str | None = None  # ready-to-click Google Maps deep link for destination_lat/lon
    distance_km: float | None = None
    bearing_deg: float | None = None
    destination_risk: RiskAssessment | None = None
    waypoints: list[dict] = []  # [{lat, lon}, ...]
    candidates_evaluated: list[RouteCandidate] = []
    recommendation: str
    found_safe_zone: bool = False
    # Set when the requested range had nothing viable and the search agent
    # expanded outward past it to still return a real answer instead of a
    # dead-end "nothing found" — see route_agent.py::find_safest_zone. The
    # zone returned in destination_lat/lon is always the nearest one that
    # actually cleared Stage 1 + verification, whatever ring it came from.
    requested_range_km: float | None = None
    exceeded_requested_range: bool = False


class ValidationResult(BaseModel):
    valid: bool = True
    issues: list[str] = []


class EvidenceReceipt(BaseModel):
    """
    PRD Section 36 — "AI reasoning receipt": every recommendation should be
    traceable to the exact sources, freshness, and factors that produced
    it, in one structured object a UI can render directly (or an LLM can
    phrase from) without re-deriving anything.
    """

    decision_id: str | None = None
    recommendation_summary: str
    risk_score: int | None = None
    risk_level: str | None = None
    factor_lines: list[str] = []  # plain-language "X -> +N" lines, already human-readable
    sources_used: list[str] = []
    data_freshness: dict[str, str] = {}
    data_gaps: list[str] = []
    rejected_alternatives: list[str] = []  # PRD Section 16, "Why not?"
    confidence_statement: str
    validation_note: str | None = None
    # Exact coordinates for the point this receipt is actually about (the
    # route destination, or the queried point for a current-conditions
    # answer) plus a ready-to-click Google Maps link — added 26 Aug 2026
    # after a real answer told a user "the safest zone is 20km at bearing
    # 45 deg" with no way to actually find it without doing that math
    # themselves. Both the LLM prompt and the rule-based renderer are
    # required to surface these when present (see graph.py / rule_based.py).
    location_lat: float | None = None
    location_lon: float | None = None
    location_maps_url: str | None = None


class SimulationResult(BaseModel):
    scenario: str  # human-readable description of what was varied
    baseline_risk_score: int
    baseline_risk_level: str
    scenario_risk_score: int
    scenario_risk_level: str
    delta: int  # scenario - baseline, positive = got riskier
    scenario_explanation: list[str]
    is_synthetic_perturbation: bool = False  # True for hypothetical "what if wave +30%" stress tests, not real forecast data
    narrative: str


class FusedMarineState(BaseModel):
    lat: float
    lon: float
    maps_url: str | None = None  # ready-to-click Google Maps deep link for lat/lon
    queried_at: datetime
    weather: WeatherState
    ocean: OceanState
    geo: GeoState
    risk: RiskAssessment
    validation: ValidationResult = ValidationResult()
    confidence_note: str


class QuickCheckResult(BaseModel):
    """
    Response for GET /marine/quick-check — the live safety monitor's poll
    endpoint (frontend SafetyMonitor.tsx, ~every 10s from a moving vessel's
    browser geolocation). Deliberately backed by route_agent.quick_check's
    fast (Open-Meteo + MPA + bathymetry) path, NOT the full Copernicus/tide/
    SST Ocean Agent — same check_hard_constraints veto logic either way
    (single shared source of truth, see risk_agent.py), just fast enough to
    poll this often without exhausting the Copernicus login pipeline or the
    DB connection pool for every actively-monitoring user.
    """

    lat: float
    lon: float
    maps_url: str
    checked_at: datetime
    risk_score: int
    risk_level: str
    vetoed: bool
    reasons: list[str]  # why it's vetoed, if it is — empty when not vetoed
    explanation: list[str]  # Stage-2 factor lines, when scored
    insufficient_confidence: bool
    confidence_reason: str | None = None


# PassagePlan.waypoints is annotated with a forward reference because
# PassagePlan is declared next to the other passage types, above
# RouteWaypointRisk. Resolve it now that the whole module namespace exists.
PassagePlan.model_rebuild()
