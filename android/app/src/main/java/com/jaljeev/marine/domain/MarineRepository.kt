package com.jaljeev.marine.domain

import android.util.Log
import com.jaljeev.marine.data.cache.MarineStateCache
import com.jaljeev.marine.data.remote.ApiClient
import com.jaljeev.marine.data.remote.ChatRequest
import com.jaljeev.marine.data.remote.ChatResponse
import com.jaljeev.marine.data.remote.FusedMarineState
import com.jaljeev.marine.data.remote.OptimizedRoute
import com.jaljeev.marine.data.remote.QuickCheckResult
import com.jaljeev.marine.data.remote.RouteRecommendation
import com.jaljeev.marine.data.remote.SimulationResult
import com.jaljeev.marine.data.settings.SettingsRepository
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.withTimeout
import retrofit2.HttpException
import java.io.IOException

/** Result of one backend call. `staleAgeMillis != null` means it came from cache. */
sealed interface ApiOutcome<out T> {
    data class Ok<T>(val value: T, val staleAgeMillis: Long? = null) : ApiOutcome<T>
    data class Err(val message: String, val detail: String? = null) : ApiOutcome<Nothing>
}

/**
 * Every network call the UI makes goes through here.
 *
 * The one rule this class exists to enforce: a failure is reported as a
 * failure, with the exception type and message intact (CLAUDE.md gotcha #4 -
 * a bare `catch { return null }` in this project once hid an instant HTTP 429
 * behind two debugging sessions' worth of "it's probably just slow"). No
 * method here ever returns a plausible-looking substitute for data it did
 * not receive.
 */
class MarineRepository(
    private val settings: SettingsRepository,
    private val cache: MarineStateCache,
) {
    private val api get() = ApiClient.api
    private val vessel get() = settings.settings.value.vessel

    /** Exclusion layers for the current viewport. Cached hard server-side. */
    suspend fun boundaries(
        minLat: Double, minLon: Double, maxLat: Double, maxLon: Double,
    ): ApiOutcome<kotlinx.serialization.json.JsonObject> = call("map/boundaries") {
        withTimeout(20_000) { api.boundaries(minLat, minLon, maxLat, maxLon) }
    }

    suspend fun health(): ApiOutcome<String> = call("health") {
        withTimeout(10_000) { api.health().status }
    }

    suspend fun chat(
        message: String,
        sessionId: String?,
        clientLat: Double?,
        clientLon: Double?,
    ): ApiOutcome<ChatResponse> = call("chat") {
        api.chat(ChatRequest(message, sessionId, clientLat, clientLon))
    }

    /**
     * Full multi-source state. Falls back to the last cached answer for this
     * point when the network fails - returned with its age so the UI can
     * label it as not-live rather than passing it off as current.
     */
    suspend fun marineState(lat: Double, lon: Double): ApiOutcome<FusedMarineState> {
        val live = call("marine/state") {
            api.marineState(
                lat, lon,
                vessel.lengthM, vessel.maxSafeWaveM, vessel.windThresholdMs, vessel.operationalRangeKm,
            )
        }
        if (live is ApiOutcome.Ok) {
            cache.put(live.value)
            return live
        }
        val cached = cache.get(lat, lon)
        return if (cached != null) {
            ApiOutcome.Ok(cached.first, staleAgeMillis = cached.second)
        } else {
            live
        }
    }

    /**
     * The live safety poll. Tighter deadline than the shared client timeout
     * because the backend caps this endpoint at 15 s itself, and a stalled
     * poll would silently stop the watch from updating.
     *
     * No cache fallback here on purpose - see MarineStateCache's docs.
     */
    suspend fun quickCheck(lat: Double, lon: Double): ApiOutcome<QuickCheckResult> = call("quick-check") {
        withTimeout(25_000) {
            api.quickCheck(
                lat, lon,
                vessel.lengthM, vessel.maxSafeWaveM, vessel.windThresholdMs, vessel.operationalRangeKm,
            )
        }
    }

    suspend fun safestRoute(lat: Double, lon: Double, rangeKm: Double): ApiOutcome<RouteRecommendation> =
        call("safest-route") {
            api.safestRoute(
                lat, lon, rangeKm,
                vessel.lengthM, vessel.maxSafeWaveM, vessel.windThresholdMs, vessel.operationalRangeKm,
            )
        }

    suspend fun optimizeRoute(lat: Double, lon: Double, rangeKm: Double): ApiOutcome<OptimizedRoute> =
        call("optimize-route") {
            api.optimizeRoute(
                lat, lon, rangeKm,
                vessel.lengthM, vessel.maxSafeWaveM, vessel.windThresholdMs, vessel.operationalRangeKm,
            )
        }

    suspend fun simulateTimeShift(lat: Double, lon: Double, hoursLater: Int): ApiOutcome<SimulationResult> =
        call("simulate/time-shift") {
            api.simulateTimeShift(
                lat, lon, hoursLater,
                vessel.lengthM, vessel.maxSafeWaveM, vessel.windThresholdMs, vessel.operationalRangeKm,
            )
        }

    suspend fun simulateWavePerturbation(lat: Double, lon: Double, multiplier: Double): ApiOutcome<SimulationResult> =
        call("simulate/wave-perturbation") {
            api.simulateWavePerturbation(
                lat, lon, multiplier,
                vessel.lengthM, vessel.maxSafeWaveM, vessel.windThresholdMs, vessel.operationalRangeKm,
            )
        }

    private suspend inline fun <T> call(label: String, block: () -> T): ApiOutcome<T> = try {
        ApiOutcome.Ok(block())
    } catch (exc: TimeoutCancellationException) {
        Log.w(TAG, "$label timed out client-side")
        ApiOutcome.Err(
            "The backend did not answer in time.",
            "$label: client-side timeout. The server may still be fetching a slow source."
        )
    } catch (exc: HttpException) {
        val body = runCatching { exc.response()?.errorBody()?.string() }.getOrNull()
        Log.w(TAG, "$label failed: HTTP ${exc.code()} $body")
        ApiOutcome.Err(httpMessage(exc.code()), "$label: HTTP ${exc.code()} ${body.orEmpty()}".trim())
    } catch (exc: IOException) {
        Log.w(TAG, "$label failed: ${exc.javaClass.simpleName}: ${exc.message}")
        ApiOutcome.Err(
            "Cannot reach the backend at ${ApiClient.currentBaseUrl()}.",
            "$label: ${exc.javaClass.simpleName}: ${exc.message}"
        )
    } catch (exc: Exception) {
        // Includes serialization failures - a schema drift between app and
        // backend should say so loudly, not look like an empty result.
        Log.e(TAG, "$label failed: ${exc.javaClass.simpleName}: ${exc.message}", exc)
        ApiOutcome.Err(
            "Unexpected error talking to the backend.",
            "$label: ${exc.javaClass.simpleName}: ${exc.message}"
        )
    }

    private fun httpMessage(code: Int): String = when (code) {
        400 -> "The backend rejected those parameters."
        429 -> "Rate limited by the backend (it allows 60 requests a minute per client)."
        502, 503 -> "The backend is up but a data source it needs is not."
        504 -> "The backend timed out fetching a source. Try again shortly."
        else -> "Backend returned HTTP $code."
    }

    private companion object {
        const val TAG = "MarineRepository"
    }
}
