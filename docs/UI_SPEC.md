# UI Specification — DroidBridge

The reference is a CLI (see VIDEO_ANALYSIS.md §0–1); there is no visual design system to copy pixel-for-pixel. This spec translates its **menu categories and workflow** into a conventional desktop GUI (sidebar + content pane), per the project brief's architecture instructions. Layout/spacing/typography choices below are therefore original design decisions, not measurements from the source — flagged as such per screen.

---

### Screen: App Shell
- **Purpose:** Persistent frame — sidebar navigation + top bar + content area, hosting every other screen.
- **Visible components:** Sidebar with sections mapped from the reference's categories (Devices, Apps, Monitoring, Screen Mirror, Files, Settings); top bar with app name "DroidBridge", global device-status pill (green/yellow/red dot + label), refresh icon.
- **User actions:** Click a sidebar item to switch content pane; click device-status pill to open the connection panel.
- **Expected result:** Content pane swaps without losing device connection state.
- **Error states:** If no device connected, non-device-dependent screens (Settings) stay usable; device-dependent screens show an empty state (see "No Device Connected" below).
- **Implementation status:** Reproduced (original layout; source confirms only *that* categories exist, not a sidebar visual).

### Screen: No Device Connected (empty state)
- **Purpose:** Default state before any pairing; also shown after a disconnect.
- **Visible components:** Illustration/icon, "No device connected" text, primary button "Connect a device", secondary link "How wireless debugging pairing works".
- **User actions:** Click "Connect a device" → opens Pairing screen.
- **Expected result:** Navigates to pairing.
- **Error states:** N/A (this *is* an error/empty state for the rest of the app).
- **Implementation status:** Reproduced (required by brief: "app must remain usable when no device is connected"); not present as such in the source, which has no GUI empty states.

### Screen: Pairing (QR + manual)
- **Purpose:** GUI equivalent of the reference's browser-hosted QR page (VIDEO_ANALYSIS.md frame_015-019).
- **Visible components:** Two tabs — "Scan QR" (QR code image, "Open Settings → System → Developer options → Wireless debugging on your phone, then scan") and "Enter pairing code" (IP:port + 6-digit code fields, matching Android's real `adb pair` flow); live status line ("Waiting for device…" → "Paired, connecting…" → "Connected").
- **User actions:** Scan QR with phone camera, or type pairing code manually; cancel button.
- **Expected result:** On success, navigates to Device Dashboard for the newly connected device.
- **Error states:** Timeout ("No response from device — check both are on the same network"), wrong/expired code, ADB not installed/found (with a "Locate adb" file-picker fallback).
- **Implementation status:** Adapted — reproduces the *workflow* (QR-based pairing over LAN) but binds it to Android's own documented `adb pair` protocol instead of an unspecified custom handshake, since the source never shows an authorization step and we won't build a pairing flow that could skip Android's consent dialog.

### Screen: Device Dashboard
- **Purpose:** GUI equivalent of "Device Info" + "Check connection" + "System Monitoring" menu categories.
- **Visible components:** Header card (model, manufacturer, Android version/API level, serial, connection type — USB/Wi-Fi); stat tiles for battery %, charging state, storage used/free, memory used/free; a "Running processes" and "Network info" expandable table each.
- **User actions:** Click "Refresh" to re-poll; click a stat tile to expand its detailed view; "Disconnect" button.
- **Expected result:** Tiles update from fresh `adb shell` output; disconnect returns to empty state.
- **Error states:** Device unplugged/unreachable mid-view → tiles show "Unavailable" with last-known timestamp instead of stale data presented as live; disconnect confirmation if any operation is in-flight.
- **Implementation status:** Reproduced (source confirms these data categories exist: battery, memory, CPU, storage, processes, network, system properties — items 28–34).

### Screen: App Management
- **Purpose:** GUI equivalent of "APP MANAGEMENT" category (install/uninstall/list/info/clear/force-stop/start/backup/batch install).
- **Visible components:** Searchable/sortable package table (name, version, size, install source); toolbar buttons (Install APK, Batch Install, Uninstall, Force Stop, Clear Data, Backup); row-level "Launch" action.
- **User actions:** Select a row to enable row-scoped actions; drag-and-drop or file-picker for Install.
- **Expected result:** Action runs, toolbar shows a progress toast, table refreshes.
- **Error states:** Install failure (signature mismatch, insufficient storage, user-declined install prompt on device) surfaces the device's own error text rather than a generic failure.
- **Implementation status:** Reproduced (items 10–18).

### Screen: Shell / Logs
- **Purpose:** GUI equivalent of "Execute shell command" + "Get device logs".
- **Visible components:** Two tabs — "Logcat" (scrolling log viewer, level/tag filters, pause/resume, "Start live tail" toggle, export button) and "Shell" (command input, allowlist indicator, output pane).
- **User actions:** Type a command and press Enter; if not on the allowlist, a confirmation dialog appears showing the literal command before it runs.
- **Expected result:** Output streamed into the pane; logcat updates live when tailing is on.
- **Error states:** Device offline mid-command → pane shows a disconnect banner instead of hanging silently.
- **Implementation status:** Adapted (allowlist + confirmation is new; the source shows no such gate, but the brief requires "command allowlisting" and "confirmation dialogs" for exactly this feature).

### Screen: Screen Mirror
- **Purpose:** GUI equivalent of "SCREEN SHARING" category and the reference's separate "Remote Android Screen" window (frame_040-050).
- **Visible components:** Live mirrored frame of the device (via scrcpy), session list sidebar-within-screen if multiple devices connected, toolbar (Start/Stop, Record, Settings — bitrate/max-size/orientation), "Check scrcpy" status indicator.
- **User actions:** Start/stop mirroring; click a session to bring its window forward; start/stop recording to a chosen file path.
- **Expected result:** Real-time mirrored view; recording produces a playable video file.
- **Error states:** scrcpy not found/installed → inline install instructions instead of a silent no-op; device screen off → mirror shows "Device screen is off" rather than a frozen frame mistaken for live.
- **Implementation status:** Reproduced (items 37, 40–45); item 38 ("Generate QR Payload") intentionally omitted — see FEATURE_SPEC.md.

### Screen: File Browser / Transfer
- **Purpose:** GUI equivalent of "Sync folder" (#46), made explicit/on-demand rather than an implied background sync.
- **Visible components:** Two-pane file browser (device filesystem on one side, local on the other), transfer queue with per-file progress.
- **User actions:** Navigate device directories the current ADB permission level can read; drag files between panes to `adb push`/`adb pull`.
- **Expected result:** Transfer queue completes with per-file success/fail status.
- **Error states:** Permission-denied paths shown as locked/greyed rather than silently skipped; transfer failure shows the underlying `adb` error.
- **Implementation status:** Adapted (explicit, operator-initiated transfer only — see FEATURE_SPEC.md #46 rationale).

### Screen: Settings
- **Purpose:** Not shown in the source at all (CLI tools don't have a settings screen); required by the brief's architecture (Phase 4 component list includes "SettingsPanel").
- **Visible components:** ADB binary path override, scrcpy binary path override, shell command allowlist editor, log retention/export location, theme toggle.
- **User actions:** Edit and save; "Reset to defaults".
- **Expected result:** Persisted to local config (SQLite/config file), applied without restart where feasible.
- **Error states:** Invalid path → inline validation error, not a silent revert.
- **Implementation status:** Inferred/original (no source basis; needed for the app to be usable and configurable).

---

## Design tokens (original, not source-derived)

Since the source has no shippable visual design (it's a red-on-black terminal), DroidBridge uses a neutral, professional palette distinct from the source's branding:
- Dark-mode-first, matching the "developer tool" register of the source's terminal aesthetic, but in a conventional slate/blue palette (no red skull/glitch styling, no "PhantomDroid" wordmark).
- Status colors: green = connected/ready, amber = connecting/degraded, red = error/disconnected — reused consistently across the device-status pill, session list, and mirror toolbar.
- Monospace font reserved for the Shell/Logs screen only, to keep its "raw" register readable, matching the one place the source's terminal identity is genuinely functional rather than branding.
