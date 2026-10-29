package com.tddprojectai.parentalmonitor.usage

import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.Context
import com.tddprojectai.parentalmonitor.core.RawEventType
import com.tddprojectai.parentalmonitor.core.RawUsageEvent
import com.tddprojectai.parentalmonitor.core.SessionBuilder
import com.tddprojectai.parentalmonitor.data.AppUsageSession
import com.tddprojectai.parentalmonitor.util.AppLabelResolver

/**
 * Batch source of truth for app usage: reads everything UsageStatsManager has recorded since
 * the last sync point and turns it into sessions via the shared [SessionBuilder] logic.
 * Requires PACKAGE_USAGE_STATS access (see PermissionUtils.hasUsageAccess).
 */
class UsageStatsCollector(
    private val context: Context,
    private val appLabelResolver: AppLabelResolver,
) {
    private val usageStatsManager =
        context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager

    /** Collects and converts events in [sinceMillis, untilMillis) into ready-to-persist sessions. */
    fun collectSessions(sinceMillis: Long, untilMillis: Long): List<AppUsageSession> {
        if (untilMillis <= sinceMillis) return emptyList()

        val rawEvents = readRawEvents(sinceMillis, untilMillis)
        val sessions = SessionBuilder.buildSessions(rawEvents, openSessionEndMillis = untilMillis)

        return sessions.map { session ->
            AppUsageSession(
                packageName = session.packageName,
                appLabel = appLabelResolver.labelFor(session.packageName),
                startTimeMillis = session.startTimeMillis,
                endTimeMillis = session.endTimeMillis,
                source = SOURCE_USAGE_STATS,
            )
        }
    }

    private fun readRawEvents(sinceMillis: Long, untilMillis: Long): List<RawUsageEvent> {
        val events = usageStatsManager.queryEvents(sinceMillis, untilMillis)
        val result = mutableListOf<RawUsageEvent>()
        val event = UsageEvents.Event()

        while (events.hasNextEvent()) {
            events.getNextEvent(event)
            val type = when (event.eventType) {
                UsageEvents.Event.MOVE_TO_FOREGROUND -> RawEventType.FOREGROUND
                UsageEvents.Event.MOVE_TO_BACKGROUND -> RawEventType.BACKGROUND
                else -> continue
            }
            result += RawUsageEvent(event.packageName, type, event.timeStamp)
        }
        return result
    }

    companion object {
        const val SOURCE_USAGE_STATS = "usage_stats"
    }
}
