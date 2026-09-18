/**
 * Device model shared between the desktop main process, renderer, and (conceptually)
 * the Android companion app's status reporting.
 *
 * Every field here must be obtainable from an authorized device via documented
 * Android/ADB mechanisms (`adb devices`, `adb shell getprop`, `dumpsys battery`, etc.).
 * See docs/FEATURE_SPEC.md for the exact command backing each field.
 */

export type DeviceConnectionState =
  | 'disconnected'
  | 'detecting'
  | 'connecting'
  | 'connected'
  | 'unauthorized'
  | 'offline'
  | 'error';

export type DeviceTransport = 'usb' | 'wifi';

export interface BatteryInfo {
  /** 0-100 */
  levelPercent: number;
  isCharging: boolean;
  /** e.g. "ac", "usb", "wireless", "none" — from `dumpsys battery` */
  powerSource: 'ac' | 'usb' | 'wireless' | 'none' | 'unknown';
  temperatureCelsius?: number;
}

export interface StorageInfo {
  totalBytes: number;
  freeBytes: number;
}

export interface MemoryInfo {
  totalBytes: number;
  availableBytes: number;
}

/**
 * Legitimately obtainable, non-sensitive device identity/state.
 * Deliberately excludes anything that would require special/dangerous
 * permissions to read (IMEI, SIM data, contacts, location, etc.).
 */
export interface AndroidDevice {
  /** adb serial, e.g. "192.168.1.6:5555" or a USB serial number */
  serial: string;
  manufacturer?: string;
  model?: string;
  /** e.g. "14" */
  androidVersion?: string;
  /** e.g. 34 */
  apiLevel?: number;
  transport: DeviceTransport;
  connectionState: DeviceConnectionState;
  battery?: BatteryInfo;
  storage?: StorageInfo;
  memory?: MemoryInfo;
  /** ISO-8601 timestamp of the last successful status refresh */
  lastSeenAt?: string;
  /** Present only when connectionState === 'error' */
  lastError?: string;
}

export const DEVICE_CONNECTION_STATES: readonly DeviceConnectionState[] = [
  'disconnected',
  'detecting',
  'connecting',
  'connected',
  'unauthorized',
  'offline',
  'error',
];

/**
 * The allowed state transition graph. Used by both the desktop device registry
 * and its tests to make sure nothing jumps to/from a state it shouldn't.
 */
export const DEVICE_STATE_TRANSITIONS: Readonly<
  Record<DeviceConnectionState, readonly DeviceConnectionState[]>
> = {
  disconnected: ['detecting', 'connecting'],
  detecting: ['connecting', 'disconnected', 'unauthorized', 'error'],
  connecting: ['connected', 'unauthorized', 'offline', 'error', 'disconnected'],
  connected: ['offline', 'disconnected', 'error'],
  unauthorized: ['connecting', 'disconnected'],
  offline: ['connecting', 'disconnected'],
  error: ['disconnected', 'connecting'],
};

export function isValidDeviceStateTransition(
  from: DeviceConnectionState,
  to: DeviceConnectionState,
): boolean {
  if (from === to) return true;
  return DEVICE_STATE_TRANSITIONS[from].includes(to);
}
