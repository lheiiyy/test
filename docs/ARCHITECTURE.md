# Architecture — DroidBridge

This documents what Phase 2 actually built. Where something is a real,
working implementation vs. a documented placeholder, it says so explicitly —
see the "Phase 2 scope" line on each component.

## Component map

```
Desktop UI            desktop/src/renderer/**            React components/pages, zustand store
Desktop Services       desktop/src/main/services/**       AdbService, ScrcpyService, ScreenMirrorService,
                                                            PairingService, DeviceRegistry
ADB Service            desktop/src/main/services/adb/**   real: shells out to `adb`, enforces the allowlist
Screen Mirroring Svc   desktop/src/main/services/mirror/** real state machine; scrcpy launch is Phase-2-stubbed
Pairing Service        desktop/src/main/services/pairing/** real: issues/validates/consumes pairing sessions
Android Companion      android/app/**                     Kotlin, single Activity, real permission flow
Shared Protocol        shared/src/**                       types, zod-validated pairing payload, IPC contract
```

## Desktop architecture

Electron main process (`desktop/src/main`) + a sandboxed renderer
(`desktop/src/renderer`, React + Vite) + a preload bridge
(`desktop/src/preload`) that is the *only* thing exposed into the renderer's
global scope (`window.droidbridge`). This is the standard Electron security
posture: `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true`
(see `desktop/src/main/index.ts`), so the renderer cannot `require()`
anything, spawn processes, or touch the filesystem directly — every
privileged action is one of the seven methods on `DroidBridgeIpcApi`
(`shared/src/types/ipc.ts`), each handled in `desktop/src/main/ipc/handlers.ts`
with its own structural validation (`isConnectDeviceRequest`,
`isStartMirrorRequest`) before touching a service.

**State management:** a single zustand store (`desktop/src/renderer/state/appStore.ts`)
holds devices, app status, mirror sessions, and the active sidebar section.
Chosen over Redux/Context for its size (~1KB) and because Phase 2's state
shape is flat enough not to need normalization or middleware.

**Styling:** plain CSS with custom properties (`desktop/src/renderer/styles/global.css`),
not Tailwind. The brief allows "Tailwind or another clean component system";
given the app's small Phase 2 surface (5 pages, ~10 components), a
utility-class build pipeline wasn't worth its config/dependency weight yet.
Revisit if the component count grows enough that ad hoc CSS starts
duplicating itself.

**Why `@droidbridge/shared` has no compiled build step in the runtime path:**
both the renderer (via Vite) and the main/preload bundles (via the esbuild
script at `desktop/scripts/build-electron.mjs`) resolve and inline the
shared package's TypeScript source directly — the same way a bundler would
treat any local workspace package. `shared/package.json`'s `main`/`types`
point at `src/index.ts` for exactly this reason. `shared` still has its own
`tsc` build script (emits to `shared/dist`) for standalone type-checking and
in case a future non-bundled consumer (e.g. a CLI, or the Android app via
some interop layer) needs a compiled artifact — but nothing in the current
runtime path depends on `shared/dist` existing.

## Android architecture

Single-module Kotlin app (`android/app`), one Activity
(`MainActivity.kt`), traditional Views + ViewBinding (not Compose — chosen to
minimize Gradle/Kotlin-compiler-version coupling risk for a Phase 2 skeleton
that could not be build-verified in this sandbox; revisit once a real SDK
environment confirms the toolchain). It shows, plainly and always:
connection status ("Disconnected" by default — there is no background
service to fake a connection), camera permission status, a "Scan QR to Pair"
button, and a "Disconnect" button. Camera permission is requested only when
the user taps Scan QR (`ActivityResultContracts.RequestPermission`), with a
rationale string always visible on screen — never requested at install time
or silently. No hidden components, no non-launcher entry points, no
background services: see `AndroidManifest.xml`'s comments and
`FEATURE_SPEC.md`'s "Explicitly out of scope".

**Phase 2 scope:** the permission flow and status display are real. QR
decoding is not implemented — tapping "Scan QR" after permission is granted
shows a Snackbar saying so, rather than pretending to scan (matching
`ScrcpyService`'s "Not implemented in Phase 2" convention on the desktop
side, for the same reason: don't fake success).

## ADB integration

`desktop/src/main/services/adb/AdbService.ts` implements `IAdbService`
(`detectDevices`, `getDeviceInfo`, `getDeviceState`, `connect`, `disconnect`,
`executeAllowedOperation`, `executeConfirmedShellCommand`) against a
`CommandRunner` seam (`types.ts`). `NodeCommandRunner` is the real
implementation — it shells out via `node:child_process.execFile` with argv
arrays only (never a concatenated shell string), so there is no
command-injection surface at this layer regardless of what a caller passes
as a "command" string. Every non-allowlisted command still goes through
`String.split(' ')` into argv, not a shell.

Security boundary: `executeAllowedOperation` checks
`isAllowlistedShellCommand` (`shared/src/constants/adbAllowlist.ts`) and
throws `CommandNotAllowedError` for anything else. The *only* other path,
`executeConfirmedShellCommand`, exists specifically for the Shell screen's
confirmation-dialog flow (UI_SPEC.md) — it still logs a warning with the
literal command, but does not re-check the allowlist, because by the time
it's called the operator has already seen and approved the exact command.
There is no third path; nothing in the IPC layer can reach `AdbService`
except through one of these two methods.

## Screen mirroring service

`ScreenMirrorService` (`desktop/src/main/services/mirror/`) owns
`MirrorSession` state and the transition graph in
`shared/src/types/mirror.ts` (`idle → starting → active ⇄ paused → stopping → idle`,
with `error` reachable from every state). It knows nothing about IPC or
React — it's constructed with an `IScrcpyService` and a logger only, so it's
unit-testable headlessly and swappable independently of the UI layer, per
the brief's "do not couple screen mirroring directly to React components."

**Phase 2 scope:** the state machine is real and tested
(`ScreenMirrorService.test.ts`). Calling `start()` always ends in the
`error` state right now, because `ScrcpyService.launch()` is an intentional
stub (see below) — `start()` surfaces scrcpy's unavailability or the "Not
implemented in Phase 2" message as `session.lastError` rather than ever
reporting `active` for a session nothing actually started.

## scrcpy integration

`ScrcpyService` (`desktop/src/main/services/scrcpy/`) is the sole boundary
that will ever spawn `scrcpy`. Plan, to be implemented in a later phase:

- **Detection:** `checkAvailability()` (implemented now) runs `scrcpy --version`
  via `child_process.execFile` against a configurable binary path
  (`DROIDBRIDGE_SCRCPY_PATH` env var for now; a Settings-screen override
  later). A missing/failing binary is reported as `{ available: false, reason }`,
  never silently retried or hidden.
- **Launch:** `launch(options)` will spawn `scrcpy --serial <serial> [--max-size --video-bit-rate --record]`
  as an argv array (same no-shell-string rule as AdbService), returning the
  child process's pid.
- **Lifecycle:** one tracked child process per `MirrorSession`; `terminate(pid)`
  sends a graceful signal first (`SIGTERM`/`taskkill` equivalent), escalating
  only if the process doesn't exit within a timeout.
- **stdout/stderr:** piped into the `Logger` at `DEBUG` level by default, with
  an `onOutput` subscription hook for the future Screen Mirror UI to surface
  scrcpy's own error text (e.g. "device not found") verbatim rather than a
  generic failure message.
- **Device selection:** always explicit via `--serial`, sourced from the
  operator's selection in the Devices/Screen Mirror UI — scrcpy is never
  launched without a target, and never against "whatever device is plugged
  in" implicitly.
- **Error reporting:** every failure path resolves to `MirrorSession.state === 'error'`
  with a human-readable `lastError`; nothing is swallowed.

**Distribution/licensing:** DroidBridge does not vendor a scrcpy binary. It
expects a system-installed, official build from
[Genymobile/scrcpy](https://github.com/Genymobile/scrcpy) (Apache-2.0) on the
user's `PATH`, or a path configured in Settings. This avoids bundling an
unverified third-party binary and keeps scrcpy's own license terms with
scrcpy's own distribution channel. `checkAvailability()`'s error message
tells the user where to get it (see DEVELOPMENT.md).

## QR / network pairing

See `docs/PROTOCOL.md` for the full wire format. Summary: `PairingService`
(`desktop/src/main/services/pairing/`) issues short-lived, single-use
sessions (`createSession`) and validates/consumes scanned or typed content
(`consume`) via `shared/src/protocol/pairing.ts`'s zod schema — structural
validity, protocol version, and expiry are all checked before a session is
even looked up, and a used/unknown session is rejected regardless of
validity. This service **never** performs the actual device authorization —
that's still Android's own "Allow wireless/USB debugging" system dialog,
which DroidBridge cannot suppress, pre-answer, or bypass. A successful
`consume()` means "safe to attempt `adb pair`/`adb connect` with", not
"device is now trusted."

## Device discovery

`AdbService.detectDevices()` parses `adb devices -l` (USB and
already-connected Wi-Fi devices alike — adb reports both the same way once a
`tcpip`/`connect` handshake has happened at the OS level). There is no
separate "discovery" protocol beyond what `adb` itself provides; DroidBridge
does not broadcast on the network or scan for devices outside of what `adb`
reports.

## State management (cross-cutting)

- **Device state:** `DeviceRegistry` (`desktop/src/main/services/device/`)
  is the single place device state is mutated in the main process. It
  enforces `DEVICE_STATE_TRANSITIONS` (`shared/src/types/device.ts`) on every
  update — an illegal transition reported by `adb` (e.g. a device jumping
  straight from `disconnected` to `connected`) is logged and ignored rather
  than applied, so the UI can trust that whatever state it sees was reached
  legitimately. Tested at the unit level (`shared/src/types/device.test.ts`)
  and the integration level (`tests/integration/device-registry-transitions.test.ts`).
- **Renderer state:** the zustand store above mirrors what IPC returns; it
  does not independently compute or guess device state.

## IPC

Complete, closed surface — see `shared/src/types/ipc.ts`'s `IPC_CHANNELS` and
`DroidBridgeIpcApi`. Seven channels total for Phase 2:
`getAppStatus`, `getDevices`, `connectDevice`, `disconnectDevice`,
`startMirror`, `stopMirror`, `getMirrorSessions`. There is no generic
"run this command" or "read this file" channel — anything that needs a new
capability needs a new, specifically-typed channel and handler, by design.
Every handler in `desktop/src/main/ipc/handlers.ts` re-validates its
argument at runtime (`isConnectDeviceRequest`, `isStartMirrorRequest`) even
though the renderer is our own code — the preload bridge is the one seam an
injected or compromised renderer could try to send malformed data across.

## Security boundaries

1. Renderer → preload → IPC → main-process handler → service. No layer is
   skippable from the renderer's side (enforced by Electron's
   `contextIsolation`/`sandbox`, not just convention).
2. Every process spawn (`adb`, eventually `scrcpy`) goes through one
   argv-array call site per binary (`NodeCommandRunner.runAdb`,
   `ScrcpyService`'s future launch method) — no shell string interpolation
   anywhere in the codebase.
3. Shell commands against a connected device are allowlisted by default
   (`ADB_READONLY_SHELL_PREFIXES`); anything else requires an explicit,
   already-shown confirmation before `executeConfirmedShellCommand` is ever
   called (enforced at the UI layer in a later phase; the service-level gate
   exists now).
4. Destructive `adb` operations (`DESTRUCTIVE_ADB_OPERATIONS`) are flagged
   for mandatory confirmation regardless of allowlist status.
5. Pairing payloads are validated (structure, version, expiry) before
   lookup, and sessions are single-use.

## Logging

`desktop/src/main/logging/logger.ts`: a small structured logger
(`DEBUG`/`INFO`/`WARN`/`ERROR`), scoped via `.child(scope)` (one child logger
per service: `"adb"`, `"scrcpy"`, `"mirror"`, `"devices"`, `"main"`). Every
entry is `{ level, scope, message, timestamp, data? }`. A fixed redaction
list (`token`, `pairingCode`, `password`, `secret`, `authorization`,
`credential`, case-insensitive) is applied to the `data` payload before any
sink sees it — belt-and-suspenders on top of callers simply not passing
sensitive fields in the first place (e.g. `PairingService.createSession`
never puts the token in its own log call). Minimum level is configurable via
`DROIDBRIDGE_LOG_LEVEL`.

## Error handling

Every service method that can fail either throws a specifically-typed error
(`AdbNotFoundError`, `CommandNotAllowedError`, `InvalidMirrorTransitionError`)
or resolves to an explicit `{ ok: false, error }`/`error` state — nothing
resolves to a happy-path shape while actually having failed. This is checked
directly in tests (e.g. `ScreenMirrorService.test.ts`'s "never reports an
active session when nothing was actually started").

## Testing strategy

- **Unit tests**, colocated with source (`*.test.ts` next to the file it
  tests) in both `shared/` and `desktop/`: fast, no I/O, real `adb`/`scrcpy`
  binaries replaced with fakes/mocks (`CommandRunner`, `IScrcpyService`).
- **Integration tests**, in the top-level `tests/` folder: cross-package
  checks that a decision recorded in `shared/` is actually enforced in
  `desktop/` (e.g. `tests/integration/adb-allowlist-boundary.test.ts` checks
  every entry in `ADB_READONLY_SHELL_PREFIXES` is actually accepted by
  `AdbService`, and everything else is actually rejected). See `tests/README.md`.
- **Renderer test**, `desktop/src/renderer/App.test.tsx`: `@testing-library/react`
  + jsdom (scoped per-file via a `// @vitest-environment jsdom` pragma, so
  the rest of the desktop suite stays on the faster default `node`
  environment), covering the empty-state and connected-device paths.
- **Type checking:** `tsc --noEmit` against `shared`, the renderer
  (`desktop/tsconfig.json`), and main/preload (`desktop/tsconfig.electron.json`)
  separately, since they target different runtimes (DOM+bundler vs. bare
  Node) and shouldn't share a single `include` set.
- **Not yet covered:** Electron end-to-end tests (e.g. Playwright driving a
  real Electron window) — deferred; Phase 2's UI tests are component-level
  only, per the brief's "basic UI tests if practical."

## TypeScript strictness

`tsconfig.base.json` enables `strict`, `noUncheckedIndexedAccess`, and
`noImplicitOverride`. It deliberately does **not** enable
`exactOptionalPropertyTypes`: that flag requires every optional field to be
assigned `T | undefined` explicitly rather than just omitted or assigned
`undefined`, which conflicts with the very common (and otherwise type-safe)
pattern used throughout this codebase of building a response object where
an optional field's value is itself `string | undefined` (e.g.
`AndroidDevice.manufacturer` from a `getprop` parse that may not find the
property). Enabling it would have meant threading `| undefined` through
most optional fields in `shared/src/types/*.ts` for no correctness benefit
here — `strict` already catches the bugs that flag is meant for elsewhere
(implicit `any`, unchecked `null`/`undefined` access).

## Known deviations from `docs/UI_SPEC.md`

`UI_SPEC.md`'s "Screen: App Shell" lists a sidebar of *Devices, Apps,
Monitoring, Screen Mirror, Files, Settings*. The Phase 2 task brief
specified *Dashboard, Devices, Screen Mirror, Tools, Settings* instead. This
is a genuine mismatch between the two source documents (both from this
project's own earlier phases), not something to silently paper over:

- **What was built:** the Phase 2 nav set, exactly as specified in this
  phase's instructions (`desktop/src/renderer/components/Sidebar.tsx`).
- **Reconciliation:** `Tools` is a placeholder page
  (`desktop/src/renderer/pages/Tools.tsx`) that names the three screens
  UI_SPEC.md describes separately (App Management, Shell/Logs, File
  Browser) as "coming later." When those features are actually implemented
  in a subsequent phase, `Tools` should split into those dedicated nav
  items, converging the sidebar onto UI_SPEC.md's fuller list. `Dashboard`
  (Phase 2) and UI_SPEC.md's "Device Dashboard" screen are the same screen
  under different sidebar labels — no functional gap there, just naming.
- Nothing was deleted or contradicted from UI_SPEC.md; the fuller structure
  is deferred, not abandoned.
