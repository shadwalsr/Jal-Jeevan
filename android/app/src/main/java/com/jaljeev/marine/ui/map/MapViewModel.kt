package com.jaljeev.marine.ui.map

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.jaljeev.marine.AppContainer
import com.jaljeev.marine.data.remote.FusedMarineState
import com.jaljeev.marine.domain.ApiOutcome
import com.jaljeev.marine.domain.GeoPoint
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class MapUiState(
    val selected: GeoPoint? = null,
    val loading: Boolean = false,
    val state: FusedMarineState? = null,
    val staleAgeMillis: Long? = null,
    val error: String? = null,
    val errorDetail: String? = null,
    val locationDenied: Boolean = false,
    val boundaries: BoundaryLayers? = null,
    /** Non-null when the exclusion layer could not be loaded - the UI must say so. */
    val boundaryNote: String? = null,
)

class MapViewModel(private val container: AppContainer) : ViewModel() {

    private val _ui = MutableStateFlow(MapUiState())
    val ui: StateFlow<MapUiState> = _ui.asStateFlow()

    val route = container.session.route
    val focus = container.session.pendingMapFocus

    private var inFlight: Job? = null
    private var boundaryJob: Job? = null
    private var lastBoundaryKey: String? = null

    init {
        // A point chosen anywhere else in the app (a chat answer's location,
        // a route destination) becomes this screen's selection.
        viewModelScope.launch {
            container.session.selectedPoint.collect { point ->
                if (point != null && point != _ui.value.selected) {
                    _ui.value = _ui.value.copy(selected = point)
                    load(point)
                }
            }
        }
    }

    /**
     * Exclusion layers for the visible area. Keyed on a coarse bbox so small
     * pans reuse the last fetch instead of hammering the endpoint on every
     * camera idle - and the server caches these for a week regardless.
     */
    fun onCameraIdle(minLat: Double, minLon: Double, maxLat: Double, maxLon: Double) {
        if (maxLat - minLat > 39 || maxLon - minLon > 39) return
        val key = "%.1f,%.1f,%.1f,%.1f".format(minLat, minLon, maxLat, maxLon)
        if (key == lastBoundaryKey) return
        lastBoundaryKey = key
        boundaryJob?.cancel()
        boundaryJob = viewModelScope.launch {
            when (val outcome = container.repository.boundaries(minLat, minLon, maxLat, maxLon)) {
                is ApiOutcome.Ok -> {
                    val root = outcome.value
                    _ui.value = _ui.value.copy(
                        boundaries = BoundaryLayers(
                            eez = root["eez"]?.toString(),
                            mpa = root["mpa"]?.toString(),
                            ports = root["ports"]?.toString(),
                        ),
                        boundaryNote = null,
                    )
                }
                is ApiOutcome.Err -> {
                    // An empty exclusion layer must never be allowed to imply
                    // "nothing is restricted here".
                    lastBoundaryKey = null
                    _ui.value = _ui.value.copy(
                        boundaryNote = "Exclusion layer unavailable - restricted areas are not being shown."
                    )
                }
            }
        }
    }

    fun onMapClick(point: GeoPoint) {
        container.session.selectPoint(point)
        _ui.value = _ui.value.copy(selected = point)
        load(point)
    }

    fun consumeFocus() = container.session.consumeMapFocus()

    fun clearRoute() = container.session.setRoute(null)

    fun useMyLocation() {
        viewModelScope.launch {
            if (!container.locationProvider.hasPermission()) {
                _ui.value = _ui.value.copy(locationDenied = true)
                return@launch
            }
            val point = container.locationProvider.current()
            if (point == null) {
                _ui.value = _ui.value.copy(
                    error = "No position fix available yet.",
                    errorDetail = "Fused location returned nothing within 20 s.",
                )
                return@launch
            }
            container.session.focusOnMap(point)
            _ui.value = _ui.value.copy(selected = point, locationDenied = false)
            load(point)
        }
    }

    fun onLocationPermissionResult(granted: Boolean) {
        _ui.value = _ui.value.copy(locationDenied = !granted)
        if (granted) useMyLocation()
    }

    fun retry() {
        _ui.value.selected?.let { load(it) }
    }

    private fun load(point: GeoPoint) {
        inFlight?.cancel() // a new tap supersedes an in-flight lookup
        _ui.value = _ui.value.copy(loading = true, error = null, errorDetail = null, staleAgeMillis = null)
        inFlight = viewModelScope.launch {
            when (val outcome = container.repository.marineState(point.lat, point.lon)) {
                is ApiOutcome.Ok -> _ui.value = _ui.value.copy(
                    loading = false,
                    state = outcome.value,
                    staleAgeMillis = outcome.staleAgeMillis,
                    error = null,
                    errorDetail = null,
                )

                is ApiOutcome.Err -> _ui.value = _ui.value.copy(
                    loading = false,
                    state = null, // never leave a previous point's readings on screen under a new coordinate
                    error = outcome.message,
                    errorDetail = outcome.detail,
                )
            }
        }
    }

    companion object {
        fun factory(container: AppContainer): ViewModelProvider.Factory = viewModelFactory {
            initializer { MapViewModel(container) }
        }
    }
}
