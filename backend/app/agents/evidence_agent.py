"""
Explanation & Evidence Agent (PRD Section 8 / Section 36's "AI reasoning
receipt"). Deterministic aggregation — no LLM: it reformats what other
agents already produced into one traceable structure, it doesn't invent
new reasoning. The planner's synthesize_answer step (the one place an LLM
touches this data) is fed this receipt rather than raw tool JSON, so its
phrasing is grounded in an already-organized, already-labeled evidence
trail instead of having to re-derive structure from a nested dict itself.

Three builders: one for a single-point /marine/state result, one for a
Route Agent result (which additionally has rejected candidates — the
PRD's "Why not?" feature, Section 16), and one for a Passage Agent
port-to-port plan (the sailor/trader path, whose equivalent of "why not?"
is the leg-by-leg breakdown plus the diversion ports).
"""
from app.core.maps import google_maps_url
from app.models.schemas import EvidenceReceipt, FusedMarineState, PassagePlan, RouteRecommendation

# "Why not?" only needs to be answerable, not exhaustive — the full list of
# rejected candidates is still on RouteRecommendation.candidates_evaluated
# for anything that wants it (the map view, an API consumer). Capping what
# goes into the EvidenceReceipt matters because this receipt is exactly what
# gets JSON-dumped into the synthesis LLM prompt (see planner/graph.py):
# find_safest_zone can now expand its search across several rings before
# finding a viable zone (see route_agent.py's expansion policy), which
# multiplies candidates_evaluated well past the original single-ring 16 —
# feeding all of them to the LLM only inflates prompt tokens (slower, more
# expensive synthesis) without helping the phrasing say anything truer.
MAX_REJECTED_ALTERNATIVES_IN_RECEIPT = 5


def _capped_rejections(reasons: list[str]) -> list[str]:
    if len(reasons) <= MAX_REJECTED_ALTERNATIVES_IN_RECEIPT:
        return reasons
    kept = reasons[:MAX_REJECTED_ALTERNATIVES_IN_RECEIPT]
    kept.append(f"...and {len(reasons) - MAX_REJECTED_ALTERNATIVES_IN_RECEIPT} more candidate(s) rejected")
    return kept


def build_receipt_for_state(state: FusedMarineState, decision_id: str | None = None) -> EvidenceReceipt:
    sources = sorted(set(state.weather.sources_used) | set(state.ocean.sources_used))
    freshness = {**state.weather.data_freshness, **state.ocean.data_freshness}
    gaps = state.weather.missing + state.ocean.missing + state.geo.missing

    if state.risk.hard_constraints.vetoed:
        summary = f"Rejected — {'; '.join(state.risk.hard_constraints.reasons)}"
    else:
        summary = f"{state.risk.risk_level} risk ({state.risk.risk_score}/100)"

    confidence = state.confidence_note
    if state.validation.issues:
        confidence = "VALIDATION FLAGGED THIS RESULT — " + "; ".join(state.validation.issues)

    return EvidenceReceipt(
        decision_id=decision_id,
        recommendation_summary=summary,
        risk_score=state.risk.risk_score,
        risk_level=state.risk.risk_level,
        factor_lines=state.risk.explanation,
        sources_used=sources,
        data_freshness=freshness,
        data_gaps=gaps,
        rejected_alternatives=[],
        confidence_statement=confidence,
        validation_note="; ".join(state.validation.issues) if state.validation.issues else None,
        location_lat=state.lat,
        location_lon=state.lon,
        location_maps_url=google_maps_url(state.lat, state.lon),
    )


def build_receipt_for_route(route: RouteRecommendation, decision_id: str | None = None) -> EvidenceReceipt:
    if not route.found_safe_zone:
        return EvidenceReceipt(
            decision_id=decision_id,
            recommendation_summary="No viable zone found within range",
            factor_lines=[],
            rejected_alternatives=_capped_rejections([
                f"{c.lat:.2f},{c.lon:.2f} ({c.bearing_deg:.0f} deg, {c.distance_from_origin_km}km): {c.rejection_reason}"
                for c in route.candidates_evaluated
                if c.rejected
            ]),
            confidence_statement=route.recommendation,
        )

    dest_risk = route.destination_risk
    sources = dest_risk.hard_constraints.reasons if dest_risk else []
    return EvidenceReceipt(
        decision_id=decision_id,
        recommendation_summary=f"Safest zone: {route.distance_km:.1f}km at bearing {route.bearing_deg:.0f} deg",
        risk_score=dest_risk.risk_score if dest_risk else None,
        risk_level=dest_risk.risk_level if dest_risk else None,
        factor_lines=dest_risk.explanation if dest_risk else [],
        sources_used=[],  # destination_risk doesn't carry per-source freshness; full detail lives in the /marine/state call for that point
        data_freshness={},
        data_gaps=[],
        rejected_alternatives=_capped_rejections([
            f"{c.lat:.2f},{c.lon:.2f} ({c.bearing_deg:.0f} deg, {c.distance_from_origin_km}km): {c.rejection_reason}"
            for c in route.candidates_evaluated
            if c.rejected
        ]),
        confidence_statement=route.recommendation,
        location_lat=route.destination_lat,
        location_lon=route.destination_lon,
        location_maps_url=route.destination_maps_url,
    )


def build_receipt_for_passage(passage: PassagePlan, decision_id: str | None = None) -> EvidenceReceipt:
    """
    Third builder, for the sailor/trader port-to-port path. Same
    deterministic reformatting job as the other two — nothing here computes
    or infers, it only reorganises what the Passage Agent already produced.

    The one thing this receipt says that the others cannot: how much of the
    plan is real forecast. A passage spans hours or days, and the honest
    answer for its later legs is often "this is beyond the forecast
    horizon," which must reach the user rather than being smoothed over by
    whatever phrases the final answer.
    """
    if not passage.found_route:
        return EvidenceReceipt(
            decision_id=decision_id,
            recommendation_summary=(
                f"No viable passage from {passage.origin_name or 'the departure point'} to "
                f"{passage.destination_name or 'the destination'} for {passage.vessel_name}"
            ),
            factor_lines=[],
            confidence_statement=passage.reason or "No route found.",
            location_lat=passage.destination_lat,
            location_lon=passage.destination_lon,
        )

    origin_label = passage.origin_name or f"{passage.origin_lat:.2f},{passage.origin_lon:.2f}"
    dest_label = passage.destination_name or f"{passage.destination_lat:.2f},{passage.destination_lon:.2f}"

    factor_lines = [
        f"Leg {i + 1}: steer {leg.bearing_deg:.0f} deg for {leg.distance_nm:.1f} nm — "
        f"{leg.risk_level} ({leg.risk_score}/100) at +{leg.forecast_hour_offset}h"
        + (" — must be tacked, cannot be laid direct" if leg.must_tack else "")
        + (" — BEYOND FORECAST HORIZON" if leg.beyond_forecast_horizon else "")
        for i, leg in enumerate(passage.legs)
    ]

    # The worst leg is the one that decides whether this passage is
    # acceptable — an average across a long passage would hide exactly the
    # few hours that matter.
    if passage.max_leg_risk_level:
        factor_lines.append(
            f"Worst leg on this passage: {passage.max_leg_risk_level} ({passage.max_leg_risk_score}/100) — "
            f"this, not the average, is what the passage should be judged on"
        )

    if passage.sailed_distance_nm and passage.routed_distance_nm:
        if passage.sailed_distance_nm > passage.routed_distance_nm + 0.1:
            factor_lines.append(
                f"{passage.routed_distance_nm:.1f} nm over the ground, but {passage.sailed_distance_nm:.1f} nm "
                f"actually sailed once windward legs are tacked"
            )

    if passage.direct_distance_nm and passage.routed_distance_nm:
        detour = passage.routed_distance_nm - passage.direct_distance_nm
        if detour > 0.5:
            factor_lines.append(
                f"Routed {detour:.1f} nm longer than the {passage.direct_distance_nm:.1f} nm direct track "
                f"to keep clear of higher-risk or vetoed water"
            )

    gaps = []
    if passage.forecast_note and any(leg.beyond_forecast_horizon for leg in passage.legs):
        gaps.append("forecast horizon exceeded for the later legs of this passage")

    diversions = [
        f"Shelter from leg {d.from_leg_index + 1}: {d.name} ({d.distance_km:.0f}km)"
        for d in passage.diversion_ports
    ]

    hours = passage.total_eta_hours or 0.0
    return EvidenceReceipt(
        decision_id=decision_id,
        recommendation_summary=(
            f"{origin_label} to {dest_label} for {passage.vessel_name}: "
            f"{passage.routed_distance_nm:.0f} nm, about {hours:.1f}h "
            f"({hours / 24:.1f} days) at {len(passage.legs)} legs"
        ),
        risk_score=passage.max_leg_risk_score,
        risk_level=passage.max_leg_risk_level,
        factor_lines=factor_lines,
        sources_used=["Open-Meteo Marine", "Open-Meteo Forecast", "GEBCO bathymetry", "WDPA protected areas"],
        data_freshness={},
        data_gaps=gaps,
        # Not "rejected candidates" in the Route Agent's sense — these are
        # the bolt-holes, which is the equivalent "what are my options if
        # this goes wrong" information for a passage.
        rejected_alternatives=diversions,
        confidence_statement=passage.forecast_note or "Passage scored against current forecast.",
        location_lat=passage.destination_lat,
        location_lon=passage.destination_lon,
        location_maps_url=passage.destination_maps_url,
    )
