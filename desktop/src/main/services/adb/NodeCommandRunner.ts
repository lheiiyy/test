import { execFile } from 'node:child_process';
import type { CommandResult, CommandRunner } from './types.js';
import { AdbNotFoundError } from './types.js';

/**
 * Real, process-spawning implementation of CommandRunner. This is the *only*
 * place in the desktop app that spawns `adb`. It always uses argv arrays
 * (never a shell string), so there is no command-injection surface here —
 * see docs/ARCHITECTURE.md "Security boundaries".
 */
export class NodeCommandRunner implements CommandRunner {
  constructor(private readonly adbPath: string = 'adb') {}

  async runAdb(args: string[], timeoutMs = 15_000): Promise<CommandResult> {
    return new Promise((resolve, reject) => {
      execFile(this.adbPath, args, { timeout: timeoutMs }, (error, stdout, stderr) => {
        if (error && (error as NodeJS.ErrnoException).code === 'ENOENT') {
          reject(new AdbNotFoundError(this.adbPath));
          return;
        }
        resolve({
          stdout: stdout.toString(),
          stderr: stderr.toString(),
          exitCode: error && typeof error.code === 'number' ? error.code : (error ? 1 : 0),
        });
      });
    });
  }
}
