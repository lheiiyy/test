package com.tddprojectai.parentalmonitor.accessibility

import android.accessibilityservice.AccessibilityService
import android.view.accessibility.AccessibilityEvent
import com.tddprojectai.parentalmonitor.ParentalMonitorApp
import com.tddprojectai.parentalmonitor.core.AlertMessages
import com.tddprojectai.parentalmonitor.core.AlertType
import com.tddprojectai.parentalmonitor.core.AppSession
import com.tddprojectai.parentalmonitor.core.ForegroundSessionTracker
import com.tddprojectai.parentalmonitor.data.AppUsageSession
import com.tddprojectai.parentalmonitor.monitor.TamperDetector
import com.tddprojectai.parentalmonitor.util.PermissionUtils
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/**
 * Near-real-time supplement to [com.tddprojectai.parentalmonitor.usage.UsageSyncWorker].
 *
 * Only handles TYPE_WINDOW_STATE_CHANGED (which app/window just came to front) — see
 * accessibility_service_config.xml, which requests no other event types and
 * canRetrieveWindowContent="false". This service never reads screen text, view hierarchies,
 * or touch/key input, so it has no way to capture keystrokes or message content.
 */
class ForegroundAppAccessibilityService : AccessibilityService() {

    private val tracker = ForegroundSessionTracker()
    private val job = SupervisorJob()
    private val scope = CoroutineScope(Dispatchers.IO + job)

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event?.eventType != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) return
        val packageName = event.packageName?.toString() ?: return

        val closedSession = tracker.onForegroundChanged(packageName, System.currentTimeMillis())
        if (closedSession != null) {
            persist(closedSession)
        }
    }

    override fun onInterrupt() {
        flushOpenSession()
    }

    override fun onDestroy() {
        flushOpenSession()

        // onDestroy fires both when the user actually disables this service in Settings and
        // on ordinary OS-driven process churn (app update, low-memory reclaim, etc). Only the
        // former is a real tamper signal, so check the current Settings state rather than
        // treating every onDestroy as "turned off". Note: the launched coroutine below is
        // intentionally not tied to `job` / cancelled here — this service being destroyed
        // does not kill the app process, so it's left to run to completion on its own.
        val app = applicationContext as ParentalMonitorApp
        val tamperDetector = TamperDetector(applicationContext)
        val isAccessibilityEnabled = PermissionUtils.isAccessibilityServiceEnabled(applicationContext)
        if (tamperDetector.becameDisabled(TamperDetector.KEY_ACCESSIBILITY, isAccessibilityEnabled)) {
            scope.launch {
                app.alertRepository.recordOnce(
                    AlertType.MONITORING_CONFIG_CHANGED,
                    AlertMessages.configChanged("accessibility service was turned off"),
                )
            }
        }

        super.onDestroy()
    }

    private fun flushOpenSession() {
        val closedSession = tracker.closeOpenSession(System.currentTimeMillis())
        if (closedSession != null) {
            persist(closedSession)
        }
    }

    private fun persist(session: AppSession) {
        val app = applicationContext as ParentalMonitorApp
        scope.launch {
            val label = app.appLabelResolver.labelFor(session.packageName)
            app.database.appUsageDao().insertAll(
                listOf(
                    AppUsageSession(
                        packageName = session.packageName,
                        appLabel = label,
                        startTimeMillis = session.startTimeMillis,
                        endTimeMillis = session.endTimeMillis,
                        source = SOURCE_ACCESSIBILITY,
                    ),
                ),
            )
        }
    }

    companion object {
        const val SOURCE_ACCESSIBILITY = "accessibility"
    }
}
