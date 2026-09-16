package com.tddprojectai.parentalmonitor.data

import androidx.room.Entity
import androidx.room.PrimaryKey
import com.tddprojectai.parentalmonitor.core.AlertType

@Entity(tableName = "alert_event")
data class AlertEventEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val type: AlertType,
    val message: String,
    val timestampMillis: Long,
)
