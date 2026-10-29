package com.tddprojectai.parentalmonitor.data

import androidx.room.Entity
import androidx.room.PrimaryKey

/** Room-persisted form of [com.tddprojectai.parentalmonitor.core.AppSession]. */
@Entity(tableName = "app_usage_session")
data class AppUsageSession(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val packageName: String,
    val appLabel: String,
    val startTimeMillis: Long,
    val endTimeMillis: Long,
    /** "usage_stats" (periodic batch sync) or "accessibility" (near-real-time supplement). */
    val source: String,
)
