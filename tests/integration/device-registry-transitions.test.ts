import { describe, expect, it } from 'vitest';
import type { AndroidDevice } from '../../shared/src/types/device.js';
import { DeviceRegistry } from '../../desktop/src/main/services/device/DeviceRegistry.js';
import type { IAdbService } from '../../desktop/src/main/services/adb/types.js';

/**
 * Confirms DeviceRegistry (desktop/) actually enforces the transition graph
 * declared in shared/src/types/device.ts, end to end through refresh() — not
 * just that the graph's own helper function returns the right booleans
 * (that's covered by shared/src/types/device.test.ts already).
 */

const nullLogger = { debug() {}, info() {}, warn() {}, error() {} };

function fakeAdb(devices: AndroidDevice[]): IAdbService {
  return {
    detectDevices: async () => devices,
    getDeviceInfo: async (serial) => devices.find((d) => d.serial === serial)!,
    getDeviceState: async (serial) => devices.find((d) => d.serial === serial)?.connectionState ?? 'disconnected',
    connect: async () => devices[0]!,
    disconnect: async () => {},
    executeAllowedOperation: async () => ({ stdout: '', stderr: '', exitCode: 0 }),
    executeConfirmedShellCommand: async () => ({ stdout: '', stderr: '', exitCode: 0 }),
  };
}

describe('DeviceRegistry honors the shared device-state transition graph', () => {
  it('accepts a device going disconnected -> connected across two refreshes via connecting', async () => {
    const serial = '192.168.1.6:5555';
    let deviceState: AndroidDevice[] = [];
    const adb: IAdbService = {
      ...fakeAdb([]),
      detectDevices: async () => deviceState,
    };
    const registry = new DeviceRegistry(adb, nullLogger);

    await registry.refresh();
    expect(registry.get(serial)).toBeUndefined();

    deviceState = [{ serial, transport: 'wifi', connectionState: 'connecting' }];
    await registry.refresh();
    expect(registry.get(serial)?.connectionState).toBe('connecting');

    deviceState = [{ serial, transport: 'wifi', connectionState: 'connected' }];
    await registry.refresh();
    expect(registry.get(serial)?.connectionState).toBe('connected');
  });

  it('marks a device disconnected once adb stops reporting it', async () => {
    const serial = '192.168.1.6:5555';
    let deviceState: AndroidDevice[] = [{ serial, transport: 'wifi', connectionState: 'connected' }];
    const adb: IAdbService = { ...fakeAdb([]), detectDevices: async () => deviceState };
    const registry = new DeviceRegistry(adb, nullLogger);

    await registry.refresh();
    expect(registry.get(serial)?.connectionState).toBe('connected');

    deviceState = [];
    await registry.refresh();
    expect(registry.get(serial)?.connectionState).toBe('disconnected');
  });

  it('ignores an illegal transition reported by adb instead of silently accepting it', async () => {
    const serial = '192.168.1.6:5555';
    let deviceState: AndroidDevice[] = [{ serial, transport: 'wifi', connectionState: 'disconnected' }];
    const adb: IAdbService = { ...fakeAdb([]), detectDevices: async () => deviceState };
    const registry = new DeviceRegistry(adb, nullLogger);
    await registry.refresh();

    // disconnected -> connected directly is not a legal transition (must pass through connecting).
    deviceState = [{ serial, transport: 'wifi', connectionState: 'connected' }];
    await registry.refresh();
    expect(registry.get(serial)?.connectionState).toBe('disconnected');
  });
});
