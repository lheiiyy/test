import { z } from 'zod';

/**
 * QR pairing payload. See docs/PROTOCOL.md for the full rationale.
 *
 * Design constraints (from FEATURE_SPEC.md #2 and the project brief):
 *  - No permanent credentials ever travel in the QR code.
 *  - The payload is short-lived (expiresAt) and single-use (sessionId is
 *    consumed on first successful pairing attempt by the desktop app).
 *  - The QR code alone is never sufficient to connect: it only carries the
 *    *coordinates* (host/port) and a short-lived token used to look up a
 *    pairing session the desktop app itself created and is displaying. The
 *    actual authorization still happens through Android's own "Allow
 *    wireless debugging" system dialog on the phone — this payload cannot
 *    bypass that, by construction (DroidBridge never touches that dialog).
 */
export const PAIRING_PAYLOAD_VERSION = 1;

/** Pairing sessions are only ever valid for this long. */
export const PAIRING_SESSION_TTL_MS = 2 * 60 * 1000; // 2 minutes

export const pairingPayloadSchema = z
  .object({
    version: z.literal(PAIRING_PAYLOAD_VERSION),
    sessionId: z.string().uuid(),
    /** LAN endpoint the desktop app is listening on for this pairing session, e.g. "192.168.1.11:41000" */
    endpoint: z
      .string()
      .regex(
        /^(\d{1,3}\.){3}\d{1,3}:\d{1,5}$/,
        'endpoint must be an IPv4 host:port pair',
      ),
    /** Single-use, short-lived token — not a credential, just a session lookup key */
    token: z.string().min(16).max(128),
    /** Unix ms timestamp; payload MUST be rejected once Date.now() exceeds this */
    expiresAt: z.number().int().positive(),
  })
  .strict();

export type PairingPayload = z.infer<typeof pairingPayloadSchema>;

export type PairingValidationResult =
  | { ok: true; payload: PairingPayload }
  | { ok: false; reason: 'malformed' | 'expired' | 'unsupported-version' };

/**
 * Validates raw QR-scanned content (a JSON string) end to end: structural
 * validity, version support, and expiry. This is the single choke point the
 * desktop app must call before ever acting on scanned QR content — see
 * PairingService in docs/ARCHITECTURE.md.
 */
export function validatePairingPayload(
  raw: unknown,
  now: number = Date.now(),
): PairingValidationResult {
  let candidate: unknown = raw;
  if (typeof raw === 'string') {
    try {
      candidate = JSON.parse(raw);
    } catch {
      return { ok: false, reason: 'malformed' };
    }
  }

  const parsed = pairingPayloadSchema.safeParse(candidate);
  if (!parsed.success) {
    // A version mismatch is reported distinctly so the UI can say
    // "update DroidBridge" instead of a generic "invalid QR code".
    const versionIssue = parsed.error.issues.find((i) => i.path[0] === 'version');
    if (versionIssue) return { ok: false, reason: 'unsupported-version' };
    return { ok: false, reason: 'malformed' };
  }

  if (parsed.data.expiresAt <= now) {
    return { ok: false, reason: 'expired' };
  }

  return { ok: true, payload: parsed.data };
}

export function createPairingExpiry(now: number = Date.now()): number {
  return now + PAIRING_SESSION_TTL_MS;
}
