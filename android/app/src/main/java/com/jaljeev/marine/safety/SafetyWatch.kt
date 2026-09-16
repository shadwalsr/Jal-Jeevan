package com.jaljeev.marine.safety

import com.jaljeev.marine.data.remote.QuickCheckResult
import com.jaljeev.marine.domain.GeoPoint
import com.jaljeev.marine.domain.RiskLevel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class WatchState(
    val running: Boolean = false,
    val position: GeoPoint? = null,
    val lastResult: QuickCheckResult? = null,
    val lastCheckedAtMillis: Long? = null,
    /** Set when the most recent poll failed. The previous result stays visible, marked stale. */
    val lastError: String? = null,
    val consecutiveFailures: Int = 0,
) {
    val level: RiskLevel get() = RiskLevel.from(lastResult?.riskLevel)

    val isUnsafe: Boolean
        get() = lastResult?.let { it.vetoed || RiskLevel.from(it.riskLevel).isUnsafe } ?: false
}

/**
 * Bridge between the foreground service (which owns the polling loop and
 * outlives any screen) and the Watch UI. A plain process-wide StateFlow is
 * enough: there is exactly one watch, and it is meaningless without the
 * process alive.
 */
object SafetyWatch {

    private val _state = MutableStateFlow(WatchState())
    val state: StateFlow<WatchState> = _state.asStateFlow()

    fun setRunning(running: Boolean) {
        _state.value = if (running) {
            _state.value.copy(running = true, lastError = null)
        } else {
            // Keep the last verdict on screen after stopping, but never keep
            // claiming it is being watched.
            _state.value.copy(running = false)
        }
    }

    fun onPosition(point: GeoPoint) {
        _state.value = _state.value.copy(position = point)
    }

    fun onResult(result: QuickCheckResult) {
        _state.value = _state.value.copy(
            lastResult = result,
            lastCheckedAtMillis = System.currentTimeMillis(),
            lastError = null,
            consecutiveFailures = 0,
        )
    }

    fun onError(message: String) {
        _state.value = _state.value.copy(
            lastError = message,
            consecutiveFailures = _state.value.consecutiveFailures + 1,
        )
    }
}
