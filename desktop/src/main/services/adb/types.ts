import type { AndroidDevice, DeviceConnectionState } from '@droidbridge/shared';

export interface CommandResult {
  stdout: string;
  stderr: string;
  exitCode: number | null;
}

/**
 * Thin seam over child_process so AdbService is unit-testable without a real
 * `adb` binary, and so every place that spawns a process goes through one
 * auditable choke point (see docs/ARCHITECTURE.md "Security boundaries").
 */
export interface CommandRunner {
  /** Runs `adb <args>`. Never invoked with unsanitized/concatenated shell strings — always argv arrays. */
  runAdb(args: string[], timeoutMs?: number): Promise<CommandResult>;
}

export type ConnectTarget =
  | { method: 'usb'; serial: string }
  | { method: 'wifi'; host: string; port: number };

export class AdbNotFoundError extends Error {
  constructor(adbPath: string) {
    super(`adb executable not found at "${adbPath}". Set it in Settings or install platform-tools.`);
    this.name = 'AdbNotFoundError';
  }
}

export class CommandNotAllowedError extends Error {
  constructor(command: string) {
    super(
      `Refusing to run non-allowlisted shell command without explicit confirmation: "${command}"`,
    );
    this.name = 'CommandNotAllowedError';
  }
}

export interface IAdbService {
  detectDevices(): Promise<AndroidDevice[]>;
  getDeviceInfo(serial: string): Promise<AndroidDevice>;
  getDeviceState(serial: string): Promise<DeviceConnectionState>;
  connect(target: ConnectTarget): Promise<AndroidDevice>;
  disconnect(serial: string): Promise<void>;
  /** Runs an allowlisted read-only diagnostic command; throws CommandNotAllowedError otherwise. */
  executeAllowedOperation(serial: string, command: string): Promise<CommandResult>;
  /** The only path for a non-allowlisted command — caller must have already shown the confirmation dialog. */
  executeConfirmedShellCommand(serial: string, command: string): Promise<CommandResult>;
}
