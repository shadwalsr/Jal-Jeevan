package com.jaljeev.marine.ui.monitor

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.jaljeev.marine.R
import com.jaljeev.marine.appContainer
import com.jaljeev.marine.domain.GeoPoint
import com.jaljeev.marine.domain.RiskLevel
import com.jaljeev.marine.safety.SafetyMonitorService
import com.jaljeev.marine.safety.SafetyWatch
import com.jaljeev.marine.ui.common.BulletList
import com.jaljeev.marine.ui.common.ErrorCard
import com.jaljeev.marine.ui.common.Reading
import com.jaljeev.marine.ui.common.RiskBadge
import com.jaljeev.marine.ui.common.SectionCard
import com.jaljeev.marine.ui.common.formatAge
import kotlinx.coroutines.delay

/**
 * The live watch: conditions where the vessel actually is, re-checked on a
 * fixed interval while under way.
 *
 * The in-app banner here is the guaranteed channel - OS notifications are a
 * bonus that a denied POST_NOTIFICATIONS permission can take away, so this
 * screen always shows the full current verdict itself.
 */
@Composable
fun MonitorScreen(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val container = context.appContainer
    val watch by SafetyWatch.state.collectAsStateWithLifecycle()
    val settings by container.settings.settings.collectAsStateWithLifecycle()

    // Re-renders the "checked N ago" line once a second without touching the
    // watch state itself.
    val now by produceState(System.currentTimeMillis()) {
        while (true) {
            value = System.currentTimeMillis()
            delay(1_000)
        }
    }

    val notificationLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* denied is survivable: the in-app banner still works */ }

    val locationLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted -> if (granted) SafetyMonitorService.start(context) }

    Column(
        modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {

        SectionCard(title = stringResource(R.string.monitor_title)) {
            val result = watch.lastResult
            if (result == null) {
                Text(
                    if (watch.running) "Waiting for the first check…" else "Not running.",
                    style = MaterialTheme.typography.titleMedium,
                )
            } else {
                RiskBadge(level = RiskLevel.from(result.riskLevel), score = result.riskScore)
                Text(
                    GeoPoint(result.lat, result.lon).format(),
                    style = MaterialTheme.typography.titleMedium,
                )
                watch.lastCheckedAtMillis?.let { checkedAt ->
                    Reading("Last checked", "${formatAge(now - checkedAt)} ago")
                }

                if (result.vetoed) {
                    Text(
                        "Do not continue here:",
                        style = MaterialTheme.typography.labelMedium,
                        color = RiskLevel.Rejected.color,
                    )
                    BulletList(result.reasons, color = RiskLevel.Rejected.color)
                } else if (result.explanation.isNotEmpty()) {
                    BulletList(result.explanation)
                }

                if (result.insufficientConfidence) {
                    Text(
                        result.confidenceReason
                            ?: "Not enough data to judge this position confidently.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.tertiary,
                    )
                }
            }
        }

        watch.lastError?.let { message ->
            // A failed check is reported as a failed check. It is never
            // allowed to look like an all-clear.
            ErrorCard(
                "Last check failed - the verdict above (if any) is not current.",
                "$message (${watch.consecutiveFailures} consecutive failures)",
            )
        }

        SectionCard(title = "How this works") {
            Text(
                "While running, JalJeev takes your position every " +
                    "${settings.monitorIntervalSeconds} seconds and re-runs the same " +
                    "hard-constraint and risk checks used everywhere else in the app, " +
                    "then warns you the moment conditions where you actually are turn unsafe.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                "It keeps running with the screen off. That needs a persistent " +
                    "notification, which Android shows while the watch is active.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            watch.position?.let { Reading("Current position", it.format()) }
        }

        Button(
            onClick = {
                if (watch.running) {
                    SafetyMonitorService.stop(context)
                } else {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        notificationLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                    }
                    if (container.locationProvider.hasPermission()) {
                        SafetyMonitorService.start(context)
                    } else {
                        locationLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
                    }
                }
            },
            modifier = Modifier.fillMaxWidth(),
            colors = if (watch.running) {
                ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
            } else {
                ButtonDefaults.buttonColors()
            },
        ) {
            Text(
                stringResource(if (watch.running) R.string.monitor_stop else R.string.monitor_start)
            )
        }
    }
}
