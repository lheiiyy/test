package com.tddprojectai.parentalmonitor.data

import androidx.room.TypeConverter
import com.tddprojectai.parentalmonitor.core.AlertType

class Converters {
    @TypeConverter
    fun fromAlertType(type: AlertType): String = type.name

    @TypeConverter
    fun toAlertType(value: String): AlertType = AlertType.valueOf(value)
}
