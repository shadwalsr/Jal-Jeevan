package com.jaljeev.marine.domain

import com.jaljeev.marine.data.remote.RouteWaypointRisk
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class GeoPoint(val lat: Double, val lon: Double) {
    fun format(): String = String.format("%.4f, %.4f", lat, lon)
}

/**
 * A route ready to draw. Both /marine/safest-route and /marine/optimize-route
 * are normalised into this shape so the map only knows about one of them.
 * [waypointsAreRiskScored] is false for the fast candidate scan, whose
 * waypoints are plain positions with no per-point score - the map must not
 * colour those as if a score had been computed for them.
 */
data class RouteOverlay(
    val origin: GeoPoint,
    val waypoints: List<RouteWaypointRisk>,
    val label: String,
    val waypointsAreRiskScored: Boolean,
    val destinationMapsUrl: String? = null,
)

/**
 * Cross-tab state that is genuinely shared: the point the user is currently
 * asking about, and the last route computed. Chat can hand the map a
 * destination ("Show on map"), the map can hand Route an origin, without
 * either screen owning the other's ViewModel.
 */
class AppSession {

    private val _selectedPoint = MutableStateFlow<GeoPoint?>(null)
    val selectedPoint: StateFlow<GeoPoint?> = _selectedPoint.asStateFlow()

    private val _route = MutableStateFlow<RouteOverlay?>(null)
    val route: StateFlow<RouteOverlay?> = _route.asStateFlow()

    /** Set when a point should be shown AND immediately checked on the map tab. */
    private val _pendingMapFocus = MutableStateFlow<GeoPoint?>(null)
    val pendingMapFocus: StateFlow<GeoPoint?> = _pendingMapFocus.asStateFlow()

    fun selectPoint(point: GeoPoint) {
        _selectedPoint.value = point
    }

    fun focusOnMap(point: GeoPoint) {
        _selectedPoint.value = point
        _pendingMapFocus.value = point
    }

    fun consumeMapFocus() {
        _pendingMapFocus.value = null
    }

    fun setRoute(route: RouteOverlay?) {
        _route.value = route
    }
}
