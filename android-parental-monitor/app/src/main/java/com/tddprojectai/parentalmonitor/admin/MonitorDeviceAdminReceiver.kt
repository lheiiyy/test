package com.tddprojectai.parentalmonitor.admin

import android.app.admin.DeviceAdminReceiver
import android.content.Context
import android.content.Intent
import com.tddprojectai.parentalmonitor.ParentalMonitorApp
import com.tddprojectai.parentalmonitor.core.AlertMessages
import com.tddprojectai.parentalmonitor.core.AlertType
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * Device admin callbacks. As a plain device admin this receiver can only *observe and log*
 * a user's attempt to remove the app (see [onDisableRequested]) and show them a warning.
 * The actual *blocking* of removal (no uninstall, no factory reset, no safe-boot escape) is
 * enforced separately once the app is promoted to Device Owner — see [DeviceOwnerManager].
 */
class MonitorDeviceAdminReceiver : DeviceAdminReceiver() {

    override fun onDisableRequested(context: Context, intent: Intent): CharSequence {
        logAlert(context, AlertType.MONITORING_DISABLE_ATTEMPT, AlertMessages.disableAttempt())
        return "Disabling this admin app turns off monitoring on this device."
    }

    override fun onDisabled(context: Context, intent: Intent) {
        logAlert(
            context,
            AlertType.MONITORING_CONFIG_CHANGED,
            AlertMessages.configChanged("device admin was disabled"),
        )
    }

    private fun logAlert(context: Context, type: AlertType, message: String) {
        val app = context.applicationContext as ParentalMonitorApp
        CoroutineScope(Dispatchers.IO).launch {
            app.alertRepository.record(type, message)
        }
    }
}
