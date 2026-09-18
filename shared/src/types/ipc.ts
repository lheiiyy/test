import type { AndroidDevice } from './device.js';
import type { MirrorSession, MirrorSettings } from './mirror.js';
import type { PairingPayload } from '../protocol/pairing.js';

/**
 * The complete, closed set of operations the renderer is allowed to request
 * from the Electron main process. This is the *entire* privileged surface —
 * nothing else is reachable from renderer code. See docs/ARCHITECTURE.md
 * "IPC" section and desktop/src/preload/index.ts.
 *
 * Phase 2 note: handlers exist for every channel below, but several return a
 * "not implemented in Phase 2" result rather than performing the real
 * operation — see FEATURE_SPEC.md / ARCHITECTURE.md for what's real vs. stubbed.
 */
export interface DroidBridgeIpcApi {
  getAppStatus(): Promise<AppStatus>;
  getDevices(): Promise<AndroidDevice[]>;
  connectDevice(request: ConnectDeviceRequest): Promise<ConnectDeviceResult>;
  disconnectDevice(serial: string): Promise<{ ok: boolean }>;
  startMirror(request: StartMirrorRequest): Promise<StartMirrorResult>;
  stopMirror(sessionId: string): Promise<{ ok: boolean }>;
  getMirrorSessions(): Promise<MirrorSession[]>;
}

export const IPC_CHANNELS = {
  getAppStatus: 'droidbridge:getAppStatus',
  getDevices: 'droidbridge:getDevices',
  connectDevice: 'droidbridge:connectDevice',
  disconnectDevice: 'droidbridge:disconnectDevice',
  startMirror: 'droidbridge:startMirror',
  stopMirror: 'droidbridge:stopMirror',
  getMirrorSessions: 'droidbridge:getMirrorSessions',
} as const;

export type IpcChannel = (typeof IPC_CHANNELS)[keyof typeof IPC_CHANNELS];

export interface AppStatus {
  version: string;
  adbAvailable: boolean;
  adbPath?: string;
  scrcpyAvailable: boolean;
  scrcpyPath?: string;
}

export type ConnectDeviceRequest =
  | { method: 'qr'; payload: PairingPayload }
  | { method: 'manual'; ip: string; port: number; pairingCode?: string }
  | { method: 'usb'; serial: string };

export interface ConnectDeviceResult {
  ok: boolean;
  device?: AndroidDevice;
  error?: string;
}

export interface StartMirrorRequest {
  deviceSerial: string;
  settings?: Partial<MirrorSettings>;
}

export interface StartMirrorResult {
  ok: boolean;
  session?: MirrorSession;
  error?: string;
}

/**
 * Runtime validators for requests crossing the IPC boundary. The main
 * process must never trust renderer input structurally — even though the
 * renderer is our own code, the preload bridge is the one place an
 * injected/compromised renderer could try to send malformed data, so every
 * handler re-validates with these before touching AdbService/ScrcpyService.
 */
export function isConnectDeviceRequest(value: unknown): value is ConnectDeviceRequest {
  if (typeof value !== 'object' || value === null) return false;
  const v = value as Record<string, unknown>;
  if (v.method === 'usb') return typeof v.serial === 'string' && v.serial.length > 0;
  if (v.method === 'manual') {
    return (
      typeof v.ip === 'string' &&
      v.ip.length > 0 &&
      typeof v.port === 'number' &&
      Number.isInteger(v.port) &&
      v.port > 0 &&
      v.port <= 65535
    );
  }
  if (v.method === 'qr') return typeof v.payload === 'object' && v.payload !== null;
  return false;
}

export function isStartMirrorRequest(value: unknown): value is StartMirrorRequest {
  if (typeof value !== 'object' || value === null) return false;
  const v = value as Record<string, unknown>;
  return typeof v.deviceSerial === 'string' && v.deviceSerial.length > 0;
}
