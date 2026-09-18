import { describe, expect, it } from 'vitest';
import {
  PAIRING_PAYLOAD_VERSION,
  createPairingExpiry,
  validatePairingPayload,
} from './pairing.js';

function validPayload(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    version: PAIRING_PAYLOAD_VERSION,
    sessionId: '123e4567-e89b-12d3-a456-426614174000',
    endpoint: '192.168.1.11:41000',
    token: 'a'.repeat(32),
    expiresAt: createPairingExpiry(),
    ...overrides,
  };
}

describe('validatePairingPayload', () => {
  it('accepts a well-formed, unexpired payload object', () => {
    const result = validatePairingPayload(validPayload());
    expect(result.ok).toBe(true);
  });

  it('accepts a well-formed payload passed as a JSON string (as scanned from a QR code)', () => {
    const result = validatePairingPayload(JSON.stringify(validPayload()));
    expect(result.ok).toBe(true);
  });

  it('rejects malformed JSON', () => {
    const result = validatePairingPayload('{not json');
    expect(result).toEqual({ ok: false, reason: 'malformed' });
  });

  it('rejects a payload missing required fields', () => {
    const { token: _drop, ...missingToken } = validPayload();
    const result = validatePairingPayload(missingToken);
    expect(result).toEqual({ ok: false, reason: 'malformed' });
  });

  it('rejects an unknown/future protocol version distinctly from other malformed payloads', () => {
    const result = validatePairingPayload(validPayload({ version: 99 }));
    expect(result).toEqual({ ok: false, reason: 'unsupported-version' });
  });

  it('rejects an expired payload', () => {
    const result = validatePairingPayload(
      validPayload({ expiresAt: Date.now() - 1000 }),
      Date.now(),
    );
    expect(result).toEqual({ ok: false, reason: 'expired' });
  });

  it('rejects an endpoint that is not a host:port pair', () => {
    const result = validatePairingPayload(validPayload({ endpoint: 'not-an-endpoint' }));
    expect(result.ok).toBe(false);
  });

  it('rejects a payload carrying extra/unknown fields (strict schema)', () => {
    const result = validatePairingPayload({
      ...validPayload(),
      password: 'should-never-be-here',
    });
    expect(result).toEqual({ ok: false, reason: 'malformed' });
  });

  it('rejects a non-object, non-string payload', () => {
    expect(validatePairingPayload(42)).toEqual({ ok: false, reason: 'malformed' });
    expect(validatePairingPayload(null)).toEqual({ ok: false, reason: 'malformed' });
  });
});
