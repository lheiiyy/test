package com.tddprojectai.parentalmonitor.core

/**
 * Stateful helper for the AccessibilityService's near-real-time foreground-app stream.
 * Unlike [SessionBuilder] (which post-processes a batch of UsageStatsManager events), this
 * consumes one window-state-changed callback at a time as it happens.
 */
class ForegroundSessionTracker {
    private var openPackage: String? = null
    private var openStartMillis: Long = 0L

    /**
     * Call when the foreground app changes. Returns the [AppSession] that just closed
     * (null if this is the first app seen, or the same package reported again).
     */
    fun onForegroundChanged(packageName: String, timestampMillis: Long): AppSession? {
        if (packageName == openPackage) return null
        val closed = closeOpenSession(timestampMillis)
        openPackage = packageName
        openStartMillis = timestampMillis
        return closed
    }

    /** Call when the service is torn down (e.g. disabled by the user) to flush the open session. */
    fun closeOpenSession(nowMillis: Long): AppSession? {
        val pkg = openPackage ?: return null
        openPackage = null
        return if (nowMillis > openStartMillis) AppSession(pkg, openStartMillis, nowMillis) else null
    }
}
