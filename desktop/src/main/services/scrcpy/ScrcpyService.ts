/**
 * Integration boundary for the `scrcpy` binary (https://github.com/Genymobile/scrcpy,
 * Apache-2.0 license). DroidBridge does not vendor a modified or unofficially-sourced
 * scrcpy build; see docs/ARCHITECTURE.md "scrcpy integration" for the documented
 * detection/launch/lifecycle/licensing plan this class exists to implement.
 *
 * Phase 2 scope: this is the service boundary and process-lifecycle contract only.
 * Nothing here launches a real scrcpy process yet — every method below either
 * performs a real, harmless check (isAvailable) or explicitly reports
 * "Not implemented in Phase 2" rather than pretending to succeed.
 */

import type { ScopedLogger } from '../../logging/logger.js';

export interface ScrcpyLaunchOptions {
  deviceSerial: string;
  maxSize?: number;
  bitRateKbps?: number;
  recordToPath?: string;
}

export interface ScrcpyProcessHandle {
  pid: number;
  deviceSerial: string;
}

export type ScrcpyAvailability =
  | { available: true; path: string; version?: string }
  | { available: false; reason: string };

export interface IScrcpyService {
  /** Real in Phase 2: checks PATH / configured binary location for `scrcpy --version`. */
  checkAvailability(): Promise<ScrcpyAvailability>;
  launch(options: ScrcpyLaunchOptions): Promise<ScrcpyProcessHandle>;
  terminate(pid: number): Promise<void>;
  onOutput(pid: number, listener: (chunk: string, stream: 'stdout' | 'stderr') => void): void;
}

const NOT_IMPLEMENTED = 'Not implemented in Phase 2';

export class ScrcpyService implements IScrcpyService {
  constructor(
    private readonly logger: ScopedLogger,
    private readonly binaryPath: string = 'scrcpy',
  ) {}

  async checkAvailability(): Promise<ScrcpyAvailability> {
    const { execFile } = await import('node:child_process');
    return new Promise((resolve) => {
      execFile(this.binaryPath, ['--version'], { timeout: 5000 }, (error, stdout) => {
        if (error) {
          this.logger.warn('scrcpy not available', { binaryPath: this.binaryPath, error: String(error) });
          resolve({ available: false, reason: `"${this.binaryPath}" not found on PATH` });
          return;
        }
        resolve({ available: true, path: this.binaryPath, version: stdout.split('\n')[0] });
      });
    });
  }

  launch(_options: ScrcpyLaunchOptions): Promise<ScrcpyProcessHandle> {
    // Deliberately unimplemented — see ScreenMirrorService, which owns the
    // session/state machine that will eventually call into a real launch().
    return Promise.reject(new Error(NOT_IMPLEMENTED));
  }

  terminate(_pid: number): Promise<void> {
    return Promise.reject(new Error(NOT_IMPLEMENTED));
  }

  onOutput(_pid: number, _listener: (chunk: string, stream: 'stdout' | 'stderr') => void): void {
    this.logger.debug(NOT_IMPLEMENTED);
  }
}
