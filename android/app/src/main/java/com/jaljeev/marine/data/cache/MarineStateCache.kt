package com.jaljeev.marine.data.cache

import android.content.Context
import android.util.Log
import com.jaljeev.marine.data.remote.ApiClient
import com.jaljeev.marine.data.remote.FusedMarineState
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import java.io.File
import kotlin.math.roundToInt

/**
 * Last-known-good store for /marine/state, so a boat that loses signal can
 * still see what it was told the last time it had one.
 *
 * Deliberate limits, both following from "never fabricate data":
 *
 *  - A cached entry is only ever returned WITH its age, and the UI is
 *    required to label it (see StaleDataBanner). It is never silently
 *    substituted for a live answer.
 *  - The live safety monitor does NOT read this cache. A quick-check exists
 *    to answer "is it safe where I am right now"; handing back a
 *    twenty-minute-old verdict there would be worse than saying nothing,
 *    which is why MarineRepository.quickCheck reports the failure instead.
 */
class MarineStateCache(context: Context) {

    private val dir = File(context.cacheDir, "marine_state").apply { mkdirs() }

    @Serializable
    private data class Entry(val savedAtMillis: Long, val payload: FusedMarineState)

    /** ~1 km granularity - finer than this and the cache would never hit. */
    private fun keyFor(lat: Double, lon: Double): String {
        val la = (lat * 100).roundToInt()
        val lo = (lon * 100).roundToInt()
        return "s_${la}_$lo.json"
    }

    suspend fun put(state: FusedMarineState) = withContext(Dispatchers.IO) {
        try {
            val entry = Entry(System.currentTimeMillis(), state)
            File(dir, keyFor(state.lat, state.lon))
                .writeText(ApiClient.json.encodeToString(Entry.serializer(), entry))
        } catch (exc: Exception) {
            // A cache write failing must never break a good live response.
            Log.w(TAG, "cache write failed: ${exc.javaClass.simpleName}: ${exc.message}")
        }
    }

    /** Returns the cached state and how old it is, or null if nothing usable. */
    suspend fun get(lat: Double, lon: Double): Pair<FusedMarineState, Long>? = withContext(Dispatchers.IO) {
        val file = File(dir, keyFor(lat, lon))
        if (!file.exists()) return@withContext null
        try {
            val entry = ApiClient.json.decodeFromString(Entry.serializer(), file.readText())
            entry.payload to (System.currentTimeMillis() - entry.savedAtMillis)
        } catch (exc: Exception) {
            Log.w(TAG, "cache read failed: ${exc.javaClass.simpleName}: ${exc.message}")
            null
        }
    }

    private companion object {
        const val TAG = "MarineStateCache"
    }
}
