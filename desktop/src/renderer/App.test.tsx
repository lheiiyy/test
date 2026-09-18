// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from './App.js';
import { useAppStore } from './state/appStore.js';

// Vitest doesn't auto-register RTL's cleanup the way Jest does unless
// `test.globals: true` is set (it isn't, deliberately — see vitest.config.ts),
// so each render() must be explicitly unmounted or renders from earlier
// tests in this file leak into later ones' DOM queries.
afterEach(() => cleanup());

function mockIpc(overrides: Partial<Window['droidbridge']> = {}) {
  window.droidbridge = {
    getAppStatus: vi.fn().mockResolvedValue({
      version: '0.1.0',
      adbAvailable: false,
      scrcpyAvailable: false,
    }),
    getDevices: vi.fn().mockResolvedValue([]),
    getMirrorSessions: vi.fn().mockResolvedValue([]),
    connectDevice: vi.fn(),
    disconnectDevice: vi.fn(),
    startMirror: vi.fn(),
    stopMirror: vi.fn(),
    ...overrides,
  };
}

describe('App shell', () => {
  beforeEach(() => {
    useAppStore.setState({
      activeSection: 'dashboard',
      devices: [],
      appStatus: null,
      mirrorSessions: [],
      loading: false,
      error: null,
    });
  });

  it('renders the sidebar navigation items', () => {
    mockIpc();
    render(<App />);
    expect(screen.getByText('DroidBridge')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Dashboard' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Devices' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Screen Mirror' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Tools' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Settings' })).toBeInTheDocument();
  });

  it('shows the "no device connected" empty state when there are no connected devices', async () => {
    mockIpc();
    render(<App />);
    await waitFor(() => expect(screen.getByText('No Android device connected')).toBeInTheDocument());
    expect(screen.getByText('Connect a device to begin.')).toBeInTheDocument();
  });

  it('shows a connected device on the dashboard once IPC resolves', async () => {
    mockIpc({
      getDevices: vi.fn().mockResolvedValue([
        {
          serial: '192.168.1.6:5555',
          transport: 'wifi',
          connectionState: 'connected',
          model: 'Pixel 6',
          manufacturer: 'Google',
          androidVersion: '14',
          apiLevel: 34,
        },
      ]),
    });
    render(<App />);
    await waitFor(() => expect(screen.getByText('Pixel 6')).toBeInTheDocument());
    expect(screen.queryByText('No Android device connected')).not.toBeInTheDocument();
  });
});
