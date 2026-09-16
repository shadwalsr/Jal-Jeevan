package com.jaljeev.marine.ui.route

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.jaljeev.marine.AppContainer
import com.jaljeev.marine.data.remote.OptimizedRoute
import com.jaljeev.marine.data.remote.RouteRecommendation
import com.jaljeev.marine.data.remote.RouteWaypointRisk
import com.jaljeev.marine.domain.ApiOutcome
import com.jaljeev.marine.domain.GeoPoint
import com.jaljeev.marine.domain.RouteOverlay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

enum class RouteMode { SafestZone, Optimized }

data class RouteUiState(
    val origin: GeoPoint? = null,
    val rangeKm: Float = 40f,
    val running: RouteMode? = null,
    val recommendation: RouteRecommendation? = null,
    val optimized: OptimizedRoute? = null,
    val error: String? = null,
    val errorDetail: String? = null,
)

class RouteViewModel(private val container: AppContainer) : ViewModel() {

    private val _ui = MutableStateFlow(RouteUiState())
    val ui: StateFlow<RouteUiState> = _ui.asStateFlow()

    init {
        viewModelScope.launch {
            container.session.selectedPoint.collect { point ->
                if (point != null && _ui.value.origin == null) {
                    _ui.value = _ui.value.copy(origin = point)
                }
            }
        }
    }

    fun setOrigin(point: GeoPoint) {
        _ui.value = _ui.value.copy(origin = point)
    }

    fun setRange(km: Float) {
        _ui.value = _ui.value.copy(rangeKm = km)
    }

    fun useMyLocation() {
        viewModelScope.launch {
            val point = container.locationProvider.current()
            if (point == null) {
                _ui.value = _ui.value.copy(
                    error = "No position fix available.",
                    errorDetail = "Fused location returned nothing, or permission is off.",
                )
            } else {
                _ui.value = _ui.value.copy(origin = point, error = null, errorDetail = null)
            }
        }
    }

    /**
     * The fast candidate scan (/marine/safest-route): 16 zones ranked by the
     * shared hard-constraint + score logic. Its waypoints carry no per-point
     * score, which the overlay records so the map does not colour them as if
     * they did.
     */
    fun findSafestZone() {
        val origin = _ui.value.origin ?: return
        startSearch(RouteMode.SafestZone) {
            when (val outcome = container.repository.safestRoute(origin.lat, origin.lon, _ui.value.rangeKm.toDouble())) {
                is ApiOutcome.Ok -> {
                    val result = outcome.value
                    _ui.value = _ui.value.copy(
                        running = null,
                        recommendation = result,
                        optimized = null,
                        error = null,
                        errorDetail = null,
                    )
                    val points = buildList {
                        add(RouteWaypointRisk(result.originLat, result.originLon, 0))
                        result.waypoints.forEach { add(RouteWaypointRisk(it.lat, it.lon, 0)) }
                        if (result.destinationLat != null && result.destinationLon != null) {
                            add(RouteWaypointRisk(result.destinationLat, result.destinationLon, 0))
                        }
                    }
                    container.session.setRoute(
                        RouteOverlay(
                            origin = GeoPoint(result.originLat, result.originLon),
                            waypoints = points,
                            label = if (result.foundSafeZone) "Safest zone within ${_ui.value.rangeKm.toInt()} km"
                            else "No safe zone found",
                            waypointsAreRiskScored = false,
                            destinationMapsUrl = result.destinationMapsUrl,
                        )
                    )
                }

                is ApiOutcome.Err -> fail(outcome)
            }
        }
    }

    /**
     * A* over the H3 risk-weighted graph (/marine/optimize-route). Slower by
     * design - the backend caps it at 90 s - so the UI must keep saying it is
     * still working rather than looking hung.
     */
    fun optimizeRoute() {
        val origin = _ui.value.origin ?: return
        startSearch(RouteMode.Optimized) {
            when (val outcome = container.repository.optimizeRoute(origin.lat, origin.lon, _ui.value.rangeKm.toDouble())) {
                is ApiOutcome.Ok -> {
                    val result = outcome.value
                    _ui.value = _ui.value.copy(
                        running = null,
                        optimized = result,
                        recommendation = null,
                        error = null,
                        errorDetail = null,
                    )
                    container.session.setRoute(
                        RouteOverlay(
                            origin = GeoPoint(result.originLat, result.originLon),
                            waypoints = result.waypoints,
                            label = if (result.foundRoute) "A* route, ${result.waypoints.size} waypoints"
                            else "No viable route",
                            waypointsAreRiskScored = true,
                            destinationMapsUrl = result.destinationMapsUrl,
                        )
                    )
                }

                is ApiOutcome.Err -> fail(outcome)
            }
        }
    }

    fun showOnMap() {
        val destination = _ui.value.optimized?.waypoints?.lastOrNull()?.let { GeoPoint(it.lat, it.lon) }
            ?: _ui.value.recommendation?.let { rec ->
                rec.destinationLat?.let { lat -> rec.destinationLon?.let { lon -> GeoPoint(lat, lon) } }
            }
            ?: _ui.value.origin
        destination?.let { container.session.focusOnMap(it) }
    }

    private fun startSearch(mode: RouteMode, block: suspend () -> Unit) {
        if (_ui.value.running != null) return
        _ui.value = _ui.value.copy(running = mode, error = null, errorDetail = null)
        viewModelScope.launch { block() }
    }

    private fun fail(outcome: ApiOutcome.Err) {
        _ui.value = _ui.value.copy(running = null, error = outcome.message, errorDetail = outcome.detail)
    }

    companion object {
        fun factory(container: AppContainer): ViewModelProvider.Factory = viewModelFactory {
            initializer { RouteViewModel(container) }
        }
    }
}
