package com.jaljeev.marine.safety

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.jaljeev.marine.MainActivity
import com.jaljeev.marine.R
import com.jaljeev.marine.data.remote.QuickCheckResult

object Notifications {

    const val CHANNEL_ALERTS = "safety_alerts"
    const val CHANNEL_STATUS = "monitor_status"

    const val ID_FOREGROUND = 1001
    const val ID_ALERT = 1002

    fun createChannels(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = context.getSystemService(NotificationManager::class.java) ?: return

        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ALERTS,
                context.getString(R.string.notification_channel_alert_name),
                NotificationManager.IMPORTANCE_HIGH,
            ).apply {
                description = context.getString(R.string.notification_channel_alert_desc)
                enableVibration(true)
            }
        )

        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_STATUS,
                context.getString(R.string.notification_channel_status_name),
                NotificationManager.IMPORTANCE_LOW, // silent: it is a status, not an alarm
            ).apply {
                description = context.getString(R.string.notification_channel_status_desc)
            }
        )
    }

    private fun openAppIntent(context: Context): PendingIntent {
        val intent = Intent(context, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        return PendingIntent.getActivity(
            context, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    /** The persistent notification the foreground service runs under. */
    fun statusNotification(context: Context, text: String): Notification =
        NotificationCompat.Builder(context, CHANNEL_STATUS)
            .setSmallIcon(R.drawable.ic_stat_jaljeev)
            .setContentTitle(context.getString(R.string.monitor_title))
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setOngoing(true)
            .setSilent(true)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setContentIntent(openAppIntent(context))
            .build()

    /**
     * The actual warning. Uses a fixed tag/id so a persisting unsafe
     * condition replaces its own alert instead of stacking a new one every
     * poll - the web client does the same thing for the same reason
     * (alarm fatigue is a safety problem, not a UX nicety).
     */
    fun alert(context: Context, result: QuickCheckResult) {
        val reasons = (if (result.vetoed) result.reasons else result.explanation)
            .takeIf { it.isNotEmpty() }
            ?.joinToString("; ")
            ?: "risk score crossed the safe threshold"

        val headline = if (result.vetoed) {
            "Do not continue - ${result.riskLevel}"
        } else {
            "${result.riskLevel} (${result.riskScore}/100)"
        }
        val body = "$headline at ${format(result.lat)}, ${format(result.lon)}\n$reasons"

        val notification = NotificationCompat.Builder(context, CHANNEL_ALERTS)
            .setSmallIcon(R.drawable.ic_stat_jaljeev)
            .setContentTitle("JalJeev - not safe to continue")
            .setContentText(headline)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setAutoCancel(true)
            .setContentIntent(openAppIntent(context))
            .build()

        try {
            NotificationManagerCompat.from(context).notify(ID_ALERT, notification)
        } catch (exc: SecurityException) {
            // POST_NOTIFICATIONS denied on API 33+. The in-app banner on the
            // Watch screen is the guaranteed channel; this one is a bonus.
        }
    }

    private fun format(v: Double) = String.format("%.4f", v)
}
