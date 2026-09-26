package com.tddprojectai.parentalmonitor.monitor

import com.tddprojectai.parentalmonitor.core.AlertType
import com.tddprojectai.parentalmonitor.data.AlertDao
import com.tddprojectai.parentalmonitor.data.AlertEventEntity
import kotlinx.coroutines.flow.Flow

class AlertRepository(private val alertDao: AlertDao) {

    fun observeRecent(limit: Int = 50): Flow<List<AlertEventEntity>> = alertDao.observeRecent(limit)

    suspend fun record(type: AlertType, message: String, timestampMillis: Long = System.currentTimeMillis()) {
        alertDao.insert(AlertEventEntity(type = type, message = message, timestampMillis = timestampMillis))
    }

    /** Like [record], but skipped if an identical alert already fired within [dedupeWindowMillis]. */
    suspend fun recordOnce(
        type: AlertType,
        message: String,
        dedupeWindowMillis: Long = 60 * 60 * 1000L,
        timestampMillis: Long = System.currentTimeMillis(),
    ) {
        val alreadyRecorded = alertDao.countMatchingSince(type, message, timestampMillis - dedupeWindowMillis) > 0
        if (!alreadyRecorded) {
            record(type, message, timestampMillis)
        }
    }
}
