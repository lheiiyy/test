import { describe, expect, it } from 'vitest';
import { PairingService } from './PairingService.js';

const nullLogger = { debug() {}, info() {}, warn() {}, error() {} };

describe('PairingService', () => {
  it('issues a session and accepts a matching consume() exactly once', async () => {
    const service = new PairingService(nullLogger);
    const { payload } = await service.createSession('192.168.1.11:41000');

    const first = service.consume(payload);
    expect(first.ok).toBe(true);

    const second = service.consume(payload);
    expect(second).toEqual({ ok: false, reason: 'already-used' });
  });

  it('rejects a payload for a session it never issued', async () => {
    const service = new PairingService(nullLogger);
    const other = new PairingService(nullLogger);
    const { payload } = await other.createSession('192.168.1.11:41000');

    const result = service.consume(payload);
    expect(result).toEqual({ ok: false, reason: 'unknown-session' });
  });

  it('rejects a payload with the right session id but a forged token', async () => {
    const service = new PairingService(nullLogger);
    const { payload } = await service.createSession('192.168.1.11:41000');

    const forged = { ...payload, token: 'f'.repeat(32) };
    const result = service.consume(forged);
    expect(result).toEqual({ ok: false, reason: 'unknown-session' });
  });

  it('rejects malformed input the same way the shared validator would', async () => {
    const service = new PairingService(nullLogger);
    const result = service.consume('not json');
    expect(result).toEqual({ ok: false, reason: 'malformed' });
  });

  it('produces a scannable QR data URL', async () => {
    const service = new PairingService(nullLogger);
    const { qrDataUrl } = await service.createSession('192.168.1.11:41000');
    expect(qrDataUrl).toMatch(/^data:image\/png;base64,/);
  });
});
