package com.jaljeev.marine.data.remote

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

/**
 * Wire models mirroring backend/app/models/schemas.py one-for-one.
 *
 * Two rules this file follows deliberately, both from the repo's core
 * philosophy (see CLAUDE.md):
 *
 *  1. Every field the backend declares nullable is nullable here too. A
 *     missing value means the source did not answer, and the UI must say so
 *     rather than substituting a default that looks like a measurement.
 *     Nothing in this file has a fabricated fallback like `0.0`.
 *  2. Provenance fields (`sources_used`, `data_freshness`, `missing`) are
 *     carried all the way to the UI, never dropped in mapping.
 */

@Serializable
data class WeatherState(
    @SerialName("wind_speed_ms") val windSpeedMs: Double? = null,
    @SerialName("wind_gust_ms") val windGustMs: Double? = null,
    @SerialName("wind_direction_deg") val windDirectionDeg: Double? = null,
    @SerialName("precipitation_probability") val precipitationProbability: Double? = null,
    @SerialName("precipitation_mm_hr") val precipitationMmHr: Double? = null,
    @SerialName("rainfall_mm_24h") val rainfallMm24h: Double? = null,
    @SerialName("pressure_msl_hpa") val pressureMslHpa: Double? = null,
    @SerialName("pressure_trend_hpa_3h") val pressureTrendHpa3h: Double? = null,
    @SerialName("temperature_2m_c") val temperature2mC: Double? = null,
    @SerialName("dew_point_2m_c") val dewPoint2mC: Double? = null,
    @SerialName("fog_risk") val fogRisk: Boolean = false,
    @SerialName("visibility_m") val visibilityM: Double? = null,
    @SerialName("cyclone_active") val cycloneActive: Boolean = false,
    @SerialName("lightning_probability") val lightningProbability: Double? = null,
    @SerialName("sources_used") val sourcesUsed: List<String> = emptyList(),
    @SerialName("data_freshness") val dataFreshness: Map<String, String> = emptyMap(),
    val partial: Boolean = false,
    val missing: List<String> = emptyList(),
)

@Serializable
data class OceanState(
    @SerialName("significant_wave_height_m") val significantWaveHeightM: Double? = null,
    @SerialName("wave_period_s") val wavePeriodS: Double? = null,
    @SerialName("swell_height_m") val swellHeightM: Double? = null,
    @SerialName("swell_period_s") val swellPeriodS: Double? = null,
    @SerialName("swell_direction_deg") val swellDirectionDeg: Double? = null,
    @SerialName("wind_wave_height_m") val windWaveHeightM: Double? = null,
    @SerialName("wind_wave_direction_deg") val windWaveDirectionDeg: Double? = null,
    @SerialName("cross_swell") val crossSwell: Boolean = false,
    @SerialName("current_speed_ms") val currentSpeedMs: Double? = null,
    @SerialName("tide_height_m") val tideHeightM: Double? = null,
    @SerialName("tide_state") val tideState: String? = null,
    @SerialName("salinity_psu") val salinityPsu: Double? = null,
    @SerialName("mixed_layer_depth_m") val mixedLayerDepthM: Double? = null,
    @SerialName("chlorophyll_mg_m3") val chlorophyllMgM3: Double? = null,
    @SerialName("hab_risk") val habRisk: Boolean = false,
    @SerialName("sst_anomaly") val sstAnomaly: Boolean = false,
    @SerialName("sst_anomaly_z_score") val sstAnomalyZScore: Double? = null,
    /**
     * The single-year (2023) baseline caveat. CLAUDE.md is explicit that this
     * note must never be dropped by a UI that surfaces the anomaly, so
     * OceanDetails renders it verbatim whenever it is present.
     */
    @SerialName("sst_anomaly_note") val sstAnomalyNote: String? = null,
    @SerialName("sst_c") val sstC: Double? = null,
    @SerialName("sst_sources") val sstSources: Map<String, Double> = emptyMap(),
    @SerialName("sst_consensus") val sstConsensus: Double? = null,
    @SerialName("sst_disagreement") val sstDisagreement: Double? = null,
    @SerialName("sources_used") val sourcesUsed: List<String> = emptyList(),
    @SerialName("data_freshness") val dataFreshness: Map<String, String> = emptyMap(),
    val partial: Boolean = false,
    val missing: List<String> = emptyList(),
)

@Serializable
data class GeoState(
    @SerialName("inside_indian_eez") val insideIndianEez: Boolean = false,
    @SerialName("eez_territory") val eezTerritory: String? = null,
    @SerialName("inside_mpa") val insideMpa: Boolean = false,
    @SerialName("mpa_name") val mpaName: String? = null,
    @SerialName("nearest_port_name") val nearestPortName: String? = null,
    @SerialName("nearest_port_distance_km") val nearestPortDistanceKm: Double? = null,
    @SerialName("depth_m") val depthM: Double? = null,
    @SerialName("is_land") val isLand: Boolean = false,
    val missing: List<String> = emptyList(),
)

/** Stage 1 of the decision pipeline: vetoes, evaluated before any scoring. */
@Serializable
data class HardConstraintResult(
    val vetoed: Boolean = false,
    val reasons: List<String> = emptyList(),
)

@Serializable
data class RiskAssessment(
    @SerialName("risk_score") val riskScore: Int,
    @SerialName("risk_level") val riskLevel: String,
    @SerialName("factor_breakdown") val factorBreakdown: Map<String, Int> = emptyMap(),
    val explanation: List<String> = emptyList(),
    @SerialName("hard_constraints") val hardConstraints: HardConstraintResult = HardConstraintResult(),
    @SerialName("insufficient_confidence") val insufficientConfidence: Boolean = false,
    @SerialName("confidence_reason") val confidenceReason: String? = null,
)

@Serializable
data class RouteCandidate(
    val lat: Double,
    val lon: Double,
    @SerialName("distance_from_origin_km") val distanceFromOriginKm: Double,
    @SerialName("bearing_deg") val bearingDeg: Double,
    @SerialName("risk_score") val riskScore: Int,
    @SerialName("risk_level") val riskLevel: String,
    val rejected: Boolean = false,
    @SerialName("rejection_reason") val rejectionReason: String? = null,
)

@Serializable
data class RouteWaypointRisk(
    val lat: Double,
    val lon: Double,
    @SerialName("risk_score") val riskScore: Int,
)

@Serializable
data class OptimizedRoute(
    @SerialName("origin_lat") val originLat: Double,
    @SerialName("origin_lon") val originLon: Double,
    @SerialName("found_route") val foundRoute: Boolean,
    val reason: String? = null,
    val waypoints: List<RouteWaypointRisk> = emptyList(),
    @SerialName("destination_maps_url") val destinationMapsUrl: String? = null,
    @SerialName("total_risk_cost") val totalRiskCost: Double? = null,
    @SerialName("cells_evaluated") val cellsEvaluated: Int = 0,
    @SerialName("cells_viable") val cellsViable: Int = 0,
)

@Serializable
data class LatLonPoint(
    val lat: Double = 0.0,
    val lon: Double = 0.0,
)

@Serializable
data class RouteRecommendation(
    @SerialName("origin_lat") val originLat: Double,
    @SerialName("origin_lon") val originLon: Double,
    @SerialName("destination_lat") val destinationLat: Double? = null,
    @SerialName("destination_lon") val destinationLon: Double? = null,
    @SerialName("destination_maps_url") val destinationMapsUrl: String? = null,
    @SerialName("distance_km") val distanceKm: Double? = null,
    @SerialName("bearing_deg") val bearingDeg: Double? = null,
    @SerialName("destination_risk") val destinationRisk: RiskAssessment? = null,
    val waypoints: List<LatLonPoint> = emptyList(),
    @SerialName("candidates_evaluated") val candidatesEvaluated: List<RouteCandidate> = emptyList(),
    val recommendation: String,
    @SerialName("found_safe_zone") val foundSafeZone: Boolean = false,
)

@Serializable
data class ValidationResult(
    val valid: Boolean = true,
    val issues: List<String> = emptyList(),
)

/** PRD Section 36 "AI reasoning receipt" - the centrepiece of the chat UI. */
@Serializable
data class EvidenceReceipt(
    @SerialName("decision_id") val decisionId: String? = null,
    @SerialName("recommendation_summary") val recommendationSummary: String = "",
    @SerialName("risk_score") val riskScore: Int? = null,
    @SerialName("risk_level") val riskLevel: String? = null,
    @SerialName("factor_lines") val factorLines: List<String> = emptyList(),
    @SerialName("sources_used") val sourcesUsed: List<String> = emptyList(),
    @SerialName("data_freshness") val dataFreshness: Map<String, String> = emptyMap(),
    @SerialName("data_gaps") val dataGaps: List<String> = emptyList(),
    @SerialName("rejected_alternatives") val rejectedAlternatives: List<String> = emptyList(),
    @SerialName("confidence_statement") val confidenceStatement: String = "",
    @SerialName("validation_note") val validationNote: String? = null,
    @SerialName("location_lat") val locationLat: Double? = null,
    @SerialName("location_lon") val locationLon: Double? = null,
    @SerialName("location_maps_url") val locationMapsUrl: String? = null,
) {
    /** True when the backend returned an empty receipt (non-marine small talk). */
    val isEmpty: Boolean
        get() = recommendationSummary.isBlank() &&
            factorLines.isEmpty() &&
            sourcesUsed.isEmpty() &&
            riskLevel == null
}

@Serializable
data class SimulationResult(
    val scenario: String,
    @SerialName("baseline_risk_score") val baselineRiskScore: Int,
    @SerialName("baseline_risk_level") val baselineRiskLevel: String,
    @SerialName("scenario_risk_score") val scenarioRiskScore: Int,
    @SerialName("scenario_risk_level") val scenarioRiskLevel: String,
    val delta: Int,
    @SerialName("scenario_explanation") val scenarioExplanation: List<String> = emptyList(),
    @SerialName("is_synthetic_perturbation") val isSyntheticPerturbation: Boolean = false,
    val narrative: String,
)

@Serializable
data class FusedMarineState(
    val lat: Double,
    val lon: Double,
    @SerialName("maps_url") val mapsUrl: String? = null,
    @SerialName("queried_at") val queriedAt: String,
    val weather: WeatherState = WeatherState(),
    val ocean: OceanState = OceanState(),
    val geo: GeoState = GeoState(),
    val risk: RiskAssessment,
    val validation: ValidationResult = ValidationResult(),
    @SerialName("confidence_note") val confidenceNote: String = "",
)

@Serializable
data class QuickCheckResult(
    val lat: Double,
    val lon: Double,
    @SerialName("maps_url") val mapsUrl: String? = null,
    @SerialName("checked_at") val checkedAt: String,
    @SerialName("risk_score") val riskScore: Int,
    @SerialName("risk_level") val riskLevel: String,
    val vetoed: Boolean,
    val reasons: List<String> = emptyList(),
    val explanation: List<String> = emptyList(),
    @SerialName("insufficient_confidence") val insufficientConfidence: Boolean = false,
    @SerialName("confidence_reason") val confidenceReason: String? = null,
)

@Serializable
data class ChatRequest(
    val message: String,
    @SerialName("session_id") val sessionId: String? = null,
    @SerialName("client_lat") val clientLat: Double? = null,
    @SerialName("client_lon") val clientLon: Double? = null,
)

@Serializable
data class ChatResponse(
    val answer: String,
    val trace: List<String> = emptyList(),
    /** Raw tool_results from the planner - shape varies by intent, so it stays untyped. */
    val data: JsonObject? = null,
    val evidence: EvidenceReceipt = EvidenceReceipt(),
    @SerialName("decision_id") val decisionId: String,
    @SerialName("session_id") val sessionId: String,
)

@Serializable
data class HealthResponse(
    val status: String,
    val env: String? = null,
)
