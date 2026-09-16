package com.jaljeev.marine.data.settings

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.doublePreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.jaljeev.marine.BuildConfig
import com.jaljeev.marine.data.remote.ApiClient
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.stateIn

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "jaljeev_settings")

/**
 * Vessel characteristics sent with every marine request.
 *
 * Defaults match the backend's own VesselProfile defaults (a typical small
 * Indian fishing boat, the PRD's "8-metre boat at Puri" case) so an
 * unconfigured app behaves identically to the web client.
 */
data class VesselProfile(
    val lengthM: Double = 8.0,
    val maxSafeWaveM: Double = 1.5,
    val windThresholdMs: Double = 12.0,
    val operationalRangeKm: Double = 40.0,
)

data class AppSettings(
    val baseUrl: String = BuildConfig.DEFAULT_API_BASE,
    val vessel: VesselProfile = VesselProfile(),
    val monitorIntervalSeconds: Int = 15,
    val attachLocationToChat: Boolean = true,
)

class SettingsRepository(
    private val context: Context,
    scope: CoroutineScope,
) {
    private object Keys {
        val BASE_URL = stringPreferencesKey("base_url")
        val VESSEL_LENGTH = doublePreferencesKey("vessel_length_m")
        val VESSEL_WAVE = doublePreferencesKey("vessel_max_safe_wave_m")
        val VESSEL_WIND = doublePreferencesKey("vessel_wind_threshold_ms")
        val VESSEL_RANGE = doublePreferencesKey("vessel_operational_range_km")
        val MONITOR_INTERVAL = intPreferencesKey("monitor_interval_seconds")
        val ATTACH_LOCATION = booleanPreferencesKey("attach_location_to_chat")
    }

    private val flow: Flow<AppSettings> = context.dataStore.data.map { prefs ->
        AppSettings(
            baseUrl = prefs[Keys.BASE_URL] ?: BuildConfig.DEFAULT_API_BASE,
            vessel = VesselProfile(
                lengthM = prefs[Keys.VESSEL_LENGTH] ?: 8.0,
                maxSafeWaveM = prefs[Keys.VESSEL_WAVE] ?: 1.5,
                windThresholdMs = prefs[Keys.VESSEL_WIND] ?: 12.0,
                operationalRangeKm = prefs[Keys.VESSEL_RANGE] ?: 40.0,
            ),
            monitorIntervalSeconds = prefs[Keys.MONITOR_INTERVAL] ?: 15,
            attachLocationToChat = prefs[Keys.ATTACH_LOCATION] ?: true,
        )
    }.onEach { settings ->
        // Single place the HTTP layer learns about a URL change - no screen
        // has to remember to push it, and a restart picks it up on first read.
        ApiClient.setBaseUrl(settings.baseUrl)
    }

    val settings: StateFlow<AppSettings> =
        flow.stateIn(scope, SharingStarted.Eagerly, AppSettings())

    suspend fun setBaseUrl(url: String) = context.dataStore.edit { it[Keys.BASE_URL] = url.trim() }

    suspend fun setVessel(profile: VesselProfile) = context.dataStore.edit {
        it[Keys.VESSEL_LENGTH] = profile.lengthM
        it[Keys.VESSEL_WAVE] = profile.maxSafeWaveM
        it[Keys.VESSEL_WIND] = profile.windThresholdMs
        it[Keys.VESSEL_RANGE] = profile.operationalRangeKm
    }

    suspend fun setMonitorInterval(seconds: Int) = context.dataStore.edit {
        it[Keys.MONITOR_INTERVAL] = seconds.coerceIn(10, 300)
    }

    suspend fun setAttachLocationToChat(enabled: Boolean) = context.dataStore.edit {
        it[Keys.ATTACH_LOCATION] = enabled
    }
}
