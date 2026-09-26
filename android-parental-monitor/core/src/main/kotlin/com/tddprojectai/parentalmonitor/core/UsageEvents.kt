package com.tddprojectai.parentalmonitor.core

/** Mirrors the subset of android.app.usage.UsageEvents.Event types we care about. */
enum class RawEventType {
    FOREGROUND,
    BACKGROUND,
}

data class RawUsageEvent(
    val packageName: String,
    val type: RawEventType,
    val timestampMillis: Long,
)

/** A single contiguous stretch of time an app spent in the foreground. */
data class AppSession(
    val packageName: String,
    val startTimeMillis: Long,
    val endTimeMillis: Long,
) {
    init {
        require(endTimeMillis >= startTimeMillis) {
            "endTimeMillis ($endTimeMillis) must be >= startTimeMillis ($startTimeMillis)"
        }
    }

    val durationMillis: Long get() = endTimeMillis - startTimeMillis
}
