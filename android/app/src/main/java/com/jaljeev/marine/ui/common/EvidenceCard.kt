package com.jaljeev.marine.ui.common

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Map
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.jaljeev.marine.R
import com.jaljeev.marine.data.remote.EvidenceReceipt
import com.jaljeev.marine.domain.GeoPoint
import com.jaljeev.marine.domain.RiskLevel

/**
 * The evidence receipt, rendered field by field.
 *
 * This is the whole point of the product: the answer text above it is a
 * phrasing of this object, and everything here was computed deterministically
 * before any language model saw it. So nothing in this card is summarised,
 * re-worded, or quietly dropped - in particular [EvidenceReceipt.dataGaps]
 * gets its own visible section rather than being hidden behind a toggle,
 * because "what we did not know" is part of the answer.
 */
@Composable
fun EvidenceCard(
    evidence: EvidenceReceipt,
    modifier: Modifier = Modifier,
    onShowOnMap: ((GeoPoint) -> Unit)? = null,
) {
    if (evidence.isEmpty) return
    val context = LocalContext.current
    val level = RiskLevel.from(evidence.riskLevel)

    SectionCard(
        title = stringResource(R.string.evidence_title),
        modifier = modifier,
    ) {
        if (evidence.riskLevel != null) {
            RiskBadge(level = level, score = evidence.riskScore)
        }

        if (evidence.recommendationSummary.isNotBlank()) {
            Text(
                evidence.recommendationSummary,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface,
            )
        }

        if (evidence.factorLines.isNotEmpty()) {
            Text(
                stringResource(R.string.evidence_factors).uppercase(),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            BulletList(evidence.factorLines, isMonospace = true)
        } else if (level.isVeto) {
            Text(
                "Vetoed by a hard constraint, so no risk score was computed — scoring only runs on candidates that pass legal and survivability checks.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.error,
            )
        }

        if (evidence.dataGaps.isNotEmpty()) {
            Text(
                stringResource(R.string.evidence_gaps).uppercase(),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.tertiary,
            )
            BulletList(evidence.dataGaps, color = MaterialTheme.colorScheme.tertiary, isMonospace = false)
        }

        if (evidence.rejectedAlternatives.isNotEmpty()) {
            ExpandableSection(stringResource(R.string.evidence_rejected)) {
                BulletList(evidence.rejectedAlternatives, color = MaterialTheme.colorScheme.onSurfaceVariant, isMonospace = true)
            }
        }

        if (evidence.sourcesUsed.isNotEmpty()) {
            ExpandableSection(
                "${stringResource(R.string.evidence_sources)} (${evidence.sourcesUsed.size})"
            ) {
                TagRow(evidence.sourcesUsed)
                if (evidence.dataFreshness.isNotEmpty()) {
                    Text(
                        stringResource(R.string.evidence_freshness).uppercase(),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 4.dp),
                    )
                    evidence.dataFreshness.forEach { (key, value) -> Reading(key, value) }
                }
            }
        }

        if (evidence.confidenceStatement.isNotBlank()) {
            Text(
                evidence.confidenceStatement,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        evidence.validationNote?.takeIf { it.isNotBlank() }?.let { note ->
            Text(
                "${stringResource(R.string.evidence_validation)}: $note",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.error,
            )
        }

        val lat = evidence.locationLat
        val lon = evidence.locationLon
        if (lat != null && lon != null) {
            Reading("Coordinates", GeoPoint(lat, lon).format())
            Row(
                Modifier.fillMaxWidth().padding(top = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                if (onShowOnMap != null) {
                    OutlinedButton(
                        onClick = { onShowOnMap(GeoPoint(lat, lon)) },
                        shape = androidx.compose.foundation.shape.RoundedCornerShape(3.dp),
                    ) {
                        Icon(Icons.Filled.Map, contentDescription = null, modifier = Modifier.size(16.dp))
                        Text(
                            stringResource(R.string.evidence_show_on_map),
                            style = MaterialTheme.typography.labelMedium,
                            modifier = Modifier.padding(start = 6.dp),
                        )
                    }
                }
                evidence.locationMapsUrl?.let { url ->
                    OutlinedButton(
                        onClick = {
                            runCatching {
                                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                            }
                        },
                        shape = androidx.compose.foundation.shape.RoundedCornerShape(3.dp),
                    ) {
                        Icon(Icons.AutoMirrored.Filled.OpenInNew, contentDescription = null, modifier = Modifier.size(16.dp))
                        Text(
                            stringResource(R.string.evidence_open_maps),
                            style = MaterialTheme.typography.labelMedium,
                            modifier = Modifier.padding(start = 6.dp),
                        )
                    }
                }
            }
        }

        evidence.decisionId?.let {
            Text(
                "Decision $it",
                style = MaterialTheme.typography.labelSmall,
                fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace,
                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f),
            )
        }
    }
}
