package com.tddprojectai.parentalmonitor.core

/**
 * Turns a raw FOREGROUND/BACKGROUND event stream (as reported by UsageStatsManager) into
 * discrete [AppSession]s. Real devices occasionally drop a BACKGROUND event (e.g. the app is
 * killed rather than backgrounded), so a session is force-closed the moment a *different*
 * package comes to the foreground, not only on a matching BACKGROUND event.
 */
object SessionBuilder {

    /**
     * @param events unordered raw events; will be sorted by timestamp internally.
     * @param openSessionEndMillis the timestamp to close a still-open trailing session at
     *   (typically "now"), so the currently foregrounded app is included in today's totals.
     */
    fun buildSessions(events: List<RawUsageEvent>, openSessionEndMillis: Long): List<AppSession> {
        val sorted = events.sortedBy { it.timestampMillis }
        val sessions = mutableListOf<AppSession>()
        var current: RawUsageEvent? = null

        for (event in sorted) {
            when (event.type) {
                RawEventType.FOREGROUND -> {
                    val prev = current
                    if (prev != null && prev.packageName != event.packageName) {
                        sessions += AppSession(prev.packageName, prev.timestampMillis, event.timestampMillis)
                    }
                    if (prev == null || prev.packageName != event.packageName) {
                        current = event
                    }
                }

                RawEventType.BACKGROUND -> {
                    val prev = current
                    if (prev != null && prev.packageName == event.packageName) {
                        sessions += AppSession(prev.packageName, prev.timestampMillis, event.timestampMillis)
                        current = null
                    }
                    // A BACKGROUND event with no matching open FOREGROUND is spurious; ignore it.
                }
            }
        }

        current?.let { prev ->
            if (openSessionEndMillis > prev.timestampMillis) {
                sessions += AppSession(prev.packageName, prev.timestampMillis, openSessionEndMillis)
            }
        }

        return sessions
    }

    /** Sums session duration per package, clipped to [rangeStartMillis, rangeEndMillis). */
    fun totalDurationByPackage(
        sessions: List<AppSession>,
        rangeStartMillis: Long,
        rangeEndMillis: Long,
    ): Map<String, Long> {
        val totals = mutableMapOf<String, Long>()
        for (session in sessions) {
            val clippedStart = maxOf(session.startTimeMillis, rangeStartMillis)
            val clippedEnd = minOf(session.endTimeMillis, rangeEndMillis)
            if (clippedEnd > clippedStart) {
                totals.merge(session.packageName, clippedEnd - clippedStart, Long::plus)
            }
        }
        return totals
    }
}
