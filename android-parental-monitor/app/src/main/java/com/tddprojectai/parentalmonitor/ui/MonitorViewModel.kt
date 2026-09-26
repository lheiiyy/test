package com.tddprojectai.parentalmonitor.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.tddprojectai.parentalmonitor.ParentalMonitorApp
import com.tddprojectai.parentalmonitor.data.AlertEventEntity
import com.tddprojectai.parentalmonitor.data.PackageUsageTotal
import com.tddprojectai.parentalmonitor.util.PermissionUtils
import java.time.LocalDate
import java.time.ZoneId
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update

class MonitorViewModel(application: Application) : AndroidViewModel(application) {

    private val app = application as ParentalMonitorApp

    private fun startOfTodayMillis(): Long =
        LocalDate.now(ZoneId.systemDefault()).atStartOfDay(ZoneId.systemDefault()).toInstant().toEpochMilli()

    val todaysUsage: StateFlow<List<PackageUsageTotal>> =
        app.database.appUsageDao()
            .observeUsageTotals(startOfTodayMillis(), System.currentTimeMillis())
            .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    val recentAlerts: StateFlow<List<AlertEventEntity>> =
        app.alertRepository.observeRecent()
            .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    private val _setupState = MutableStateFlow(SetupState())
    val setupState: StateFlow<SetupState> = _setupState

    fun refreshSetupState() {
        _setupState.update {
            SetupState(
                isDeviceOwner = app.deviceOwnerManager.isDeviceOwner,
                isDeviceAdminActive = app.deviceOwnerManager.isDeviceAdminActive(),
                hasUsageAccess = PermissionUtils.hasUsageAccess(app),
                isAccessibilityEnabled = PermissionUtils.isAccessibilityServiceEnabled(app),
            )
        }
    }

    data class SetupState(
        val isDeviceOwner: Boolean = false,
        val isDeviceAdminActive: Boolean = false,
        val hasUsageAccess: Boolean = false,
        val isAccessibilityEnabled: Boolean = false,
    ) {
        val isFullyConfigured: Boolean get() = hasUsageAccess && isAccessibilityEnabled
    }
}
