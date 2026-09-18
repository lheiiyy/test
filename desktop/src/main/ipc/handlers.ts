/**
 * Registers every privileged operation the renderer is allowed to invoke.
 * This is the complete, closed IPC surface — see shared/src/types/ipc.ts for
 * the channel list and docs/ARCHITECTURE.md "IPC" for why nothing else is
 * reachable from the renderer (no generic "runCommand" channel exists).
 */
import { ipcMain } from 'electron';
import {
  IPC_CHANNELS,
  isConnectDeviceRequest,
  isStartMirrorRequest,
} from '@droidbridge/shared';
import type { AppStatus, ConnectDeviceResult, StartMirrorResult } from '@droidbridge/shared';
import type { ScopedLogger } from '../logging/logger.js';
import type { DeviceRegistry } from '../services/device/DeviceRegistry.js';
import type { IAdbService } from '../services/adb/types.js';
import type { IScrcpyService } from '../services/scrcpy/ScrcpyService.js';
import type { IScreenMirrorService } from '../services/mirror/ScreenMirrorService.js';

export interface IpcDependencies {
  adb: IAdbService;
  scrcpy: IScrcpyService;
  devices: DeviceRegistry;
  mirror: IScreenMirrorService;
  logger: ScopedLogger;
  appVersion: string;
}

export function registerIpcHandlers(deps: IpcDependencies): void {
  const { adb, scrcpy, devices, mirror, logger, appVersion } = deps;

  ipcMain.handle(IPC_CHANNELS.getAppStatus, async (): Promise<AppStatus> => {
    const scrcpyStatus = await scrcpy.checkAvailability();
    // Checked directly against AdbService (not devices.refresh(), which
    // deliberately never throws — see DeviceRegistry.refresh()'s docstring)
    // so a missing adb binary is still accurately reported here.
    const adbAvailable = await adb
      .detectDevices()
      .then(() => true)
      .catch(() => false);
    return {
      version: appVersion,
      adbAvailable,
      scrcpyAvailable: scrcpyStatus.available,
      scrcpyPath: scrcpyStatus.available ? scrcpyStatus.path : undefined,
    };
  });

  ipcMain.handle(IPC_CHANNELS.getDevices, async () => {
    return devices.refresh();
  });

  ipcMain.handle(IPC_CHANNELS.connectDevice, async (_event, request: unknown): Promise<ConnectDeviceResult> => {
    if (!isConnectDeviceRequest(request)) {
      logger.warn('Rejected malformed connectDevice request from renderer');
      return { ok: false, error: 'Malformed connect request' };
    }
    try {
      if (request.method === 'usb') {
        const device = await devices.connect(request.serial, () => adb.getDeviceInfo(request.serial));
        return { ok: true, device };
      }
      if (request.method === 'manual') {
        const serial = `${request.ip}:${request.port}`;
        const device = await devices.connect(serial, () =>
          adb.connect({ method: 'wifi', host: request.ip, port: request.port }),
        );
        return { ok: true, device };
      }
      // QR-based pairing is validated by PairingService before this channel
      // is ever called (see docs/ARCHITECTURE.md "Pairing Service") — Phase 2
      // wires the type but the renderer doesn't have a working QR scanner yet.
      return { ok: false, error: 'QR pairing is not wired up to a live scanner in Phase 2' };
    } catch (err) {
      logger.error('connectDevice failed', { error: err instanceof Error ? err.message : String(err) });
      return { ok: false, error: err instanceof Error ? err.message : 'Unknown connection error' };
    }
  });

  ipcMain.handle(IPC_CHANNELS.disconnectDevice, async (_event, serial: unknown) => {
    if (typeof serial !== 'string' || serial.length === 0) {
      return { ok: false };
    }
    await devices.disconnect(serial);
    return { ok: true };
  });

  ipcMain.handle(IPC_CHANNELS.startMirror, async (_event, request: unknown): Promise<StartMirrorResult> => {
    if (!isStartMirrorRequest(request)) {
      return { ok: false, error: 'Malformed start-mirror request' };
    }
    const session = await mirror.start(request.deviceSerial, request.settings);
    if (session.state === 'error') {
      return { ok: false, session, error: session.lastError };
    }
    return { ok: true, session };
  });

  ipcMain.handle(IPC_CHANNELS.stopMirror, async (_event, sessionId: unknown) => {
    if (typeof sessionId !== 'string' || sessionId.length === 0) {
      return { ok: false };
    }
    await mirror.stop(sessionId).catch((err) => {
      logger.warn('stopMirror failed', { error: err instanceof Error ? err.message : String(err) });
    });
    return { ok: true };
  });

  ipcMain.handle(IPC_CHANNELS.getMirrorSessions, async () => {
    return mirror.listSessions();
  });
}
