import { describe, expect, it } from 'vitest';
import { DEVICE_CONNECTION_STATES, isValidDeviceStateTransition } from './device.js';

describe('device connection state transitions', () => {
  it('allows the documented happy path: disconnected -> connecting -> connected', () => {
    expect(isValidDeviceStateTransition('disconnected', 'connecting')).toBe(true);
    expect(isValidDeviceStateTransition('connecting', 'connected')).toBe(true);
  });

  it('allows a connected device to go offline and back', () => {
    expect(isValidDeviceStateTransition('connected', 'offline')).toBe(true);
    expect(isValidDeviceStateTransition('offline', 'connecting')).toBe(true);
  });

  it('allows an unauthorized device (declined on-device prompt) to retry', () => {
    expect(isValidDeviceStateTransition('connecting', 'unauthorized')).toBe(true);
    expect(isValidDeviceStateTransition('unauthorized', 'connecting')).toBe(true);
  });

  it('rejects jumping straight from disconnected to connected (must pass through connecting)', () => {
    expect(isValidDeviceStateTransition('disconnected', 'connected')).toBe(false);
  });

  it('rejects jumping from an idle disconnected state to offline', () => {
    expect(isValidDeviceStateTransition('disconnected', 'offline')).toBe(false);
  });

  it('treats staying in the same state as always valid (idempotent refresh)', () => {
    for (const state of DEVICE_CONNECTION_STATES) {
      expect(isValidDeviceStateTransition(state, state)).toBe(true);
    }
  });

  it('allows any state to recover to disconnected (manual disconnect always works)', () => {
    for (const state of DEVICE_CONNECTION_STATES) {
      if (state === 'disconnected') continue;
      // every state's transition table must be able to reach disconnected,
      // directly or (for detecting/connecting) via an intermediate step.
      const canDisconnectDirectly = isValidDeviceStateTransition(state, 'disconnected');
      const canErrorThenDisconnect =
        isValidDeviceStateTransition(state, 'error') &&
        isValidDeviceStateTransition('error', 'disconnected');
      expect(canDisconnectDirectly || canErrorThenDisconnect).toBe(true);
    }
  });
});
