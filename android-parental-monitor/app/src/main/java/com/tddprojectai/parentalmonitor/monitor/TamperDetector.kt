package com.tddprojectai.parentalmonitor.monitor

import android.content.Context

/**
 * Tracks whether a monitoring prerequisite (usage access, accessibility) was previously seen
 * enabled, so [UsageSyncWorker][com.tddprojectai.parentalmonitor.usage.UsageSyncWorker] can
 * tell "not configured yet" (during setup, before the parent has granted it) apart from
 * "was enabled and got turned off" (an actual tamper signal worth alerting on).
 */
class TamperDetector(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    /** Returns true only the first time [currentlyEnabled] is false *after* having been true. */
    fun becameDisabled(key: String, currentlyEnabled: Boolean): Boolean {
        val wasEnabled = prefs.getBoolean(key, false)
        prefs.edit().putBoolean(key, currentlyEnabled).apply()
        return wasEnabled && !currentlyEnabled
    }

    companion object {
        private const val PREFS_NAME = "tamper_detector"
        const val KEY_USAGE_ACCESS = "usage_access"
        const val KEY_ACCESSIBILITY = "accessibility"
    }
}
