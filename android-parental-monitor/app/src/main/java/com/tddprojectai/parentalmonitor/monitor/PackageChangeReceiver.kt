package com.tddprojectai.parentalmonitor.monitor

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.tddprojectai.parentalmonitor.ParentalMonitorApp
import com.tddprojectai.parentalmonitor.core.AlertMessages
import com.tddprojectai.parentalmonitor.core.AlertType
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/** Logs an alert when an app is installed or removed on the device. Ignores app updates. */
class PackageChangeReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        val packageName = intent.data?.schemeSpecificPart ?: return
        // An app update fires REMOVED then ADDED, both with EXTRA_REPLACING=true. We only
        // care about genuine installs/removals, not version updates.
        val isReplacing = intent.getBooleanExtra(Intent.EXTRA_REPLACING, false)
        if (isReplacing) return

        val app = context.applicationContext as ParentalMonitorApp
        val pendingResult = goAsync()

        CoroutineScope(Dispatchers.IO).launch {
            try {
                when (intent.action) {
                    Intent.ACTION_PACKAGE_ADDED -> {
                        val label = app.appLabelResolver.labelFor(packageName)
                        app.alertRepository.record(AlertType.NEW_APP_INSTALLED, AlertMessages.newAppInstalled(label))
                    }

                    Intent.ACTION_PACKAGE_REMOVED -> {
                        val label = app.appLabelResolver.labelFor(packageName)
                        app.alertRepository.record(AlertType.APP_REMOVED, AlertMessages.appRemoved(label))
                    }
                }
            } finally {
                pendingResult.finish()
            }
        }
    }
}
