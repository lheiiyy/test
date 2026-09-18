import { describe, expect, it, vi } from 'vitest';
import { AdbService } from './AdbService.js';
import { CommandNotAllowedError } from './types.js';
import type { CommandResult, CommandRunner } from './types.js';

function makeRunner(responses: Record<string, CommandResult>): CommandRunner {
  return {
    runAdb: vi.fn(async (args: string[]) => {
      const key = args.join(' ');
      const match = Object.entries(responses).find(([pattern]) => key.startsWith(pattern));
      if (!match) {
        throw new Error(`No mock response configured for: adb ${key}`);
      }
      return match[1];
    }),
  };
}

const nullLogger = { debug() {}, info() {}, warn() {}, error() {} };

describe('AdbService.detectDevices', () => {
  it('parses connected, unauthorized, and offline devices from `adb devices -l`', async () => {
    const runner = makeRunner({
      'devices -l': {
        exitCode: 0,
        stderr: '',
        stdout: [
          'List of devices attached',
          '192.168.1.6:5555       device product:oriole model:Pixel_6 transport_id:5',
          'R58N1234ABC            unauthorized usb:1-1 transport_id:3',
          'emulator-5554          offline',
          '',
        ].join('\n'),
      },
    });
    const service = new AdbService(runner, nullLogger);
    const devices = await service.detectDevices();

    expect(devices).toEqual([
      expect.objectContaining({ serial: '192.168.1.6:5555', connectionState: 'connected', transport: 'wifi' }),
      expect.objectContaining({ serial: 'R58N1234ABC', connectionState: 'unauthorized', transport: 'usb' }),
      expect.objectContaining({ serial: 'emulator-5554', connectionState: 'offline', transport: 'usb' }),
    ]);
  });

  it('returns an empty list when no devices are attached', async () => {
    const runner = makeRunner({
      'devices -l': { exitCode: 0, stderr: '', stdout: 'List of devices attached\n\n' },
    });
    const service = new AdbService(runner, nullLogger);
    expect(await service.detectDevices()).toEqual([]);
  });
});

describe('AdbService.getDeviceInfo', () => {
  it('enriches a connected device with parsed getprop fields', async () => {
    const runner = makeRunner({
      'devices -l': {
        exitCode: 0,
        stderr: '',
        stdout: 'List of devices attached\n192.168.1.6:5555\tdevice\n',
      },
      '-s 192.168.1.6:5555 shell getprop': {
        exitCode: 0,
        stderr: '',
        stdout: [
          '[ro.product.manufacturer]: [Google]',
          '[ro.product.model]: [Pixel 6]',
          '[ro.build.version.release]: [14]',
          '[ro.build.version.sdk]: [34]',
        ].join('\n'),
      },
    });
    const service = new AdbService(runner, nullLogger);
    const info = await service.getDeviceInfo('192.168.1.6:5555');

    expect(info).toMatchObject({
      serial: '192.168.1.6:5555',
      manufacturer: 'Google',
      model: 'Pixel 6',
      androidVersion: '14',
      apiLevel: 34,
      connectionState: 'connected',
    });
  });

  it('does not call getprop for a device that is not connected', async () => {
    const runner = makeRunner({
      'devices -l': {
        exitCode: 0,
        stderr: '',
        stdout: 'List of devices attached\nR58N1234ABC\tunauthorized\n',
      },
    });
    const service = new AdbService(runner, nullLogger);
    const info = await service.getDeviceInfo('R58N1234ABC');
    expect(info.connectionState).toBe('unauthorized');
    expect(runner.runAdb).toHaveBeenCalledTimes(1);
  });
});

describe('AdbService security boundary', () => {
  it('runs allowlisted read-only commands directly', async () => {
    const runner = makeRunner({
      '-s SERIAL shell dumpsys battery': { exitCode: 0, stderr: '', stdout: 'level: 80' },
    });
    const service = new AdbService(runner, nullLogger);
    const result = await service.executeAllowedOperation('SERIAL', 'dumpsys battery');
    expect(result.stdout).toContain('level: 80');
  });

  it('refuses a non-allowlisted command via the fast path', async () => {
    const runner = makeRunner({});
    const service = new AdbService(runner, nullLogger);
    await expect(service.executeAllowedOperation('SERIAL', 'rm -rf /sdcard')).rejects.toBeInstanceOf(
      CommandNotAllowedError,
    );
  });

  it('allows a non-allowlisted command only through the explicit confirmation path', async () => {
    const runner = makeRunner({
      '-s SERIAL shell rm -rf /sdcard/test': { exitCode: 0, stderr: '', stdout: '' },
    });
    const service = new AdbService(runner, nullLogger);
    await expect(
      service.executeConfirmedShellCommand('SERIAL', 'rm -rf /sdcard/test'),
    ).resolves.toBeDefined();
  });
});
