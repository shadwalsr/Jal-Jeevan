package com.jaljeev.marine.ui.map

import android.annotation.SuppressLint
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Color as AndroidColor
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.graphics.toArgb
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import com.jaljeev.marine.domain.GeoPoint
import com.jaljeev.marine.domain.RouteOverlay
import com.jaljeev.marine.domain.riskColorForScore
import org.maplibre.android.MapLibre
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.geometry.LatLngBounds
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.Style
import org.maplibre.android.style.expressions.Expression
import org.maplibre.android.style.layers.CircleLayer
import org.maplibre.android.style.layers.FillLayer
import org.maplibre.android.style.layers.LineLayer
import org.maplibre.android.style.layers.PropertyFactory
import org.maplibre.android.style.sources.GeoJsonSource
import org.maplibre.geojson.Feature
import org.maplibre.geojson.FeatureCollection
import org.maplibre.geojson.LineString
import org.maplibre.geojson.Point

/**
 * Free, key-less OpenStreetMap raster style - byte-for-byte the same source
 * and attribution the web client uses (frontend/src/MarineMap.tsx), so the
 * two front-ends are looking at literally the same basemap and neither one
 * needs a commercial tile key to run.
 */
private const val OSM_STYLE_JSON = """
{
  "version": 8,
  "sources": {
    "osm": {
      "type": "raster",
      "tiles": ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      "tileSize": 256,
      "attribution": "© OpenStreetMap contributors"
    }
  },
  "layers": [{ "id": "osm", "type": "raster", "source": "osm" }]
}
"""

private const val SRC_EEZ = "jaljeev-eez"
private const val SRC_MPA = "jaljeev-mpa"
private const val SRC_PORTS = "jaljeev-ports"
private const val LYR_EEZ_PERMITTED = "jaljeev-eez-permitted"
private const val LYR_EEZ_EXCL_FILL = "jaljeev-eez-exclusion-fill"
private const val LYR_EEZ_EXCL_LINE = "jaljeev-eez-exclusion-line"
private const val LYR_MPA_FILL = "jaljeev-mpa-fill"
private const val LYR_MPA_LINE = "jaljeev-mpa-line"
private const val LYR_PORTS = "jaljeev-ports-circles"
private const val IMG_HATCH = "jaljeev-hatch"

// Exclusions use the chart convention for restricted areas: a magenta-crimson
// hatch, never a solid fill. Deliberate and load-bearing - a hard-constraint
// veto is categorically different from a high risk score, and painting them in
// the same visual language would undo on screen exactly what risk_agent.py's
// two-stage pipeline enforces in the backend. Hatching also survives greyscale
// and does not depend on hue.
private const val EXCLUSION_COLOR = "#C2185B"
private const val PERMITTED_COLOR = "#3ECFA8"

private const val SRC_ROUTE = "jaljeev-route"
private const val SRC_WAYPOINTS = "jaljeev-waypoints"
private const val SRC_SELECTED = "jaljeev-selected"
private const val LYR_ROUTE = "jaljeev-route-line"
private const val LYR_WAYPOINTS = "jaljeev-waypoint-circles"
private const val LYR_SELECTED = "jaljeev-selected-circle"

/**
 * MapLibre Native wrapped for Compose.
 *
 * Everything drawn here is a GeoJSON source plus a style layer rather than
 * the legacy marker/annotation API: layers are the part of the SDK that is
 * stable across MapLibre major versions, and it keeps updates to a single
 * setGeoJson call instead of add/remove churn on every recomposition.
 */
@SuppressLint("MissingPermission")
@Composable
fun MarineMapView(
    selected: GeoPoint?,
    route: RouteOverlay?,
    focusRequest: GeoPoint?,
    onMapClick: (GeoPoint) -> Unit,
    boundaries: BoundaryLayers? = null,
    onCameraIdle: (minLat: Double, minLon: Double, maxLat: Double, maxLon: Double) -> Unit = { _, _, _, _ -> },
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    // Must run before any MapView is constructed.
    remember { MapLibre.getInstance(context) }

    val mapView = remember { MapView(context) }
    val holder = remember { MapHolder() }

    DisposableEffect(lifecycleOwner) {
        mapView.onCreate(null)
        // The composable can enter while the host is already STARTED/RESUMED,
        // in which case those events will never fire again - without this the
        // map surface is created but never started, and renders nothing.
        if (lifecycleOwner.lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) {
            mapView.onStart()
        }
        if (lifecycleOwner.lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) {
            mapView.onResume()
        }
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> mapView.onStart()
                Lifecycle.Event.ON_RESUME -> mapView.onResume()
                Lifecycle.Event.ON_PAUSE -> mapView.onPause()
                Lifecycle.Event.ON_STOP -> mapView.onStop()
                Lifecycle.Event.ON_DESTROY -> mapView.onDestroy()
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            mapView.onDestroy()
        }
    }

    AndroidView(
        modifier = modifier,
        factory = {
            mapView.getMapAsync { map ->
                holder.map = map
                map.setStyle(Style.Builder().fromJson(OSM_STYLE_JSON)) { style ->
                    holder.style = style
                    installLayers(style)
                    holder.applyPending()
                }
                map.addOnMapClickListener { latLng ->
                    onMapClick(GeoPoint(latLng.latitude, latLng.longitude))
                    true
                }
                map.addOnCameraIdleListener {
                    val b = map.projection.visibleRegion.latLngBounds
                    onCameraIdle(b.latitudeSouth, b.longitudeWest, b.latitudeNorth, b.longitudeEast)
                }
                map.uiSettings.isRotateGesturesEnabled = false
                map.uiSettings.isTiltGesturesEnabled = false
                map.uiSettings.setAttributionMargins(16, 0, 0, 16)
            }
            mapView
        },
        update = {
            holder.update(selected, route, focusRequest)
            holder.applyBoundaries(boundaries)
        },
    )
}

/** Raw GeoJSON for each exclusion layer, straight from /map/boundaries. */
data class BoundaryLayers(val eez: String?, val mpa: String?, val ports: String?)

private class MapHolder {
    var map: MapLibreMap? = null
    var style: Style? = null
    private var lastBoundaries: BoundaryLayers? = null

    /**
     * MapLibre's GeoJsonSource takes a GeoJSON string directly, so the payload
     * goes from the API to the map without ever being modelled in Kotlin.
     */
    fun applyBoundaries(layers: BoundaryLayers?) {
        if (layers == null || layers == lastBoundaries) return
        val style = style ?: return
        lastBoundaries = layers
        layers.eez?.let { style.getSourceAs<GeoJsonSource>(SRC_EEZ)?.setGeoJson(it) }
        layers.mpa?.let { style.getSourceAs<GeoJsonSource>(SRC_MPA)?.setGeoJson(it) }
        layers.ports?.let { style.getSourceAs<GeoJsonSource>(SRC_PORTS)?.setGeoJson(it) }
    }

    private var pendingSelected: GeoPoint? = null
    private var pendingRoute: RouteOverlay? = null
    private var pendingFocus: GeoPoint? = null
    private var lastFocus: GeoPoint? = null

    fun update(selected: GeoPoint?, route: RouteOverlay?, focus: GeoPoint?) {
        pendingSelected = selected
        pendingRoute = route
        pendingFocus = focus
        applyPending()
    }

    fun applyPending() {
        val style = style ?: return // style not loaded yet; applied in the callback
        val map = map ?: return

        (style.getSourceAs<GeoJsonSource>(SRC_SELECTED))?.setGeoJson(
            FeatureCollection.fromFeatures(
                pendingSelected?.let {
                    listOf(Feature.fromGeometry(Point.fromLngLat(it.lon, it.lat)))
                } ?: emptyList()
            )
        )

        val route = pendingRoute
        val waypointFeatures = route?.waypoints?.map { waypoint ->
            Feature.fromGeometry(Point.fromLngLat(waypoint.lon, waypoint.lat)).apply {
                // A fast-scan route carries positions with no per-point score;
                // colouring those by score would show a number nobody computed.
                val color = if (route.waypointsAreRiskScored) {
                    riskColorForScore(waypoint.riskScore).toHex()
                } else {
                    UNSCORED_WAYPOINT_COLOR
                }
                addStringProperty("color", color)
            }
        }.orEmpty()

        (style.getSourceAs<GeoJsonSource>(SRC_WAYPOINTS))
            ?.setGeoJson(FeatureCollection.fromFeatures(waypointFeatures))

        val lineFeatures = route?.waypoints
            ?.takeIf { it.size >= 2 }
            ?.map { Point.fromLngLat(it.lon, it.lat) }
            ?.let { listOf(Feature.fromGeometry(LineString.fromLngLats(it))) }
            .orEmpty()

        (style.getSourceAs<GeoJsonSource>(SRC_ROUTE))
            ?.setGeoJson(FeatureCollection.fromFeatures(lineFeatures))

        // Fit the route if there is one; otherwise honour an explicit focus
        // request exactly once (so the camera does not fight the user's pan).
        if (route != null && route.waypoints.size >= 2) {
            val bounds = LatLngBounds.Builder()
                .includes(route.waypoints.map { LatLng(it.lat, it.lon) })
                .build()
            map.easeCamera(CameraUpdateFactory.newLatLngBounds(bounds, 80), 600)
        } else {
            val focus = pendingFocus
            if (focus != null && focus != lastFocus) {
                lastFocus = focus
                map.easeCamera(
                    CameraUpdateFactory.newLatLngZoom(LatLng(focus.lat, focus.lon), 9.0),
                    600,
                )
            }
        }
    }

    private companion object {
        const val UNSCORED_WAYPOINT_COLOR = "#8FA3B8"
    }
}

/** Diagonal hatch tile used as the exclusion fill pattern. */
private fun hatchBitmap(colorHex: String, size: Int = 16): Bitmap {
    val bmp = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
    val canvas = Canvas(bmp)
    val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = AndroidColor.parseColor(colorHex)
        strokeWidth = 2.5f
        style = Paint.Style.STROKE
    }
    val s = size.toFloat()
    // Three strokes so the diagonal tiles seamlessly across the pattern edge.
    canvas.drawLine(0f, s, s, 0f, paint)
    canvas.drawLine(-2f, 2f, 2f, -2f, paint)
    canvas.drawLine(s - 2f, s + 2f, s + 2f, s - 2f, paint)
    return bmp
}

private fun installBoundaryLayers(style: Style) {
    style.addImage(IMG_HATCH, hatchBitmap(EXCLUSION_COLOR))
    style.addSource(GeoJsonSource(SRC_EEZ))
    style.addSource(GeoJsonSource(SRC_MPA))
    style.addSource(GeoJsonSource(SRC_PORTS))

    // India's own EEZ is the PERMITTED area, not a restriction - outline only.
    // A foreign EEZ is where an Indian fisherman gets detained, which is a far
    // more consequential boundary day to day than the high seas.
    style.addLayer(
        LineLayer(LYR_EEZ_PERMITTED, SRC_EEZ)
            .withFilter(Expression.eq(Expression.get("exclusion"), Expression.literal(false)))
            .withProperties(
                PropertyFactory.lineColor(PERMITTED_COLOR),
                PropertyFactory.lineWidth(1.5f),
                PropertyFactory.lineOpacity(0.8f),
            )
    )
    style.addLayer(
        FillLayer(LYR_EEZ_EXCL_FILL, SRC_EEZ)
            .withFilter(Expression.eq(Expression.get("exclusion"), Expression.literal(true)))
            .withProperties(
                PropertyFactory.fillPattern(IMG_HATCH),
                PropertyFactory.fillOpacity(0.55f),
            )
    )
    style.addLayer(
        LineLayer(LYR_EEZ_EXCL_LINE, SRC_EEZ)
            .withFilter(Expression.eq(Expression.get("exclusion"), Expression.literal(true)))
            .withProperties(
                PropertyFactory.lineColor(EXCLUSION_COLOR),
                PropertyFactory.lineWidth(2f),
            )
    )
    style.addLayer(
        FillLayer(LYR_MPA_FILL, SRC_MPA).withProperties(
            PropertyFactory.fillPattern(IMG_HATCH),
            PropertyFactory.fillOpacity(0.75f),
        )
    )
    style.addLayer(
        LineLayer(LYR_MPA_LINE, SRC_MPA).withProperties(
            PropertyFactory.lineColor(EXCLUSION_COLOR),
            PropertyFactory.lineWidth(1.5f),
        )
    )
    style.addLayer(
        CircleLayer(LYR_PORTS, SRC_PORTS).withProperties(
            PropertyFactory.circleRadius(4f),
            PropertyFactory.circleColor("#4F8FE0"),
            PropertyFactory.circleStrokeWidth(1.5f),
            PropertyFactory.circleStrokeColor("#FFFFFF"),
        )
    )
}

private fun installLayers(style: Style) {
    installBoundaryLayers(style)
    style.addSource(GeoJsonSource(SRC_ROUTE))
    style.addSource(GeoJsonSource(SRC_WAYPOINTS))
    style.addSource(GeoJsonSource(SRC_SELECTED))

    style.addLayer(
        LineLayer(LYR_ROUTE, SRC_ROUTE).withProperties(
            PropertyFactory.lineColor("#3ECFA8"),
            PropertyFactory.lineWidth(3.5f),
            PropertyFactory.lineOpacity(0.9f),
        )
    )
    style.addLayer(
        CircleLayer(LYR_WAYPOINTS, SRC_WAYPOINTS).withProperties(
            PropertyFactory.circleRadius(7f),
            PropertyFactory.circleColor(Expression.get("color")),
            PropertyFactory.circleStrokeWidth(2f),
            PropertyFactory.circleStrokeColor("#FFFFFF"),
        )
    )
    style.addLayer(
        CircleLayer(LYR_SELECTED, SRC_SELECTED).withProperties(
            PropertyFactory.circleRadius(9f),
            PropertyFactory.circleColor("#4F8FE0"),
            PropertyFactory.circleStrokeWidth(3f),
            PropertyFactory.circleStrokeColor("#FFFFFF"),
        )
    )
}

private fun androidx.compose.ui.graphics.Color.toHex(): String =
    String.format("#%06X", 0xFFFFFF and toArgb())
