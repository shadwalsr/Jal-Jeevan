package com.jaljeev.marine.safety

import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.ServiceCompat
import com.jaljeev.marine.appContainer
import com.jaljeev.marine.domain.ApiOutcome
import com.jaljeev.marine.domain.GeoPoint
import com.jaljeev.marine.domain.RiskLevel
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * The live safety watch: "we are essentially also a guide, because nothing is
 * sure about when the parameters might change."
 *
 * A foreground service rather than WorkManager or an in-Activity loop, because
 * the thing being watched is a boat under way: the phone will be in a pocket
 * with the screen off, and a warning that arrives when the user next opens the
 * app is not a warning.
 *
 * Two loops, deliberately separate:
 *  - location updates write to [lastKnown] as fast as the GPS produces them;
 *  - the poll loop reads [lastKnown] on a fixed interval and calls
 *    /marine/quick-check.
 * Polling straight from the location callback would tie backend request rate
 * to GPS jitter and could blow through the backend's 60-requests-per-minute
 * limit while sitting still.
 */
class SafetyMonitorService : Service() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var locationJob: Job? = null
    private var pollJob: Job? = null

    @Volatile
    private var lastKnown: GeoPoint? = null

    private var lastNotifiedAtMillis = 0L

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                stop()
                return START_NOT_STICKY
            }
        }
        start()
        // START_STICKY: if the system kills us under memory pressure while a
        // boat is out, we want to come back.
        return START_STICKY
    }

    private fun start() {
        if (locationJob != null) return

        startAsForeground("Waiting for a position fix…")
        SafetyWatch.setRunning(true)

        val container = appContainer
        val intervalSeconds = container.settings.settings.value.monitorIntervalSeconds.toLong()

        locationJob = scope.launch {
            try {
                container.locationProvider.updates(intervalMillis = 5_000L).collect { point ->
                    lastKnown = point
                    SafetyWatch.onPosition(point)
                }
            } catch (exc: SecurityException) {
                SafetyWatch.onError("Location permission was revoked - monitoring stopped.")
                stop()
            } catch (exc: Exception) {
                Log.w(TAG, "location stream failed: ${exc.javaClass.simpleName}: ${exc.message}")
                SafetyWatch.onError("Location unavailable: ${exc.javaClass.simpleName}")
            }
        }

        pollJob = scope.launch {
            while (isActive) {
                val point = lastKnown
                if (point == null) {
                    updateStatus("Waiting for a position fix…")
                } else {
                    when (val outcome = container.repository.quickCheck(point.lat, point.lon)) {
                        is ApiOutcome.Ok -> {
                            val result = outcome.value
                            SafetyWatch.onResult(result)

                            val level = RiskLevel.from(result.riskLevel)
                            val unsafe = result.vetoed || level.isUnsafe
                            val now = System.currentTimeMillis()
                            if (unsafe && now - lastNotifiedAtMillis > RENOTIFY_INTERVAL_MS) {
                                Notifications.alert(this@SafetyMonitorService, result)
                                lastNotifiedAtMillis = now
                            }
                            if (!unsafe) {
                                // Reset the throttle so the next time conditions
                                // turn bad, the alert fires immediately.
                                lastNotifiedAtMillis = 0L
                            }
                            updateStatus(statusLine(result.riskLevel, result.riskScore, result.vetoed))
                        }

                        is ApiOutcome.Err -> {
                            Log.w(TAG, "quick-check failed: ${outcome.detail ?: outcome.message}")
                            SafetyWatch.onError(outcome.message)
                            // Say the check failed. Do not imply the water is fine.
                            updateStatus("Last check failed - ${outcome.message}")
                        }
                    }
                }
                delay(intervalSeconds * 1000)
            }
        }
    }

    private fun statusLine(level: String, score: Int, vetoed: Boolean): String = when {
        vetoed -> "Not permitted here - $level"
        else -> "$level ($score/100) - checked just now"
    }

    private fun startAsForeground(text: String) {
        val notification = Notifications.statusNotification(this, text)
        val type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION
        } else {
            0
        }
        ServiceCompat.startForeground(this, Notifications.ID_FOREGROUND, notification, type)
    }

    private fun updateStatus(text: String) {
        try {
            androidx.core.app.NotificationManagerCompat.from(this)
                .notify(Notifications.ID_FOREGROUND, Notifications.statusNotification(this, text))
        } catch (exc: SecurityException) {
            // Notifications denied; the Watch screen still shows everything.
        }
    }

    private fun stop() {
        locationJob?.cancel()
        pollJob?.cancel()
        locationJob = null
        pollJob = null
        SafetyWatch.setRunning(false)
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        scope.cancel()
        SafetyWatch.setRunning(false)
        super.onDestroy()
    }

    companion object {
        private const val TAG = "SafetyMonitorService"
        private const val ACTION_STOP = "com.jaljeev.marine.action.STOP_WATCH"

        /**
         * Once already unsafe, do not fire a fresh alert on every poll - that
         * is noise, not a warning. Matches the web client's 60 s re-notify
         * throttle.
         */
        private const val RENOTIFY_INTERVAL_MS = 60_000L

        fun start(context: Context) {
            val intent = Intent(context, SafetyMonitorService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun stop(context: Context) {
            val intent = Intent(context, SafetyMonitorService::class.java).setAction(ACTION_STOP)
            context.startService(intent)
        }
    }
}
