package com.tddprojectai.parentalmonitor.data

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import com.tddprojectai.parentalmonitor.core.AlertType
import kotlinx.coroutines.flow.Flow

@Dao
interface AlertDao {
    @Insert
    suspend fun insert(alert: AlertEventEntity)

    @Query("SELECT * FROM alert_event ORDER BY timestampMillis DESC LIMIT :limit")
    fun observeRecent(limit: Int = 50): Flow<List<AlertEventEntity>>

    @Query(
        "SELECT COUNT(*) FROM alert_event WHERE type = :type AND message = :message AND timestampMillis >= :sinceMillis"
    )
    suspend fun countMatchingSince(type: AlertType, message: String, sinceMillis: Long): Int

    @Query("DELETE FROM alert_event WHERE timestampMillis < :beforeMillis")
    suspend fun deleteOlderThan(beforeMillis: Long)
}
