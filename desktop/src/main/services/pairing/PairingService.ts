/**
 * Owns the *desktop-issued* half of QR pairing: creating a short-lived session
 * and validating what comes back. See docs/PROTOCOL.md for the full design
 * and shared/src/protocol/pairing.ts for the wire format + structural/expiry
 * validation this class builds on.
 *
 * This class does not talk to Android at all — actually connecting still goes
 * through AdbService.connect(), using Android's own `adb pair`/`adb connect`.
 * PairingService's only job is: "is this QR content something *we* issued,
 * that hasn't expired, and that hasn't been used already?" A yes here means
 * "safe to attempt an adb pairing handshake with", not "device is now
 * connected" — Android's own on-device authorization dialog is still the
 * final gate DroidBridge cannot and does not bypass.
 */

import { randomBytes, randomUUID } from 'node:crypto';
import QRCode from 'qrcode';
import type { PairingPayload, PairingValidationResult } from '@droidbridge/shared';
import {
  PAIRING_PAYLOAD_VERSION,
  createPairingExpiry,
  validatePairingPayload,
} from '@droidbridge/shared';
import type { ScopedLogger } from '../../logging/logger.js';

interface IssuedSession {
  payload: PairingPayload;
  consumed: boolean;
}

export type PairingConsumptionResult =
  | { ok: true; payload: PairingPayload }
  | {
      ok: false;
      reason: 'malformed' | 'expired' | 'unsupported-version' | 'unknown-session' | 'already-used';
    };

export class PairingService {
  private readonly issued = new Map<string, IssuedSession>();

  constructor(private readonly logger: ScopedLogger) {}

  /**
   * Issues a new pairing session bound to the given LAN endpoint
   * (host:port that the desktop app's own pairing listener — added in a
   * later phase — will be reachable on). Returns both the raw payload (for
   * the "enter code manually" path) and a QR code data URL (for scanning).
   */
  async createSession(endpoint: string): Promise<{ payload: PairingPayload; qrDataUrl: string }> {
    const payload: PairingPayload = {
      version: PAIRING_PAYLOAD_VERSION,
      sessionId: randomUUID(),
      endpoint,
      token: randomBytes(24).toString('hex'),
      expiresAt: createPairingExpiry(),
    };
    this.issued.set(payload.sessionId, { payload, consumed: false });
    this.logger.info('Issued pairing session', {
      sessionId: payload.sessionId,
      endpoint: payload.endpoint,
      // token intentionally omitted — see logger.ts redaction list, belt-and-suspenders here too
    });
    const qrDataUrl = await QRCode.toDataURL(JSON.stringify(payload));
    return { payload, qrDataUrl };
  }

  /**
   * Validates and consumes a scanned/typed pairing payload. Single-use: a
   * second attempt with the same sessionId is rejected even if not expired.
   */
  consume(raw: unknown): PairingConsumptionResult {
    const result: PairingValidationResult = validatePairingPayload(raw);
    if (!result.ok) return result;

    const session = this.issued.get(result.payload.sessionId);
    if (!session) return { ok: false, reason: 'unknown-session' };
    if (session.consumed) return { ok: false, reason: 'already-used' };
    if (session.payload.token !== result.payload.token) {
      return { ok: false, reason: 'unknown-session' };
    }

    session.consumed = true;
    this.logger.info('Pairing session consumed', { sessionId: result.payload.sessionId });
    return { ok: true, payload: result.payload };
  }

  /** Housekeeping: drop expired/consumed sessions so this map can't grow unbounded. */
  sweepExpired(now: number = Date.now()): void {
    for (const [id, session] of this.issued) {
      if (session.consumed || session.payload.expiresAt <= now) {
        this.issued.delete(id);
      }
    }
  }
}
