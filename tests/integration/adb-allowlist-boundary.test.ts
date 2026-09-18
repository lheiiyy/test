import { describe, expect, it, vi } from 'vitest';
import { ADB_READONLY_SHELL_PREFIXES, isAllowlistedShellCommand } from '../../shared/src/constants/adbAllowlist.js';
import { AdbService } from '../../desktop/src/main/services/adb/AdbService.js';
import { CommandNotAllowedError } from '../../desktop/src/main/services/adb/types.js';
import type { CommandResult, CommandRunner } from '../../desktop/src/main/services/adb/types.js';

/**
 * Confirms the security decision recorded in shared/src/constants/adbAllowlist.ts
 * (FEATURE_SPEC.md #7: "a command allowlist covers read-only diagnostic
 * commands by default") is actually enforced by AdbService, not just declared.
 * A change to the allowlist that AdbService doesn't honor — or an AdbService
 * change that bypasses the allowlist — should fail this test.
 */

const nullLogger = { debug() {}, info() {}, warn() {}, error() {} };

function stubRunner(): CommandRunner {
  const result: CommandResult = { stdout: 'ok', stderr: '', exitCode: 0 };
  return { runAdb: vi.fn(async () => result) };
}

describe('shared allowlist <-> AdbService security boundary', () => {
  it('lets every declared read-only prefix through executeAllowedOperation', async () => {
    const runner = stubRunner();
    const service = new AdbService(runner, nullLogger);
    for (const prefix of ADB_READONLY_SHELL_PREFIXES) {
      await expect(service.executeAllowedOperation('SERIAL', prefix)).resolves.toBeDefined();
    }
  });

  it('blocks anything the shared allowlist does not recognize', async () => {
    const runner = stubRunner();
    const service = new AdbService(runner, nullLogger);
    const disallowed = ['reboot', 'pm uninstall com.example', 'rm -rf /sdcard', 'input keyevent 4'];
    for (const command of disallowed) {
      expect(isAllowlistedShellCommand(command)).toBe(false);
      await expect(service.executeAllowedOperation('SERIAL', command)).rejects.toBeInstanceOf(
        CommandNotAllowedError,
      );
    }
  });
});
