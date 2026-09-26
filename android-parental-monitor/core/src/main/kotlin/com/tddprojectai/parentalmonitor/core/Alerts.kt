package com.tddprojectai.parentalmonitor.core

import java.time.Instant
import java.time.ZoneId

/**
 * The only alert categories this app raises. Deliberately narrow — see README for what this
 * project does *not* monitor (keystrokes, screenshots, microphone, message content).
 */
enum class AlertType {
    NEW_APP_INSTALLED,
    APP_REMOVED,
    MONITORING_DISABLE_ATTEMPT,
    MONITORING_CONFIG_CHANGED,
}

object AlertMessages {
    fun newAppInstalled(appLabel: String) = "New application installed: $appLabel"
    fun appRemoved(appLabel: String) = "Application removed: $appLabel"
    fun disableAttempt() = "Attempt to disable device administrator"
    fun configChanged(detail: String) = "Monitoring configuration changed: $detail"
}

/** Formats an alert for the dashboard feed, e.g. "09:42  New application installed: Roblox". */
object AlertDisplayFormatter {
    fun format(timestampMillis: Long, message: String, zone: ZoneId): String {
        val time = Instant.ofEpochMilli(timestampMillis).atZone(zone).toLocalTime()
        val hh = time.hour.toString().padStart(2, '0')
        val mm = time.minute.toString().padStart(2, '0')
        return "$hh:$mm  $message"
    }
}
