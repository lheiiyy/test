# Feature Specification — DroidBridge

Legend: **R** = Reproduced (legitimate equivalent built), **A** = Adapted (behavior kept, mechanism made explicit/safe), **O** = Omitted (unverifiable or unsafe as sourced).

## Device connection & session

| # | Reference feature (as labeled in video) | Status | DroidBridge equivalent |
|---|---|---|---|
| 1 | List devices | R | `adb devices -l`, rendered as a device list panel |
| 2 | Connect WiFi | A | Wireless-debugging pairing flow using Android 11+'s **official** `adb pair` (six-digit code) where available, falling back to `adb connect ip:port` for the operator's own already-debug-enabled device on the same LAN. QR code, when used, encodes the same pairing info a user would otherwise type — it never silently grants access; the phone always shows Android's own "Allow wireless debugging" / "Allow USB debugging" system dialog, which DroidBridge cannot suppress or bypass (by Android design). |
| 3 | Disconnect device | R | `adb disconnect <serial>` |
| 4 | Device Info | R | `adb shell getprop` subset (model, manufacturer, Android version, SDK/API level, build fingerprint) |
| 5 | Restart PhantomDroid | A | "Restart connection" — re-runs the connection handshake; renamed because "restart the tool" and "restart the phone" were ambiguously worded in the source |
| 6 | Check connection | R | Poll `adb get-state` / heartbeat ping on an interval, shown as a live status dot |
| 7 | Execute shell command | A | Kept, but scoped: a command **allowlist** (see SECURITY.md) covers read-only diagnostic commands by default; running an arbitrary/non-allowlisted shell command requires an explicit "Run anyway" confirmation dialog that names the exact command about to run. Never executed from a remote/unauthenticated source — only from the local operator's UI. |
| 8 | Get device logs | R | `adb logcat -d` (dump, not live-follow by default, to avoid accidentally capturing more than the operator intends), with an explicit "Start live tail" toggle |
| 9 | Reboot device | R | `adb reboot`, gated behind a confirmation dialog (destructive/disruptive to the device owner) |

## App management

| # | Reference feature | Status | DroidBridge equivalent |
|---|---|---|---|
| 10 | Install APK | R | File picker → `adb install`, requires the operator to explicitly choose the APK file; no silent/remote install path |
| 11 | Uninstall app | R | `adb uninstall <package>`, confirmation dialog |
| 12 | List packages | R | `adb shell pm list packages` |
| 13 | Package info | R | `adb shell dumpsys package <name>` (permissions, version, install source shown to the operator) |
| 14 | Clear app data | R | `adb shell pm clear <package>`, confirmation dialog (destructive) |
| 15 | Force stop app | R | `adb shell am force-stop <package>` |
| 16 | Start app | R | `adb shell monkey -p <package> -c android.intent.category.LAUNCHER 1` |
| 17 | Backup app | A | `adb backup` where the target's Android version/OEM still supports it (deprecated on many modern builds); UI clearly states when unsupported rather than failing silently |
| 18 | Batch install | R | Multi-file picker looping `adb install` with per-file success/fail reporting |

## System monitoring

| # | Reference feature | Status | DroidBridge equivalent |
|---|---|---|---|
| 28 | Battery info | R | `adb shell dumpsys battery` |
| 29 | Memory info | R | `adb shell dumpsys meminfo` |
| 30 | CPU info | R | `adb shell dumpsys cpuinfo` / `/proc/cpuinfo` |
| 31 | Storage info | R | `adb shell df` |
| 32 | Running processes | R | `adb shell ps -A` |
| 33 | Network info | R | `adb shell ip addr` / `dumpsys connectivity` (interface + connectivity state only, no traffic interception) |
| 34 | System properties | R | `adb shell getprop` (full dump, searchable in UI) |
| 35 | Apps with size | R | `adb shell pm list packages` + `dumpsys package` size stats |
| 36 | Monitor performance | R | Polling loop over 29/30 rendered as a live sparkline |

## Screen sharing / mirroring

| # | Reference feature | Status | DroidBridge equivalent |
|---|---|---|---|
| 37 | Start screen sharing | R | Launches `scrcpy` (bundled/invoked as an external dependency) against the selected device, embedded in-app where the platform allows, else as a native window |
| 38 | Generate QR Payload | **O** | Name is ambiguous in the source and its behavior is never shown executing. "Payload" terminology in a device-access tool is exactly the kind of unverifiable-but-risky-sounding feature this project's brief says to exclude rather than guess at. Reproduced instead by generic pairing QR (see #2) — nothing named "payload" ships. |
| 39 | Custom screen sharing | A | Exposed as scrcpy launch options the user already controls today (bit-rate, max size, orientation) — a settings panel, not a new capability |
| 40 | Stop screen sharing | R | Terminates the scrcpy process for that session |
| 41 | Stop all sharing | R | Terminates all active scrcpy sessions |
| 42 | Show active sessions | R | Session list panel (already needed for the UI anyway) |
| 43 | Multi-device sharing | R | One scrcpy window per connected device, tiled or tabbed |
| 44 | Check scrcpy | R | Startup dependency check with an install/PATH-fix hint if missing |
| 45 | Record screen | R | `adb shell screenrecord` (device-side, time-limited per Android's own API) or scrcpy's `--record` flag, saved to a path the operator chooses |
| 46 | Sync folder | A | Explicit, operator-initiated file transfer (`adb pull`/`adb push` on a chosen path) — not a background "sync" daemon, since silent/continuous background pulling of a device's files is exactly the kind of covert-data-extraction pattern this project must not implement |

## Undetermined ranges (19–27, 47–55)

**Not implemented, at all, in any form.** The video never shows these 18 menu items executing, printing, or even being scrolled into view. Per this project's rule ("where the reference appears to perform a potentially unsafe or unauthorized operation, replace it with an explicit, authorized equivalent" — extended here to "where the reference's operation is simply unknown, do not guess and build it anyway"), these are logged as a known gap, not silently skipped.

## Explicitly out of scope (per project brief, regardless of source)

Credential/password extraction, hidden/background surveillance, covert microphone or camera activation, keylogging, stealth persistence or hidden app icons, bypassing Android's permission or debugging-authorization dialogs, exploiting vulnerabilities, disabling Play Protect/security services, and extracting contacts/SMS/call logs/location without an explicit, visible, per-action user confirmation on the managed device.
