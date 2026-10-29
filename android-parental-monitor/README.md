# Family Device Monitor (Android)

A parental-monitoring app for a device a parent owns and provisions for their child — the
same category as Google Family Link, Bark, or Qustodio. It records **which apps run, when,
and for how long**, plus a small set of tamper/install alerts. It does not read message
content, screenshots, keystrokes, or audio. See [What this does not do](#what-this-does-not-do).

## Architecture

```
UsageStatsManager ──┐
                     ├──> SessionBuilder (core) ──> Room DB ──> on-device dashboard (Compose)
AccessibilityService ┘
      │
PackageChangeReceiver, MonitorDeviceAdminReceiver ──> AlertRepository ──> Room DB
```

- **`core/`** — a plain-JVM Kotlin module with zero Android dependency: event-to-session
  logic, alert message formatting. Runs and unit-tests with a plain JDK + Gradle (no Android
  SDK needed) — see [Running the tests](#running-the-tests). This is where the actual "did
  we compute usage correctly" logic lives and is verified.
- **`app/`** — the Android module. Depends on `core` for the pure logic and wraps it with:
  - `usage/UsageStatsCollector.kt` + `usage/UsageSyncWorker.kt` — every 15 minutes (the
    WorkManager-enforced minimum for periodic work), reads everything `UsageStatsManager` has
    recorded since the last sync and persists it as sessions. This is the authoritative
    source for the dashboard's per-app totals.
  - `accessibility/ForegroundAppAccessibilityService.kt` — a near-real-time supplement that
    only listens for `TYPE_WINDOW_STATE_CHANGED` (which app/window just came to front).
    Requests no other event types and `canRetrieveWindowContent="false"`
    (`res/xml/accessibility_service_config.xml`), so it has no ability to read screen text or
    input. Its rows are kept separately in the DB and are *not* summed into the dashboard
    totals (to avoid double-counting against the UsageStatsManager sync — see the comment on
    `AppUsageDao.observeUsageTotals`).
  - `admin/MonitorDeviceAdminReceiver.kt` + `admin/DeviceOwnerManager.kt` — device admin /
    Device Owner integration. See [Provisioning as Device Owner](#provisioning-as-device-owner).
  - `monitor/PackageChangeReceiver.kt` — logs an alert when an app is installed or removed
    (ignores app updates).
  - `data/` — Room entities, DAOs, database.
  - `ui/MainActivity.kt` — a single-screen on-device dashboard: a setup checklist (Device
    Owner / Device Admin / Usage Access / Accessibility status, each with a button to the
    relevant system settings screen) plus today's per-app usage totals and the alerts feed.

### What this does not do

Deliberately excluded, per the design this implements:

- No keystroke logging.
- No screenshots or screen recording.
- No microphone or camera access.
- No reading of message/chat content, browsing history text, or clipboard.
- No `QUERY_ALL_PACKAGES` — package labels are resolved one known package at a time, which
  works for Device Owner apps without that restricted permission (see the comment in
  `AndroidManifest.xml` and `util/AppLabelResolver.kt`).

A realistic first version targets **app → timestamp → duration**, not **app → every exact
page → every keystroke**. VPN/DNS-based domain visibility (Step 2C in the original design) is
intentionally **not** included yet — see [Roadmap](#roadmap).

## Provisioning as Device Owner

Device Owner status cannot be granted by the app itself at runtime; it has to be set up
before any user account exists on the device (typically right after a factory reset), via
ADB:

```sh
# On a freshly factory-reset device, with USB debugging enabled and no accounts added yet:
adb install app-debug.apk
adb shell dpm set-device-owner com.tddprojectai.parentalmonitor/.admin.MonitorDeviceAdminReceiver
```

See Android's own
[DevicePolicyManager documentation](https://developer.android.com/reference/android/app/admin/DevicePolicyManager)
for the managed-provisioning (QR/NFC) alternative if ADB access isn't practical.

Once Device Owner status is granted, `DeviceOwnerManager.applyAntiTamperPolicies()` (called on
every app start, from `ParentalMonitorApp.onCreate`) applies a small, deliberately narrow set
of restrictions:

| Restriction | Why |
|---|---|
| `setUninstallBlocked` (this app only) | Can't uninstall the monitor itself. Other apps are untouched — a child can still install/remove their own apps. |
| `DISALLOW_FACTORY_RESET` | Can't wipe the device to remove Device Owner. |
| `DISALLOW_SAFE_BOOT` | Safe mode disables all third-party apps/services, including this one and the accessibility service. |
| `DISALLOW_DEBUGGING_FEATURES` | No ADB access to disable services, revoke permissions, or remove Device Owner. |
| `DISALLOW_ADD_USER` | Policies are scoped to the primary user; a second profile would bypass them. |
| `DISALLOW_CONFIG_DATE_TIME` | Protects the integrity of recorded timestamps. |

**Known limitation:** there is no public Device Owner API to silently enable an
`AccessibilityService` — Android does not expose one. The parent still has to turn it on once
via **Settings → Accessibility** (the app's setup checklist links directly there). If it's
later turned off, `UsageSyncWorker` detects that within 15 minutes and logs a "monitoring
configuration changed" alert (and the `AccessibilityService.onDestroy()` callback also logs it
immediately on the app's next foreground check). The periodic `UsageStatsManager` sync doesn't
depend on Accessibility at all, so usage totals stay accurate even while it's off — only the
near-real-time supplement is lost.

## Building

Requires the Android SDK (compileSdk 34) and network access to Google's Maven repository —
neither is available in the sandbox this was written in, so the `app` module has not been
compiled here (only manually reviewed). The `core` module has no such dependency and **was**
built and tested in-sandbox — see below.

```sh
./gradlew :app:assembleDebug   # needs Android SDK
./gradlew :core:test           # plain JDK, no SDK needed
```

If `ANDROID_HOME`/`ANDROID_SDK_ROOT` isn't set, create `local.properties` at the project root
pointing `sdk.dir` at your SDK install, or open the project in Android Studio and let it do
that for you.

### Running the tests

`core`'s session-building and alert-formatting logic is unit tested with JUnit 5 and runs on a
plain JDK:

```sh
./gradlew :core:test
```

This was verified in-sandbox with the system's Gradle 8.14.3 / JDK 21 (not via the wrapper,
which needs to download a matching distribution): 16 tests, all passing — covering normal
foreground/background pairing, interleaved apps, a dropped `BACKGROUND` event being closed by
the next app's `FOREGROUND` event, a still-open trailing session, duplicate-event collapsing,
spurious-event handling, unsorted input, range-clipped duration totals, the real-time
`ForegroundSessionTracker` state machine, and alert message formatting.

The `app` module's Android-specific code (Room queries, the AccessibilityService, the
DevicePolicyManager integration) needs an emulator/device or Robolectric to exercise — not set
up here; see [Roadmap](#roadmap).

## Testing on a device (once built)

1. Provision as Device Owner (above), install, launch the app.
2. Walk through the setup checklist: enable the device admin, grant Usage Access
   (`Settings → Apps → Special access → Usage access`), enable the Accessibility service.
3. **Incognito test:** open Chrome normally, visit a site, close it; open Incognito, visit a
   different site, close it. Check the dashboard — you should see Chrome's total time include
   both windows, even though Chrome itself won't retain Incognito history. (This app tracks
   *app* usage, not in-app browsing history, so Incognito mode doesn't hide anything from it.)
4. **Tamper-alert test:** try to remove the device admin from Settings — you should see a
   warning dialog (`onDisableRequested`) and, if you proceed, a "monitoring configuration
   changed" alert on the dashboard. With Device Owner active, uninstalling the app outright is
   blocked entirely.
5. **Install/uninstall test:** install or remove any other app and confirm an alert appears
   within a few seconds.

## Roadmap

Deliberately left for a follow-up change, in priority order:

1. **Remote parent dashboard.** Today the dashboard is on-device only (useful for setup
   verification, not for a parent checking from their own phone). `AlertRepository` and
   `AppUsageDao` are the natural sync boundary — the next step is pushing their rows to a
   backend (Firebase/Firestore was the original suggestion) and building a small viewer.
2. **VPN/DNS-based domain visibility** (`VpnService`). Explicitly deferred — the original
   design calls for building Device Owner + UsageStats + Accessibility first and treating
   VPN/DNS as a separate, later step, which this follows.
3. Instrumented/Robolectric tests for the Android-specific pieces (Room queries, the
   AccessibilityService, DevicePolicyManager integration) that `core`'s plain-JUnit tests
   can't reach.
4. Real launcher artwork — `res/drawable/ic_launcher_{background,foreground}.xml` are
   placeholder vector shapes, not final icon art.
