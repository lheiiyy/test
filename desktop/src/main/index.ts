import { app, BrowserWindow } from 'electron';
import path from 'node:path';
import { rootLogger } from './logging/logger.js';
import { NodeCommandRunner } from './services/adb/NodeCommandRunner.js';
import { AdbService } from './services/adb/AdbService.js';
import { ScrcpyService } from './services/scrcpy/ScrcpyService.js';
import { ScreenMirrorService } from './services/mirror/ScreenMirrorService.js';
import { DeviceRegistry } from './services/device/DeviceRegistry.js';
import { registerIpcHandlers } from './ipc/handlers.js';

// This file is bundled to CommonJS (see scripts/build-electron.mjs), so the
// native CJS `__dirname` is available and correct — no import.meta shim needed.
const logger = rootLogger.child('main');

// Allow overriding binary locations from the environment for now; a
// Settings screen (see docs/UI_SPEC.md "Screen: Settings") will replace this.
const adbPath = process.env.DROIDBRIDGE_ADB_PATH ?? 'adb';
const scrcpyPath = process.env.DROIDBRIDGE_SCRCPY_PATH ?? 'scrcpy';

const commandRunner = new NodeCommandRunner(adbPath);
const adbService = new AdbService(commandRunner, rootLogger.child('adb'));
const scrcpyService = new ScrcpyService(rootLogger.child('scrcpy'), scrcpyPath);
const mirrorService = new ScreenMirrorService(scrcpyService, rootLogger.child('mirror'));
const deviceRegistry = new DeviceRegistry(adbService, rootLogger.child('devices'));

function createWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 960,
    minHeight: 640,
    title: 'DroidBridge',
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  const devServerUrl = process.env.VITE_DEV_SERVER_URL;
  if (devServerUrl) {
    win.loadURL(devServerUrl);
  } else {
    win.loadFile(path.join(__dirname, '../../dist/index.html'));
  }

  return win;
}

app.whenReady().then(() => {
  registerIpcHandlers({
    adb: adbService,
    scrcpy: scrcpyService,
    devices: deviceRegistry,
    mirror: mirrorService,
    logger,
    appVersion: app.getVersion(),
  });

  logger.info('DroidBridge starting', { adbPath, scrcpyPath });
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
