/**
 * Owns MirrorSession state (see shared/src/types/mirror.ts) and will eventually
 * delegate to ScrcpyService for the actual process. Deliberately decoupled from
 * React: this class knows nothing about IPC or renderer components, so it can
 * be unit-tested headlessly and swapped/mocked independently of the UI.
 *
 * Phase 2 scope: state machine + validation are real; starting/stopping an
 * actual mirrored video stream is not implemented yet (ScrcpyService.launch()
 * is a stub) — start() surfaces that plainly instead of faking success.
 */

import type { MirrorSession, MirrorSettings } from '@droidbridge/shared';
import { DEFAULT_MIRROR_SETTINGS, isValidMirrorStateTransition } from '@droidbridge/shared';
import { randomUUID } from 'node:crypto';
import type { ScopedLogger } from '../../logging/logger.js';
import type { IScrcpyService } from '../scrcpy/ScrcpyService.js';

export class InvalidMirrorTransitionError extends Error {
  constructor(from: string, to: string) {
    super(`Invalid mirror session transition: ${from} -> ${to}`);
    this.name = 'InvalidMirrorTransitionError';
  }
}

export interface IScreenMirrorService {
  start(deviceSerial: string, settings?: Partial<MirrorSettings>): Promise<MirrorSession>;
  stop(sessionId: string): Promise<void>;
  pause(sessionId: string): Promise<void>;
  resume(sessionId: string): Promise<void>;
  getStatus(sessionId: string): MirrorSession | undefined;
  listSessions(): MirrorSession[];
}

export class ScreenMirrorService implements IScreenMirrorService {
  private readonly sessions = new Map<string, MirrorSession>();

  constructor(
    private readonly scrcpy: IScrcpyService,
    private readonly logger: ScopedLogger,
  ) {}

  private transition(session: MirrorSession, to: MirrorSession['state']): MirrorSession {
    if (!isValidMirrorStateTransition(session.state, to)) {
      throw new InvalidMirrorTransitionError(session.state, to);
    }
    const updated: MirrorSession = { ...session, state: to };
    this.sessions.set(session.id, updated);
    return updated;
  }

  async start(deviceSerial: string, settings?: Partial<MirrorSettings>): Promise<MirrorSession> {
    let session: MirrorSession = {
      id: randomUUID(),
      deviceSerial,
      state: 'idle',
      settings: { ...DEFAULT_MIRROR_SETTINGS, ...settings },
    };
    this.sessions.set(session.id, session);
    session = this.transition(session, 'starting');

    const availability = await this.scrcpy.checkAvailability();
    if (!availability.available) {
      session = this.transition(session, 'error');
      this.sessions.set(session.id, { ...session, lastError: availability.reason });
      this.logger.error('Cannot start screen mirror: scrcpy unavailable', {
        deviceSerial,
        reason: availability.reason,
      });
      return this.sessions.get(session.id)!;
    }

    try {
      await this.scrcpy.launch({ deviceSerial, ...settings });
      // Unreachable until ScrcpyService.launch() is implemented (Phase 2 stub
      // always rejects) — kept so the happy path is already correct for when it is.
      session = this.transition(session, 'active');
      const started = { ...session, startedAt: new Date().toISOString() };
      this.sessions.set(started.id, started);
      return started;
    } catch (err) {
      session = this.transition(session, 'error');
      const message = 'Not implemented in Phase 2';
      this.sessions.set(session.id, { ...session, lastError: message });
      this.logger.warn('Screen mirror start is not implemented yet', {
        deviceSerial,
        error: err instanceof Error ? err.message : String(err),
      });
      return this.sessions.get(session.id)!;
    }
  }

  async stop(sessionId: string): Promise<void> {
    const session = this.requireSession(sessionId);
    const stopping = this.transition(session, 'stopping');
    this.transition(stopping, 'idle');
  }

  async pause(sessionId: string): Promise<void> {
    const session = this.requireSession(sessionId);
    this.transition(session, 'paused');
  }

  async resume(sessionId: string): Promise<void> {
    const session = this.requireSession(sessionId);
    this.transition(session, 'active');
  }

  getStatus(sessionId: string): MirrorSession | undefined {
    return this.sessions.get(sessionId);
  }

  listSessions(): MirrorSession[] {
    return Array.from(this.sessions.values());
  }

  private requireSession(sessionId: string): MirrorSession {
    const session = this.sessions.get(sessionId);
    if (!session) throw new Error(`Unknown mirror session: ${sessionId}`);
    return session;
  }
}
