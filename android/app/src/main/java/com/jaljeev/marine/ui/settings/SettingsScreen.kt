package com.jaljeev.marine.ui.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.jaljeev.marine.appContainer
import com.jaljeev.marine.data.settings.VesselProfile
import com.jaljeev.marine.domain.ApiOutcome
import com.jaljeev.marine.ui.common.SectionCard
import kotlinx.coroutines.launch

@Composable
fun SettingsScreen(modifier: Modifier = Modifier) {
    val container = LocalContext.current.appContainer
    val settings by container.settings.settings.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()

    var baseUrl by remember(settings.baseUrl) { mutableStateOf(settings.baseUrl) }
    var testResult by remember { mutableStateOf<String?>(null) }
    var testing by remember { mutableStateOf(false) }

    var length by remember(settings.vessel) { mutableStateOf(settings.vessel.lengthM.toString()) }
    var wave by remember(settings.vessel) { mutableStateOf(settings.vessel.maxSafeWaveM.toString()) }
    var wind by remember(settings.vessel) { mutableStateOf(settings.vessel.windThresholdMs.toString()) }
    var range by remember(settings.vessel) { mutableStateOf(settings.vessel.operationalRangeKm.toString()) }
    var vesselError by remember { mutableStateOf<String?>(null) }

    Column(
        modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {

        SectionCard(title = "Backend") {
            OutlinedTextField(
                value = baseUrl,
                onValueChange = { baseUrl = it; testResult = null },
                label = { Text("Base URL") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
            )
            Text(
                "The FastAPI server from the repo root: uvicorn app.main:app --port 8000. " +
                    "Use 10.0.2.2 from the emulator, or the laptop's LAN IP from a real phone " +
                    "(and start uvicorn with --host 0.0.0.0 so it accepts connections from it).",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = {
                    scope.launch {
                        container.settings.setBaseUrl(baseUrl)
                        testing = true
                        testResult = null
                        testResult = when (val outcome = container.repository.health()) {
                            is ApiOutcome.Ok -> "Connected. /health says \"${outcome.value}\"."
                            is ApiOutcome.Err -> "${outcome.message}\n${outcome.detail.orEmpty()}"
                        }
                        testing = false
                    }
                }) { Text(if (testing) "Testing…" else "Save and test") }

                OutlinedButton(onClick = { baseUrl = "http://10.0.2.2:8000" }) {
                    Text("Emulator default")
                }
            }
            testResult?.let {
                Text(it, style = MaterialTheme.typography.bodyMedium)
            }
        }

        SectionCard(title = "Vessel") {
            Text(
                "Sent with every request. The hard constraints are vessel-relative: " +
                    "a wave height that vetoes an 8 m open boat does not veto a trawler, " +
                    "and depth is checked against your draft.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            NumberField("Length (m)", length) { length = it }
            NumberField("Max safe wave height (m)", wave) { wave = it }
            NumberField("Wind threshold (m/s)", wind) { wind = it }
            NumberField("Operational range (km)", range) { range = it }
            vesselError?.let {
                Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.error)
            }
            Button(onClick = {
                // Validated against the same bounds the backend enforces, so a
                // bad value is caught here instead of coming back as a 400.
                val parsed = parseVessel(length, wave, wind, range)
                if (parsed == null) {
                    vesselError = "Enter numbers within: length 0-200 m, wave 0-20 m, " +
                        "wind 0-60 m/s, range 0-2000 km."
                } else {
                    vesselError = null
                    scope.launch { container.settings.setVessel(parsed) }
                }
            }) { Text("Save vessel") }
        }

        SectionCard(title = "Safety watch") {
            Text(
                "Check interval: ${settings.monitorIntervalSeconds} s",
                style = MaterialTheme.typography.titleMedium,
            )
            Slider(
                value = settings.monitorIntervalSeconds.toFloat(),
                onValueChange = { scope.launch { container.settings.setMonitorInterval(it.toInt()) } },
                valueRange = 10f..120f,
                steps = 21,
            )
            Text(
                "The backend rate-limits each client to 60 requests a minute, shared with " +
                    "everything else the app does. Below about 10 s the watch alone can " +
                    "reach that ceiling.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        SectionCard(title = "About") {
            Text(
                "JalJeev - agentic marine intelligence (SIH26176). This app is a native " +
                    "client: every number it shows was computed by the deterministic agents " +
                    "in the backend, never by a language model, and anything a source could " +
                    "not supply is shown as \"not available\" rather than filled in.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun NumberField(label: String, value: String, onChange: (String) -> Unit) {
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        label = { Text(label) },
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
    )
}

private fun parseVessel(length: String, wave: String, wind: String, range: String): VesselProfile? {
    val l = length.trim().toDoubleOrNull() ?: return null
    val wv = wave.trim().toDoubleOrNull() ?: return null
    val wd = wind.trim().toDoubleOrNull() ?: return null
    val r = range.trim().toDoubleOrNull() ?: return null
    if (l <= 0 || l > 200) return null
    if (wv <= 0 || wv > 20) return null
    if (wd <= 0 || wd > 60) return null
    if (r <= 0 || r > 2000) return null
    return VesselProfile(lengthM = l, maxSafeWaveM = wv, windThresholdMs = wd, operationalRangeKm = r)
}
