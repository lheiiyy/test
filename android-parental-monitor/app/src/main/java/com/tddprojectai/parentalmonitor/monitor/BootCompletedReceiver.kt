package com.tddprojectai.parentalmonitor.monitor

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.tddprojectai.parentalmonitor.usage.UsageSyncWorker

class BootCompletedReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            UsageSyncWorker.schedulePeriodic(context)
        }
    }
}
