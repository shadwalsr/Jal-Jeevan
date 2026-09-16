package com.jaljeev.marine.location

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.os.Looper
import androidx.core.content.ContextCompat
import com.google.android.gms.location.CurrentLocationRequest
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.google.android.gms.tasks.CancellationTokenSource
import com.jaljeev.marine.domain.GeoPoint
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume

/**
 * Thin wrapper over fused location.
 *
 * Returns null rather than a last-known-anything when permission is missing
 * or no fix is available: the whole system is vessel-position-relative, and a
 * silently wrong position would produce a confident, wrong safety verdict.
 */
class LocationProvider(private val context: Context) {

    private val client: FusedLocationProviderClient =
        LocationServices.getFusedLocationProviderClient(context)

    fun hasPermission(): Boolean =
        ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) ==
            PackageManager.PERMISSION_GRANTED ||
            ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) ==
            PackageManager.PERMISSION_GRANTED

    @SuppressLint("MissingPermission") // guarded by hasPermission() above
    suspend fun current(): GeoPoint? {
        if (!hasPermission()) return null
        val cancellation = CancellationTokenSource()
        return suspendCancellableCoroutine { cont ->
            val request = CurrentLocationRequest.Builder()
                .setPriority(Priority.PRIORITY_HIGH_ACCURACY)
                .setMaxUpdateAgeMillis(30_000)
                .setDurationMillis(20_000)
                .build()
            client.getCurrentLocation(request, cancellation.token)
                .addOnSuccessListener { location: Location? ->
                    cont.resume(location?.let { GeoPoint(it.latitude, it.longitude) })
                }
                .addOnFailureListener { cont.resume(null) }
            cont.invokeOnCancellation { cancellation.cancel() }
        }
    }

    /** Continuous updates for the foreground safety watch. */
    @SuppressLint("MissingPermission") // caller checks hasPermission() before collecting
    fun updates(intervalMillis: Long): Flow<GeoPoint> = callbackFlow {
        if (!hasPermission()) {
            close(SecurityException("Location permission not granted"))
            return@callbackFlow
        }
        val request = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, intervalMillis)
            .setMinUpdateIntervalMillis(intervalMillis / 2)
            .setWaitForAccurateLocation(false)
            .build()
        val callback = object : LocationCallback() {
            override fun onLocationResult(result: LocationResult) {
                result.lastLocation?.let { trySend(GeoPoint(it.latitude, it.longitude)) }
            }
        }
        client.requestLocationUpdates(request, callback, Looper.getMainLooper())
        awaitClose { client.removeLocationUpdates(callback) }
    }
}
