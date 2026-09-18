/**
 * The ONLY bridge between the sandboxed renderer and the privileged main
 * process. contextIsolation is on and nodeIntegration is off (see
 * src/main/index.ts's BrowserWindow config) — the renderer has no `require`,
 * no `process`, and no direct filesystem/child_process access. It can only
 * call the specific, typed methods exposed here, each of which maps to
 * exactly one validated IPC round-trip. See docs/ARCHITECTURE.md "IPC".
 */
import { contextBridge, ipcRenderer } from 'electron';
import { IPC_CHANNELS } from '@droidbridge/shared';
import type {
  AppStatus,
  AndroidDevice,
  ConnectDeviceRequest,
  ConnectDeviceResult,
  DroidBridgeIpcApi,
  MirrorSession,
  StartMirrorRequest,
  StartMirrorResult,
} from '@droidbridge/shared';

const api: DroidBridgeIpcApi = {
  getAppStatus: (): Promise<AppStatus> => ipcRenderer.invoke(IPC_CHANNELS.getAppStatus),
  getDevices: (): Promise<AndroidDevice[]> => ipcRenderer.invoke(IPC_CHANNELS.getDevices),
  connectDevice: (request: ConnectDeviceRequest): Promise<ConnectDeviceResult> =>
    ipcRenderer.invoke(IPC_CHANNELS.connectDevice, request),
  disconnectDevice: (serial: string): Promise<{ ok: boolean }> =>
    ipcRenderer.invoke(IPC_CHANNELS.disconnectDevice, serial),
  startMirror: (request: StartMirrorRequest): Promise<StartMirrorResult> =>
    ipcRenderer.invoke(IPC_CHANNELS.startMirror, request),
  stopMirror: (sessionId: string): Promise<{ ok: boolean }> =>
    ipcRenderer.invoke(IPC_CHANNELS.stopMirror, sessionId),
  getMirrorSessions: (): Promise<MirrorSession[]> =>
    ipcRenderer.invoke(IPC_CHANNELS.getMirrorSessions),
};

contextBridge.exposeInMainWorld('droidbridge', api);
