package com.tddprojectai.parentalmonitor.ui

import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import com.tddprojectai.parentalmonitor.admin.MonitorDeviceAdminReceiver
import com.tddprojectai.parentalmonitor.core.AlertDisplayFormatter
import com.tddprojectai.parentalmonitor.data.PackageUsageTotal
import java.time.ZoneId
import java.util.concurrent.TimeUnit

class MainActivity : ComponentActivity() {

    private val viewModel: MonitorViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    MonitorScreen(
                        viewModel = viewModel,
                        onRequestUsageAccess = { startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)) },
                        onRequestAccessibility = { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) },
                        onRequestDeviceAdmin = { startActivity(buildAddDeviceAdminIntent()) },
                    )
                }
            }
        }
    }

    private fun buildAddDeviceAdminIntent(): Intent {
        val adminComponent = ComponentName(this, MonitorDeviceAdminReceiver::class.java)
        return Intent(DevicePolicyManager.ACTION_ADD_DEVICE_ADMIN).apply {
            putExtra(DevicePolicyManager.EXTRA_DEVICE_ADMIN, adminComponent)
            putExtra(
                DevicePolicyManager.EXTRA_ADD_EXPLANATION,
                "Required so this device can enforce parental monitoring settings.",
            )
        }
    }
}

@Composable
fun MonitorScreen(
    viewModel: MonitorViewModel,
    onRequestUsageAccess: () -> Unit,
    onRequestAccessibility: () -> Unit,
    onRequestDeviceAdmin: () -> Unit,
) {
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) viewModel.refreshSetupState()
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    val setupState by viewModel.setupState.collectAsState()
    val usage by viewModel.todaysUsage.collectAsState()
    val alerts by viewModel.recentAlerts.collectAsState()

    LazyColumn(modifier = Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("Setup", style = MaterialTheme.typography.titleLarge) }
        item {
            SetupChecklist(
                setupState = setupState,
                onRequestUsageAccess = onRequestUsageAccess,
                onRequestAccessibility = onRequestAccessibility,
                onRequestDeviceAdmin = onRequestDeviceAdmin,
            )
        }

        item { Text("Today", style = MaterialTheme.typography.titleLarge) }
        if (usage.isEmpty()) {
            item { Text("No usage recorded yet.") }
        } else {
            items(usage) { entry -> UsageRow(entry) }
        }

        item { Text("Alerts", style = MaterialTheme.typography.titleLarge) }
        if (alerts.isEmpty()) {
            item { Text("No alerts.") }
        } else {
            items(alerts) { alert ->
                Text(AlertDisplayFormatter.format(alert.timestampMillis, alert.message, ZoneId.systemDefault()))
            }
        }
    }
}

@Composable
private fun SetupChecklist(
    setupState: MonitorViewModel.SetupState,
    onRequestUsageAccess: () -> Unit,
    onRequestAccessibility: () -> Unit,
    onRequestDeviceAdmin: () -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            ChecklistRow("Device admin active", setupState.isDeviceAdminActive, onRequestDeviceAdmin)
            ChecklistRow("Usage access granted", setupState.hasUsageAccess, onRequestUsageAccess)
            ChecklistRow("Accessibility service enabled", setupState.isAccessibilityEnabled, onRequestAccessibility)
            Text(
                if (setupState.isDeviceOwner) {
                    "Device Owner: active (anti-tamper policies enforced)"
                } else {
                    "Device Owner: not provisioned — see README for the adb provisioning step"
                },
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
private fun ChecklistRow(label: String, done: Boolean, onClick: () -> Unit) {
    Column {
        Text((if (done) "✓ " else "✗ ") + label)
        if (!done) {
            Button(onClick = onClick) { Text("Fix") }
        }
    }
}

@Composable
private fun UsageRow(entry: PackageUsageTotal) {
    val minutes = TimeUnit.MILLISECONDS.toMinutes(entry.totalDurationMillis)
    Text("${entry.appLabel}: ${minutes}m")
}
