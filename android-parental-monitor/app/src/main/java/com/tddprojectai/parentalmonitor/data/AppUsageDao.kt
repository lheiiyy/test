package com.tddprojectai.parentalmonitor.data

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

data class PackageUsageTotal(
    val packageName: String,
    val appLabel: String,
    val totalDurationMillis: Long,
)

@Dao
interface AppUsageDao {
    @Insert
    suspend fun insertAll(sessions: List<AppUsageSession>)

    // Only source='usage_stats' (the periodic UsageStatsManager batch sync) is aggregated here.
    // Accessibility-sourced rows cover an overlapping time range (it's a near-real-time
    // supplement, not an independent signal) and would double-count if summed together.
    @Query(
        """
        SELECT packageName, appLabel, SUM(
            MIN(endTimeMillis, :rangeEndMillis) - MAX(startTimeMillis, :rangeStartMillis)
        ) AS totalDurationMillis
        FROM app_usage_session
        WHERE source = 'usage_stats'
            AND endTimeMillis > :rangeStartMillis AND startTimeMillis < :rangeEndMillis
        GROUP BY packageName, appLabel
        ORDER BY totalDurationMillis DESC
        """
    )
    fun observeUsageTotals(rangeStartMillis: Long, rangeEndMillis: Long): Flow<List<PackageUsageTotal>>

    /** Latest end time already persisted from the batch UsageStatsManager sync, for incremental catch-up. */
    @Query("SELECT MAX(endTimeMillis) FROM app_usage_session WHERE source = 'usage_stats'")
    suspend fun latestUsageStatsSyncPointMillis(): Long?

    @Query("DELETE FROM app_usage_session WHERE endTimeMillis < :beforeMillis")
    suspend fun deleteOlderThan(beforeMillis: Long)
}
