package com.tddprojectai.parentalmonitor.admin

import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.os.UserManager

/**
 * Wraps the Device Owner policies this app applies once provisioned. Device Owner status
 * itself cannot be granted by the app at runtime — it must be set up via `adb shell dpm
 * set-device-owner` (or QR/NFC managed provisioning) on a device with no other accounts
 * configured yet. See README.md "Provisioning as Device Owner".
 *
 * The restrictions below are anti-*tamper*, not general app/content control: they make it
 * harder to silently remove monitoring, not harder to use the device day to day.
 */
class DeviceOwnerManager(private val context: Context) {

    private val devicePolicyManager: DevicePolicyManager =
        context.getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager

    private val adminComponent = ComponentName(context, MonitorDeviceAdminReceiver::class.java)

    val isDeviceOwner: Boolean
        get() = devicePolicyManager.isDeviceOwnerApp(context.packageName)

    /**
     * Applies the anti-tamper policy set. Safe to call repeatedly (e.g. on every app start);
     * every call is a no-op unless [isDeviceOwner] is true.
     */
    fun applyAntiTamperPolicies() {
        if (!isDeviceOwner) return

        // Block uninstalling this app specifically (independent of the broader
        // DISALLOW_UNINSTALL_APPS restriction, which we deliberately do not set — a child
        // should still be able to uninstall other apps on their own).
        devicePolicyManager.setUninstallBlocked(adminComponent, context.packageName, true)

        val restrictions = listOf(
            UserManager.DISALLOW_FACTORY_RESET, // can't wipe the device to remove Device Owner
            UserManager.DISALLOW_SAFE_BOOT, // safe mode disables all third-party apps/services
            UserManager.DISALLOW_DEBUGGING_FEATURES, // no ADB to disable services or grant perms
            UserManager.DISALLOW_ADD_USER, // policies are scoped to the owner user
            UserManager.DISALLOW_CONFIG_DATE_TIME, // protects log timestamp integrity
        )
        for (restriction in restrictions) {
            devicePolicyManager.addUserRestriction(adminComponent, restriction)
        }
    }

    /** True once the user has walked through Settings and enabled this app's device admin. */
    fun isDeviceAdminActive(): Boolean = devicePolicyManager.isAdminActive(adminComponent)
}
