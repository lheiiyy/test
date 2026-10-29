package com.tddprojectai.parentalmonitor

import android.app.Application
import com.tddprojectai.parentalmonitor.admin.DeviceOwnerManager
import com.tddprojectai.parentalmonitor.data.AppDatabase
import com.tddprojectai.parentalmonitor.monitor.AlertRepository
import com.tddprojectai.parentalmonitor.usage.UsageSyncWorker
import com.tddprojectai.parentalmonitor.util.AppLabelResolver

class ParentalMonitorApp : Application() {

    val database: AppDatabase by lazy { AppDatabase.getInstance(this) }
    val alertRepository: AlertRepository by lazy { AlertRepository(database.alertDao()) }
    val appLabelResolver: AppLabelResolver by lazy { AppLabelResolver(this) }
    val deviceOwnerManager: DeviceOwnerManager by lazy { DeviceOwnerManager(this) }

    override fun onCreate() {
        super.onCreate()
        deviceOwnerManager.applyAntiTamperPolicies()
        UsageSyncWorker.schedulePeriodic(this)
    }
}
