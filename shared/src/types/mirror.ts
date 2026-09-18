/**
 * Types for the screen-mirroring feature (backed by scrcpy). See
 * desktop/src/main/services/mirror/ScreenMirrorService.ts and
 * desktop/src/main/services/scrcpy/ScrcpyService.ts for the Phase 2
 * (placeholder) implementations.
 */

export type MirrorConnectionState =
  | 'idle'
  | 'starting'
  | 'active'
  | 'paused'
  | 'stopping'
  | 'error';

export interface MirrorSettings {
  /** Max long-edge resolution passed to scrcpy's --max-size */
  maxSize?: number;
  /** kbps, passed to scrcpy's --video-bit-rate */
  bitRateKbps?: number;
  /** Forward device audio through scrcpy (Android 11+ only) */
  audio: boolean;
  /** Record the session to this local file path (operator-chosen), if set */
  recordToPath?: string;
}

export const DEFAULT_MIRROR_SETTINGS: MirrorSettings = {
  audio: false,
};

export interface MirrorSession {
  id: string;
  deviceSerial: string;
  state: MirrorConnectionState;
  settings: MirrorSettings;
  startedAt?: string;
  /** Present only when state === 'error' */
  lastError?: string;
}

export const MIRROR_STATE_TRANSITIONS: Readonly<
  Record<MirrorConnectionState, readonly MirrorConnectionState[]>
> = {
  idle: ['starting'],
  starting: ['active', 'error', 'idle'],
  active: ['paused', 'stopping', 'error'],
  paused: ['active', 'stopping', 'error'],
  stopping: ['idle', 'error'],
  error: ['idle'],
};

export function isValidMirrorStateTransition(
  from: MirrorConnectionState,
  to: MirrorConnectionState,
): boolean {
  if (from === to) return true;
  return MIRROR_STATE_TRANSITIONS[from].includes(to);
}
