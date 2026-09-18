/**
 * In-memory source of truth for "what devices does the UI currently know
 * about", sitting between AdbService (stateless command execution) and the
 * IPC layer. Enforces the DEVICE_STATE_TRANSITIONS graph from
 * shared/src/types/device.ts so the UI can never observe an illegal jump
 * (e.g. disconnected -> connected without passing through connecting).
 */

import type { AndroidDevice, DeviceConnectionState } from '@droidbridge/shared';
import { isValidDeviceStateTransition } from '@droidbridge/shared';
import type { ScopedLogger } from '../../logging/logger.js';
import type { IAdbService } from '../adb/types.js';

export class DeviceRegistry {
  private readonly devices = new Map<string, AndroidDevice>();

  constructor(
    private readonly adb: IAdbService,
    private readonly logger: ScopedLogger,
  ) {}

  private setState(serial: string, state: DeviceConnectionState): void {
    const current = this.devices.get(serial);
    const from = current?.connectionState ?? 'disconnected';
    if (!isValidDeviceStateTransition(from, state)) {
      this.logger.warn('Ignored illegal device state transition', { serial, from, to: state });
      return;
    }
    this.devices.set(serial, { ...(current ?? { serial, transport: 'usb' }), connectionState: state });
  }

  /**
   * Never throws: a missing/unreachable `adb` binary is a normal, expected
   * state (see the project brief's "app must remain usable when no device
   * is connected"), surfaced separately via AppStatus.adbAvailable
   * (desktop/src/main/ipc/handlers.ts) rather than as a rejected promise
   * the renderer would have to special-case.
   */
  async refresh(): Promise<AndroidDevice[]> {
    let detected: AndroidDevice[];
    try {
      detected = await this.adb.detectDevices();
    } catch (err) {
      this.logger.warn('detectDevices failed; leaving existing device list unchanged', {
        error: err instanceof Error ? err.message : String(err),
      });
      return this.list();
    }
    for (const device of detected) {
      const existing = this.devices.get(device.serial);
      if (!existing) {
        this.devices.set(device.serial, device);
        continue;
      }
      if (isValidDeviceStateTransition(existing.connectionState, device.connectionState)) {
        this.devices.set(device.serial, { ...existing, ...device });
      } else {
        this.logger.warn('Ignored illegal device state transition during refresh', {
          serial: device.serial,
          from: existing.connectionState,
          to: device.connectionState,
        });
      }
    }
    // Devices no longer reported by `adb devices` are considered disconnected.
    for (const [serial, device] of this.devices) {
      if (!detected.some((d) => d.serial === serial) && device.connectionState !== 'disconnected') {
        this.setState(serial, 'disconnected');
      }
    }
    return this.list();
  }

  list(): AndroidDevice[] {
    return Array.from(this.devices.values());
  }

  get(serial: string): AndroidDevice | undefined {
    return this.devices.get(serial);
  }

  async connect(serial: string, connectFn: () => Promise<AndroidDevice>): Promise<AndroidDevice> {
    this.setState(serial, 'connecting');
    try {
      const device = await connectFn();
      this.devices.set(serial, device);
      return device;
    } catch (err) {
      this.setState(serial, 'error');
      throw err;
    }
  }

  async disconnect(serial: string): Promise<void> {
    await this.adb.disconnect(serial);
    this.setState(serial, 'disconnected');
  }
}
