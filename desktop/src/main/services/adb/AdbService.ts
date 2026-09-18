import type { AndroidDevice, DeviceConnectionState } from '@droidbridge/shared';
import { isAllowlistedShellCommand } from '@droidbridge/shared';
import type { ScopedLogger } from '../../logging/logger.js';
import type { CommandResult, CommandRunner, ConnectTarget, IAdbService } from './types.js';
import { CommandNotAllowedError } from './types.js';

/**
 * Parses one line of `adb devices -l` output, e.g.:
 *   "192.168.1.6:5555      device product:oriole model:Pixel_6 device:oriole transport_id:5"
 *   "R58N1234ABC           unauthorized usb:1-1 transport_id:3"
 */
function parseDevicesLine(line: string): { serial: string; state: DeviceConnectionState } | null {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith('List of devices')) return null;
  const [serial, rawState] = trimmed.split(/\s+/, 2);
  if (!serial || !rawState) return null;
  const stateMap: Record<string, DeviceConnectionState> = {
    device: 'connected',
    unauthorized: 'unauthorized',
    offline: 'offline',
  };
  return { serial, state: stateMap[rawState] ?? 'error' };
}

function parseGetprop(stdout: string): Record<string, string> {
  const props: Record<string, string> = {};
  // Lines look like: [ro.product.model]: [Pixel 6]
  const re = /^\[(.+?)\]:\s*\[(.*)\]$/;
  for (const line of stdout.split('\n')) {
    const match = re.exec(line.trim());
    if (match && match[1] !== undefined && match[2] !== undefined) {
      props[match[1]] = match[2];
    }
  }
  return props;
}

export class AdbService implements IAdbService {
  constructor(
    private readonly runner: CommandRunner,
    private readonly logger: ScopedLogger,
  ) {}

  async detectDevices(): Promise<AndroidDevice[]> {
    this.logger.info('Detecting devices via `adb devices -l`');
    const result = await this.runner.runAdb(['devices', '-l']);
    const devices: AndroidDevice[] = [];
    for (const line of result.stdout.split('\n')) {
      const parsed = parseDevicesLine(line);
      if (!parsed) continue;
      devices.push({
        serial: parsed.serial,
        transport: parsed.serial.includes(':') ? 'wifi' : 'usb',
        connectionState: parsed.state,
        lastSeenAt: new Date().toISOString(),
      });
    }
    this.logger.info('Device detection complete', { count: devices.length });
    return devices;
  }

  async getDeviceState(serial: string): Promise<DeviceConnectionState> {
    const devices = await this.detectDevices();
    return devices.find((d) => d.serial === serial)?.connectionState ?? 'disconnected';
  }

  async getDeviceInfo(serial: string): Promise<AndroidDevice> {
    const state = await this.getDeviceState(serial);
    if (state !== 'connected') {
      return {
        serial,
        transport: serial.includes(':') ? 'wifi' : 'usb',
        connectionState: state,
      };
    }
    const result = await this.runner.runAdb(['-s', serial, 'shell', 'getprop']);
    const props = parseGetprop(result.stdout);
    return {
      serial,
      transport: serial.includes(':') ? 'wifi' : 'usb',
      connectionState: 'connected',
      manufacturer: props['ro.product.manufacturer'],
      model: props['ro.product.model'],
      androidVersion: props['ro.build.version.release'],
      apiLevel: props['ro.build.version.sdk']
        ? Number.parseInt(props['ro.build.version.sdk'], 10)
        : undefined,
      lastSeenAt: new Date().toISOString(),
    };
  }

  async connect(target: ConnectTarget): Promise<AndroidDevice> {
    if (target.method === 'wifi') {
      this.logger.info('Connecting over Wi-Fi', { host: target.host, port: target.port });
      const result = await this.runner.runAdb(['connect', `${target.host}:${target.port}`]);
      if (!/connected to/i.test(result.stdout)) {
        this.logger.warn('adb connect did not report success', { stdout: result.stdout });
        return {
          serial: `${target.host}:${target.port}`,
          transport: 'wifi',
          connectionState: 'error',
          lastError: result.stdout.trim() || result.stderr.trim() || 'Unknown adb connect failure',
        };
      }
      return this.getDeviceInfo(`${target.host}:${target.port}`);
    }
    // USB devices are already visible via `adb devices` once authorized on-device;
    // "connecting" here just means confirming it shows up as authorized.
    this.logger.info('Confirming USB device authorization', { serial: target.serial });
    return this.getDeviceInfo(target.serial);
  }

  async disconnect(serial: string): Promise<void> {
    this.logger.info('Disconnecting device', { serial });
    if (serial.includes(':')) {
      await this.runner.runAdb(['disconnect', serial]);
    }
    // USB devices cannot be "disconnected" via adb (only unplugged); nothing to do.
  }

  async executeAllowedOperation(serial: string, command: string): Promise<CommandResult> {
    if (!isAllowlistedShellCommand(command)) {
      this.logger.warn('Blocked non-allowlisted command from the fast path', { command });
      throw new CommandNotAllowedError(command);
    }
    return this.runShell(serial, command);
  }

  async executeConfirmedShellCommand(serial: string, command: string): Promise<CommandResult> {
    this.logger.warn('Running operator-confirmed, non-allowlisted shell command', {
      serial,
      command,
    });
    return this.runShell(serial, command);
  }

  private async runShell(serial: string, command: string): Promise<CommandResult> {
    return this.runner.runAdb(['-s', serial, 'shell', ...command.split(' ')]);
  }
}
