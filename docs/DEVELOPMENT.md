# Development — DroidBridge

## Prerequisites

- Node.js ≥ 18.18 (developed/tested against Node 22)
- npm ≥ 10 (ships with modern Node; this repo uses npm workspaces)
- Java 17+ (for the Android project's Gradle build)
- [Android SDK](https://developer.android.com/studio) with `platform-tools`,
  `adb` on your `PATH`, for real device connections
- [scrcpy](https://github.com/Genymobile/scrcpy) on your `PATH`, for screen
  mirroring (once implemented past Phase 2) — official builds only, see
  `docs/ARCHITECTURE.md` "scrcpy integration"

None of the above are required just to look at/edit the code or run the
desktop UI against an empty device list — the app is designed to stay usable
with `adb`/`scrcpy` missing (see the Dashboard/Screen Mirror empty states).

## Install dependencies

From the repo root (this installs `shared` and `desktop`'s dependencies via
npm workspaces in one pass):

```sh
npm install
```

## Run the desktop app in development

```sh
npm run dev
```

This starts the Vite dev server (renderer, with hot reload) and, once it's
listening, bundles the Electron main/preload processes with esbuild and
launches Electron pointed at the dev server. If you change main-process or
preload code, re-run `npm run dev` to pick it up (main/preload are not
hot-reloaded in Phase 2 — only the renderer is, via Vite).

## Build

```sh
npm run build
```

Builds the shared package's standalone type-checked output, the renderer
(`desktop/dist`), and the bundled main/preload processes
(`desktop/dist-electron`). This does **not** yet produce a packaged
installer/executable (no `electron-builder`/`electron-forge` wired up) —
that's deferred past Phase 2's scope.

## Run tests

```sh
npm test
```

Runs, in order: `shared`'s unit tests, `desktop`'s unit tests (services +
the renderer smoke test), then the root-level cross-package integration
tests in `tests/`. Run any one layer individually:

```sh
npm run test --workspace shared
npm run test --workspace desktop
npm run test:integration
```

## Type-check

```sh
npm run typecheck
```

Runs `tsc --noEmit` for `shared`, then for `desktop` twice — once against
the renderer's DOM+bundler config (`desktop/tsconfig.json`) and once against
the main/preload's bare-Node config (`desktop/tsconfig.electron.json`), since
they target different runtimes and shouldn't share one `include` set.

## Lint / format

```sh
npm run lint           # eslint across shared/ and desktop/
npm run format         # prettier --write
npm run format:check   # prettier --check, for CI
```

## Build the Android companion app

```sh
cd android
./gradlew assembleDebug
```

**Known limitation of this repository's development sandbox:** the Gradle
wrapper here (`android/gradlew`) was generated and is committed, but a full
`assembleDebug` could not be executed or verified during Phase 2 development
in this project's sandboxed CI-like environment — outbound network access to
Google's Maven repository (`dl.google.com`, which serves the Android Gradle
Plugin and SDK platform artifacts) is blocked by that environment's egress
policy, and no Android SDK is installed there at all. This is an environment
limitation, not a known defect in the Gradle configuration — `android/build.gradle.kts`,
`android/app/build.gradle.kts`, and `android/settings.gradle.kts` are
ordinary, valid Android Gradle Plugin 8.6.1 / Kotlin 2.0.21 / Gradle 8.9
configuration and should build normally with:

- Android Studio (any recent version) with its bundled SDK manager, or
- A machine with the Android SDK installed and `ANDROID_HOME`/`ANDROID_SDK_ROOT`
  set, and normal (unrestricted) internet access to `dl.google.com` and
  `repo.maven.apache.org`.

If you hit a Gradle/AGP version-compatibility error on a real machine,
check the [AGP release notes](https://developer.android.com/build/releases/gradle-plugin)
for the Gradle version your AGP release requires and update
`android/gradle/wrapper/gradle-wrapper.properties` accordingly — this repo
pins Gradle 8.9 for AGP 8.6.1.

## Environment variables (desktop)

| Variable | Purpose | Default |
|---|---|---|
| `DROIDBRIDGE_ADB_PATH` | Path to the `adb` executable | `adb` (resolved via `PATH`) |
| `DROIDBRIDGE_SCRCPY_PATH` | Path to the `scrcpy` executable | `scrcpy` (resolved via `PATH`) |
| `DROIDBRIDGE_LOG_LEVEL` | Minimum log level (`DEBUG`/`INFO`/`WARN`/`ERROR`) | `INFO` |

A Settings screen to edit these without restarting is planned (see
`docs/UI_SPEC.md` "Screen: Settings") but not implemented in Phase 2 —
the current Settings page is read-only status display.

## Repository layout

```
desktop/     Electron + React + TypeScript + Vite app
android/     Kotlin companion app (Gradle)
shared/      Types, pairing protocol, IPC contract, constants — consumed
             as TypeScript source by both desktop's renderer and main/preload
             bundles (see docs/ARCHITECTURE.md for why there's no compiled
             build step in that runtime path)
tests/       Cross-package integration tests only (see tests/README.md)
docs/        This documentation set
```
