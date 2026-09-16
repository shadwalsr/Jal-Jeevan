package com.jaljeev.marine.ui.common

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.jaljeev.marine.data.remote.FusedMarineState
import com.jaljeev.marine.data.remote.RiskAssessment
import com.jaljeev.marine.domain.GeoPoint
import com.jaljeev.marine.domain.RiskLevel

/**
 * The full fused state for one point, as returned by /marine/state.
 *
 * Every value is either a real reading or an explicit "not available" - see
 * [Reading]. Nothing here fills a gap with a default, because a fabricated
 * 0 m wave height reads exactly like a calm sea.
 */
@Composable
fun MarineStateDetails(
    state: FusedMarineState,
    modifier: Modifier = Modifier,
) {
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(10.dp)) {

        RiskSection(state.risk, GeoPoint(state.lat, state.lon))

        SectionCard(title = "Weather") {
            val w = state.weather
            Reading("Wind", w.windSpeedMs.reading("m/s"))
            Reading("Gusts", w.windGustMs.reading("m/s"))
            Reading("Wind direction", w.windDirectionDeg.reading("°", decimals = 0))
            Reading("Pressure", w.pressureMslHpa.reading("hPa"))
            Reading("3 h pressure trend", w.pressureTrendHpa3h?.let { String.format("%+.1f hPa", it) })
            Reading("Rain probability", w.precipitationProbability.reading("%", decimals = 0))
            Reading("Rain (24 h)", w.rainfallMm24h.reading("mm"))
            Reading("Air temperature", w.temperature2mC.reading("°C"))
            Reading("Visibility", w.visibilityM.reading("m", decimals = 0))
            if (w.fogRisk) Flag("Fog risk flagged")
            if (w.cycloneActive) Flag("Cyclone activity flagged", severe = true)
            Provenance(w.sourcesUsed, w.missing)
        }

        SectionCard(title = "Ocean") {
            val o = state.ocean
            Reading("Significant wave height", o.significantWaveHeightM.reading("m", decimals = 2))
            Reading("Wave period", o.wavePeriodS.reading("s"))
            Reading("Swell", o.swellHeightM.reading("m", decimals = 2))
            Reading("Wind wave", o.windWaveHeightM.reading("m", decimals = 2))
            if (o.crossSwell) Flag("Cross swell: swell and wind wave from different directions")
            Reading("Surface current", o.currentSpeedMs.reading("m/s", decimals = 2))
            Reading("Tide height", o.tideHeightM.reading("m", decimals = 2))
            Reading("Tide state", o.tideState)
            Reading("Sea surface temperature", (o.sstConsensus ?: o.sstC).reading("°C"))
            Reading("Source disagreement", o.sstDisagreement.reading("°C", decimals = 2))
            Reading("Salinity", o.salinityPsu.reading("PSU", decimals = 2))
            Reading("Chlorophyll", o.chlorophyllMgM3.reading("mg/m³", decimals = 2))
            if (o.habRisk) Flag("Harmful algal bloom proxy triggered")

            if (o.sstAnomaly) {
                Flag("SST anomaly (z = ${o.sstAnomalyZScore?.let { String.format("%.2f", it) } ?: "?"})")
            }
            // CLAUDE.md is explicit that the single-year-baseline caveat must
            // never be dropped by a UI surfacing the anomaly. Rendered
            // verbatim, exactly as the Anomaly Agent wrote it.
            o.sstAnomalyNote?.takeIf { it.isNotBlank() }?.let { note ->
                Text(
                    note,
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.tertiary,
                )
            }
            Provenance(o.sourcesUsed, o.missing)
        }

        SectionCard(title = "Position") {
            val g = state.geo
            Reading("Inside Indian EEZ", if (g.insideIndianEez) "yes" else "no")
            Reading("EEZ territory", g.eezTerritory)
            Reading("Inside protected area", if (g.insideMpa) "yes - ${g.mpaName ?: "unnamed MPA"}" else "no")
            Reading("Nearest port", g.nearestPortName)
            Reading("Distance to port", g.nearestPortDistanceKm.reading("km"))
            Reading("Depth", g.depthM.reading("m", decimals = 0))
            if (g.isLand) Flag("This point is on land", severe = true)
            if (g.missing.isNotEmpty()) Provenance(emptyList(), g.missing)
        }

        SectionCard(title = "Confidence") {
            Text(state.confidenceNote, style = MaterialTheme.typography.bodyMedium)
            if (!state.validation.valid || state.validation.issues.isNotEmpty()) {
                Text(
                    "Validation issues",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.error,
                )
                BulletList(state.validation.issues, color = MaterialTheme.colorScheme.error)
            }
            Reading("Queried at", state.queriedAt)
        }
    }
}

@Composable
fun RiskSection(risk: RiskAssessment, point: GeoPoint?, modifier: Modifier = Modifier) {
    val level = RiskLevel.from(risk.riskLevel)
    SectionCard(title = "Assessment", modifier = modifier) {
        if (point != null) Text(point.format(), style = MaterialTheme.typography.titleMedium)
        RiskBadge(level = level, score = risk.riskScore)

        if (risk.hardConstraints.vetoed) {
            // Stage 1. These are not "very bad scores" - they are reasons the
            // candidate was never scored at all.
            Text(
                "Vetoed before scoring:",
                style = MaterialTheme.typography.labelMedium,
                color = RiskLevel.Rejected.color,
            )
            BulletList(risk.hardConstraints.reasons, color = RiskLevel.Rejected.color)
        }

        if (risk.insufficientConfidence) {
            Text(
                risk.confidenceReason ?: "Not enough data to score this point.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.tertiary,
            )
        }

        if (risk.explanation.isNotEmpty()) {
            BulletList(risk.explanation)
        }

        if (risk.factorBreakdown.isNotEmpty()) {
            ExpandableSection("Score breakdown") {
                risk.factorBreakdown.forEach { (factor, points) ->
                    Reading(factor, "+$points")
                }
            }
        }
    }
}

@Composable
private fun Flag(text: String, severe: Boolean = false) {
    Text(
        text,
        style = MaterialTheme.typography.bodyMedium,
        color = if (severe) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.tertiary,
    )
}

@Composable
private fun Provenance(sources: List<String>, missing: List<String>) {
    if (sources.isNotEmpty()) {
        ExpandableSection("Sources (${sources.size})") { TagRow(sources) }
    }
    if (missing.isNotEmpty()) {
        Text(
            "Not available: ${missing.joinToString(", ")}",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.tertiary,
        )
    }
}
