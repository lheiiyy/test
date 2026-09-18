import { describe, expect, it } from 'vitest';
import { ScreenMirrorService, InvalidMirrorTransitionError } from './ScreenMirrorService.js';
import type { IScrcpyService, ScrcpyAvailability } from '../scrcpy/ScrcpyService.js';

const nullLogger = { debug() {}, info() {}, warn() {}, error() {} };

function fakeScrcpy(availability: ScrcpyAvailability): IScrcpyService {
  return {
    checkAvailability: async () => availability,
    launch: async () => {
      throw new Error('Not implemented in Phase 2');
    },
    terminate: async () => {},
    onOutput: () => {},
  };
}

describe('ScreenMirrorService (Phase 2: state machine is real, transport is not)', () => {
  it('reports a clear error state when scrcpy is unavailable, rather than faking success', async () => {
    const service = new ScreenMirrorService(
      fakeScrcpy({ available: false, reason: 'scrcpy not found on PATH' }),
      nullLogger,
    );
    const session = await service.start('192.168.1.6:5555');
    expect(session.state).toBe('error');
    expect(session.lastError).toMatch(/not found/);
  });

  it('reports "Not implemented in Phase 2" when scrcpy is available but launch is a stub', async () => {
    const service = new ScreenMirrorService(
      fakeScrcpy({ available: true, path: '/usr/bin/scrcpy' }),
      nullLogger,
    );
    const session = await service.start('192.168.1.6:5555');
    expect(session.state).toBe('error');
    expect(session.lastError).toBe('Not implemented in Phase 2');
  });

  it('never reports an "active" session when nothing was actually started (no fake success)', async () => {
    const service = new ScreenMirrorService(
      fakeScrcpy({ available: true, path: '/usr/bin/scrcpy' }),
      nullLogger,
    );
    const session = await service.start('192.168.1.6:5555');
    expect(session.state).not.toBe('active');
  });

  it('rejects pausing a session that never left the error state', async () => {
    const service = new ScreenMirrorService(
      fakeScrcpy({ available: false, reason: 'unavailable' }),
      nullLogger,
    );
    const session = await service.start('192.168.1.6:5555');
    await expect(service.pause(session.id)).rejects.toBeInstanceOf(InvalidMirrorTransitionError);
  });

  it('lists sessions and exposes status lookups', async () => {
    const service = new ScreenMirrorService(
      fakeScrcpy({ available: false, reason: 'unavailable' }),
      nullLogger,
    );
    const session = await service.start('192.168.1.6:5555');
    expect(service.getStatus(session.id)?.id).toBe(session.id);
    expect(service.listSessions()).toHaveLength(1);
  });

  it('throws when acting on an unknown session id', async () => {
    const service = new ScreenMirrorService(
      fakeScrcpy({ available: false, reason: 'unavailable' }),
      nullLogger,
    );
    await expect(service.stop('does-not-exist')).rejects.toThrow(/Unknown mirror session/);
  });
});
