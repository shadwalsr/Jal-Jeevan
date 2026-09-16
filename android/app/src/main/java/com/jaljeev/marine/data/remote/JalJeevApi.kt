package com.jaljeev.marine.data.remote

import kotlinx.serialization.json.JsonObject
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query

/**
 * The complete JalJeev backend surface as of this build - see
 * backend/app/api/marine.py and backend/app/api/chat.py.
 *
 * Every marine endpoint takes the same four vessel parameters, because the
 * risk pipeline's hard constraints are vessel-relative (a 1.8 m wave vetoes
 * an 8 m open boat and does not veto a trawler). They are sent on every call
 * from the profile in Settings rather than relying on the server defaults,
 * so what the user configured is always what was actually evaluated.
 */
interface JalJeevApi {

    @GET("/health")
    suspend fun health(): HealthResponse

    @POST("/chat")
    suspend fun chat(@Body request: ChatRequest): ChatResponse

    /**
     * Static exclusion layers (foreign EEZ, protected areas, ports).
     *
     * Returned as raw GeoJSON rather than typed models: MapLibre consumes a
     * GeoJSON string as-is, so parsing it into Kotlin data classes only to
     * re-serialise it would be pure overhead.
     */
    @GET("/map/boundaries")
    suspend fun boundaries(
        @Query("min_lat") minLat: Double,
        @Query("min_lon") minLon: Double,
        @Query("max_lat") maxLat: Double,
        @Query("max_lon") maxLon: Double,
        @Query("types") types: String = "eez,mpa,ports",
    ): JsonObject

    @GET("/marine/state")
    suspend fun marineState(
        @Query("lat") lat: Double,
        @Query("lon") lon: Double,
        @Query("vessel_length_m") vesselLengthM: Double,
        @Query("vessel_max_safe_wave_m") vesselMaxSafeWaveM: Double,
        @Query("vessel_wind_threshold_ms") vesselWindThresholdMs: Double,
        @Query("vessel_operational_range_km") vesselOperationalRangeKm: Double,
    ): FusedMarineState

    @GET("/marine/quick-check")
    suspend fun quickCheck(
        @Query("lat") lat: Double,
        @Query("lon") lon: Double,
        @Query("vessel_length_m") vesselLengthM: Double,
        @Query("vessel_max_safe_wave_m") vesselMaxSafeWaveM: Double,
        @Query("vessel_wind_threshold_ms") vesselWindThresholdMs: Double,
        @Query("vessel_operational_range_km") vesselOperationalRangeKm: Double,
    ): QuickCheckResult

    @GET("/marine/safest-route")
    suspend fun safestRoute(
        @Query("lat") lat: Double,
        @Query("lon") lon: Double,
        @Query("range_km") rangeKm: Double,
        @Query("vessel_length_m") vesselLengthM: Double,
        @Query("vessel_max_safe_wave_m") vesselMaxSafeWaveM: Double,
        @Query("vessel_wind_threshold_ms") vesselWindThresholdMs: Double,
        @Query("vessel_operational_range_km") vesselOperationalRangeKm: Double,
    ): RouteRecommendation

    @GET("/marine/optimize-route")
    suspend fun optimizeRoute(
        @Query("lat") lat: Double,
        @Query("lon") lon: Double,
        @Query("range_km") rangeKm: Double,
        @Query("vessel_length_m") vesselLengthM: Double,
        @Query("vessel_max_safe_wave_m") vesselMaxSafeWaveM: Double,
        @Query("vessel_wind_threshold_ms") vesselWindThresholdMs: Double,
        @Query("vessel_operational_range_km") vesselOperationalRangeKm: Double,
    ): OptimizedRoute

    @GET("/marine/simulate/time-shift")
    suspend fun simulateTimeShift(
        @Query("lat") lat: Double,
        @Query("lon") lon: Double,
        @Query("hours_later") hoursLater: Int,
        @Query("vessel_length_m") vesselLengthM: Double,
        @Query("vessel_max_safe_wave_m") vesselMaxSafeWaveM: Double,
        @Query("vessel_wind_threshold_ms") vesselWindThresholdMs: Double,
        @Query("vessel_operational_range_km") vesselOperationalRangeKm: Double,
    ): SimulationResult

    @GET("/marine/simulate/wave-perturbation")
    suspend fun simulateWavePerturbation(
        @Query("lat") lat: Double,
        @Query("lon") lon: Double,
        @Query("wave_multiplier") waveMultiplier: Double,
        @Query("vessel_length_m") vesselLengthM: Double,
        @Query("vessel_max_safe_wave_m") vesselMaxSafeWaveM: Double,
        @Query("vessel_wind_threshold_ms") vesselWindThresholdMs: Double,
        @Query("vessel_operational_range_km") vesselOperationalRangeKm: Double,
    ): SimulationResult
}
