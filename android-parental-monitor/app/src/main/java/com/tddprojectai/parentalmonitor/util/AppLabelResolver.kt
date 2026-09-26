package com.tddprojectai.parentalmonitor.util

import android.content.Context
import android.content.pm.PackageManager

/**
 * Resolves a package name to its user-visible label (e.g. "com.google.android.youtube" ->
 * "YouTube"). Looking up a specific known package by name — as opposed to enumerating all
 * installed packages — works even without QUERY_ALL_PACKAGES once this app is Device Owner
 * (Device Owner apps are exempt from Android's package-visibility filtering). Pre-provisioning,
 * or for a package this app has no visibility into, we fall back to the raw package name.
 */
class AppLabelResolver(context: Context) {
    private val packageManager: PackageManager = context.applicationContext.packageManager
    private val cache = mutableMapOf<String, String>()

    fun labelFor(packageName: String): String = cache.getOrPut(packageName) {
        runCatching {
            val appInfo = packageManager.getApplicationInfo(packageName, 0)
            packageManager.getApplicationLabel(appInfo).toString()
        }.getOrDefault(packageName)
    }
}
