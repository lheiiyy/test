/**
 * The set of `adb shell` command *prefixes* DroidBridge will run without an
 * extra confirmation prompt, because they are read-only diagnostics with no
 * side effects on the device. Anything not matched here is still runnable
 * from the Shell screen (see UI_SPEC.md "Screen: Shell / Logs"), but only
 * after the operator explicitly confirms the literal command in a dialog.
 *
 * This list backs FEATURE_SPEC.md item #7 ("Execute shell command").
 * It is intentionally a desktop-side, local-only allowlist — it has nothing
 * to do with authorizing *remote* access, which Android's own USB/Wireless
 * debugging dialog already gates.
 */
export const ADB_READONLY_SHELL_PREFIXES: readonly string[] = [
  'getprop',
  'dumpsys battery',
  'dumpsys meminfo',
  'dumpsys cpuinfo',
  'dumpsys connectivity',
  'dumpsys package',
  'df',
  'ps',
  'pm list packages',
  'ip addr',
  'logcat',
];

export function isAllowlistedShellCommand(command: string): boolean {
  const normalized = command.trim();
  return ADB_READONLY_SHELL_PREFIXES.some(
    (prefix) => normalized === prefix || normalized.startsWith(`${prefix} `),
  );
}

/**
 * adb subcommands that must always require an explicit confirmation dialog
 * before running, regardless of allowlist status, because they change
 * device state (per FEATURE_SPEC.md's "every destructive operation must
 * require confirmation").
 */
export const DESTRUCTIVE_ADB_OPERATIONS: readonly string[] = [
  'reboot',
  'uninstall',
  'pm clear',
  'pm uninstall',
];
