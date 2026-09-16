package com.jaljeev.marine.ui.route

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Map
import androidx.compose.material.icons.filled.MyLocation
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.jaljeev.marine.R
import com.jaljeev.marine.appContainer
import com.jaljeev.marine.data.remote.OptimizedRoute
import com.jaljeev.marine.data.remote.RouteRecommendation
import com.jaljeev.marine.domain.GeoPoint
import com.jaljeev.marine.domain.RiskLevel
import com.jaljeev.marine.ui.common.BulletList
import com.jaljeev.marine.ui.common.ErrorCard
import com.jaljeev.marine.ui.common.ExpandableSection
import com.jaljeev.marine.ui.common.LoadingRow
import com.jaljeev.marine.ui.common.Reading
import com.jaljeev.marine.ui.common.RiskBadge
import com.jaljeev.marine.ui.common.RiskSection
import com.jaljeev.marine.ui.common.SectionCard

@Composable
fun RouteScreen(modifier: Modifier = Modifier) {
    val container = LocalContext.current.appContainer
    val vm: RouteViewModel = viewModel(factory = RouteViewModel.factory(container))
    val ui by vm.ui.collectAsStateWithLifecycle()

    Column(
        modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {

        SectionCard(title = stringResource(R.string.route_origin)) {
            Text(
                ui.origin?.format() ?: "No origin set",
                style = MaterialTheme.typography.titleMedium,
            )
            Text(
                "Tap a point on the Map tab to set this, or use your current position.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            OutlinedButton(onClick = vm::useMyLocation) {
                Icon(Icons.Filled.MyLocation, contentDescription = null)
                Text(stringResource(R.string.map_my_location), Modifier.padding(start = 6.dp))
            }
        }

        SectionCard(title = stringResource(R.string.route_range)) {
            Text("${ui.rangeKm.toInt()} km", style = MaterialTheme.typography.titleMedium)
            Slider(
                value = ui.rangeKm,
                onValueChange = vm::setRange,
                // 200 km is the graph search's server-side ceiling; keeping the
                // control inside it means the user cannot compose a request the
                // backend will reject with a 400.
                valueRange = 5f..200f,
                steps = 38,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = vm::findSafestZone,
                    enabled = ui.origin != null && ui.running == null,
                ) { Text(stringResource(R.string.route_find_safest)) }
                Button(
                    onClick = vm::optimizeRoute,
                    enabled = ui.origin != null && ui.running == null,
                ) { Text(stringResource(R.string.route_optimize)) }
            }
        }

        when (ui.running) {
            RouteMode.SafestZone -> LoadingRow("Scanning 16 candidate zones…")
            RouteMode.Optimized -> LoadingRow("A* over the H3 risk graph - this can take up to 90 s…")
            null -> Unit
        }

        ui.error?.let { ErrorCard(it, ui.errorDetail) }

        ui.recommendation?.let { RecommendationResult(it, onShowOnMap = vm::showOnMap) }
        ui.optimized?.let { OptimizedResult(it, onShowOnMap = vm::showOnMap) }
    }
}

@Composable
private fun RecommendationResult(result: RouteRecommendation, onShowOnMap: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        SectionCard(title = "Recommendation") {
            Text(result.recommendation, style = MaterialTheme.typography.bodyLarge)
            Reading("Destination", result.destinationLat?.let { lat ->
                result.destinationLon?.let { lon -> GeoPoint(lat, lon).format() }
            })
            Reading("Distance", result.distanceKm?.let { String.format("%.1f km", it) })
            Reading("Bearing", result.bearingDeg?.let { String.format("%.0f°", it) })
            if (result.destinationLat != null) {
                OutlinedButton(onClick = onShowOnMap) {
                    Icon(Icons.Filled.Map, contentDescription = null)
                    Text(stringResource(R.string.evidence_show_on_map), Modifier.padding(start = 6.dp))
                }
            }
        }

        result.destinationRisk?.let { risk ->
            RiskSection(
                risk,
                result.destinationLat?.let { lat ->
                    result.destinationLon?.let { lon -> GeoPoint(lat, lon) }
                },
            )
        }

        if (result.candidatesEvaluated.isNotEmpty()) {
            SectionCard(title = stringResource(R.string.route_candidates)) {
                // The "why not?" list. Rejected candidates are shown with the
                // constraint that vetoed them, not hidden - a recommendation
                // is only trustworthy if the alternatives it discarded are
                // visible too.
                ExpandableSection(
                    "${result.candidatesEvaluated.size} zones scored, " +
                        "${result.candidatesEvaluated.count { it.rejected }} vetoed",
                    initiallyExpanded = true,
                ) {
                    result.candidatesEvaluated.forEach { candidate ->
                        Column(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                            Row(
                                Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                            ) {
                                Text(
                                    "${String.format("%.0f", candidate.distanceFromOriginKm)} km " +
                                        "at ${String.format("%.0f", candidate.bearingDeg)}°",
                                    style = MaterialTheme.typography.bodyMedium,
                                )
                                RiskBadge(
                                    level = RiskLevel.from(candidate.riskLevel),
                                    score = candidate.riskScore,
                                )
                            }
                            candidate.rejectionReason?.let {
                                Text(
                                    it,
                                    style = MaterialTheme.typography.labelMedium,
                                    color = RiskLevel.Rejected.color,
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun OptimizedResult(result: OptimizedRoute, onShowOnMap: () -> Unit) {
    SectionCard(title = "A* route") {
        if (!result.foundRoute) {
            Text(
                result.reason ?: "No viable route was found.",
                style = MaterialTheme.typography.bodyLarge,
                color = RiskLevel.Rejected.color,
            )
        } else {
            Text(
                "Route found across ${result.waypoints.size} waypoints.",
                style = MaterialTheme.typography.bodyLarge,
            )
        }
        Reading("Cells evaluated", result.cellsEvaluated.toString())
        Reading(
            "Cells viable after vetoes",
            "${result.cellsViable} of ${result.cellsEvaluated}",
        )
        Reading("Total risk cost", result.totalRiskCost?.let { String.format("%.1f", it) })

        if (result.waypoints.isNotEmpty()) {
            ExpandableSection(stringResource(R.string.route_waypoints)) {
                result.waypoints.forEachIndexed { index, waypoint ->
                    Reading(
                        "${index + 1}. ${GeoPoint(waypoint.lat, waypoint.lon).format()}",
                        "risk ${waypoint.riskScore}/100",
                    )
                }
            }
            OutlinedButton(onClick = onShowOnMap) {
                Icon(Icons.Filled.Map, contentDescription = null)
                Text(stringResource(R.string.evidence_show_on_map), Modifier.padding(start = 6.dp))
            }
        }

        if (!result.foundRoute && result.cellsViable == 0 && result.cellsEvaluated > 0) {
            BulletList(
                listOf(
                    "Every cell in range was vetoed by a hard constraint - " +
                        "that is a legal or survivability answer, not a search failure."
                ),
                color = RiskLevel.Rejected.color,
            )
        }
    }
}
