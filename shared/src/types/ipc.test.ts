import { describe, expect, it } from 'vitest';
import { isConnectDeviceRequest, isStartMirrorRequest } from './ipc.js';

describe('isConnectDeviceRequest', () => {
  it('accepts a valid usb request', () => {
    expect(isConnectDeviceRequest({ method: 'usb', serial: 'R58N1234ABC' })).toBe(true);
  });

  it('accepts a valid manual (ip/port) request', () => {
    expect(isConnectDeviceRequest({ method: 'manual', ip: '192.168.1.6', port: 5555 })).toBe(true);
  });

  it('accepts a valid qr request shape', () => {
    expect(isConnectDeviceRequest({ method: 'qr', payload: { sessionId: 'x' } })).toBe(true);
  });

  it('rejects a usb request with a missing serial', () => {
    expect(isConnectDeviceRequest({ method: 'usb' })).toBe(false);
  });

  it('rejects a manual request with a non-numeric port', () => {
    expect(isConnectDeviceRequest({ method: 'manual', ip: '192.168.1.6', port: '5555' })).toBe(false);
  });

  it('rejects a manual request with an out-of-range port', () => {
    expect(isConnectDeviceRequest({ method: 'manual', ip: '192.168.1.6', port: 70000 })).toBe(false);
  });

  it('rejects an unknown method', () => {
    expect(isConnectDeviceRequest({ method: 'telnet', ip: '1.2.3.4' })).toBe(false);
  });

  it('rejects non-object input', () => {
    expect(isConnectDeviceRequest('usb')).toBe(false);
    expect(isConnectDeviceRequest(null)).toBe(false);
    expect(isConnectDeviceRequest(undefined)).toBe(false);
  });
});

describe('isStartMirrorRequest', () => {
  it('accepts a request with a device serial', () => {
    expect(isStartMirrorRequest({ deviceSerial: '192.168.1.6:5555' })).toBe(true);
  });

  it('rejects a request without a device serial', () => {
    expect(isStartMirrorRequest({})).toBe(false);
  });

  it('rejects a request with an empty device serial', () => {
    expect(isStartMirrorRequest({ deviceSerial: '' })).toBe(false);
  });

  it('rejects non-object input', () => {
    expect(isStartMirrorRequest(42)).toBe(false);
  });
});
