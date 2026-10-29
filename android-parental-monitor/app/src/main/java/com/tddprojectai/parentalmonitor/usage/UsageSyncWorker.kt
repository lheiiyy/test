package com.tddprojectai.parentalmonitor.usage

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.tddprojectai.parentalmonitor.ParentalMonitorApp
import com.tddprojectai.parentalmonitor.core.AlertMessages
import com.tddprojectai.parentalmonitor.core.AlertType
import com.tddprojectai.parentalmonitor.monitor.TamperDetector
import com.tddprojectai.parentalmonitor.util.PermissionUtils
import java.util.concurrent.TimeUnit

/**
 * Periodically pulls app usage from UsageStatsManager and persists it, and separately checks
 * that the permissions/services monitoring depends on are still granted — flagging it as a
 * "monitoring configuration changed" alert if not (see README "Tamper detection").
 */
class UsageSyncWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {

    private val tamperDetector = TamperDetector(context)

    override suspend fun doWork(): Result {
        val app = applicationContext as ParentalMonitorApp

        checkTamperSignals(app)

        if (!PermissionUtils.hasUsageAccess(applicationContext)) {
            // Nothing to sync until the parent grants Usage Access; not a worker failure.
            return Result.success()
        }

        val dao = app.database.appUsageDao()
        val collector = UsageStatsCollector(applicationContext, app.appLabelResolver)

        val now = System.currentTimeMillis()
        val since = dao.latestUsageStatsSyncPointMillis() ?: (now - DEFAULT_LOOKBACK_MILLIS)

        val sessions = collector.collectSessions(sinceMillis = since, untilMillis = now)
        if (sessions.isNotEmpty()) {
            dao.insertAll(sessions)
        }
        dao.deleteOlderThan(now - RETENTION_MILLIS)

        return Result.success()
    }

    /**
     * Only alerts on a true enabled -> disabled transition, not on "not configured yet"
     * (which is the normal state before the parent finishes the setup checklist).
     */
    private suspend fun checkTamperSignals(app: ParentalMonitorApp) {
        val hasUsageAccess = PermissionUtils.hasUsageAccess(applicationContext)
        if (tamperDetector.becameDisabled(TamperDetector.KEY_USAGE_ACCESS, hasUsageAccess)) {
            app.alertRepository.recordOnce(
                AlertType.MONITORING_CONFIG_CHANGED,
                AlertMessages.configChanged("usage access permission was revoked"),
            )
        }

        val isAccessibilityEnabled = PermissionUtils.isAccessibilityServiceEnabled(applicationContext)
        if (tamperDetector.becameDisabled(TamperDetector.KEY_ACCESSIBILITY, isAccessibilityEnabled)) {
            app.alertRepository.recordOnce(
                AlertType.MONITORING_CONFIG_CHANGED,
                AlertMessages.configChanged("accessibility service was turned off"),
            )
        }
    }

    companion object {
        private const val WORK_NAME = "usage-sync"
        private val DEFAULT_LOOKBACK_MILLIS = TimeUnit.HOURS.toMillis(24)
        private val RETENTION_MILLIS = TimeUnit.DAYS.toMillis(30)

        fun schedulePeriodic(context: Context) {
            // 15 minutes is the WorkManager-enforced minimum interval for periodic work.
            val request = PeriodicWorkRequestBuilder<UsageSyncWorker>(15, TimeUnit.MINUTES)
                .setConstraints(Constraints.NONE)
                .build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                request,
            )
        }
    }
}
