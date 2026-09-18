import type { AndroidDevice } from '@droidbridge/shared';

interface DeviceStatusPillProps {
  devices: AndroidDevice[];
  loading: boolean;
}

function summarize(devices: AndroidDevice[], loading: boolean): { tone: 'green' | 'amber' | 'red'; label: string } {
  if (loading) return { tone: 'amber', label: 'Checking…' };
  const connected = devices.filter((d) => d.connectionState === 'connected').length;
  if (connected > 0) {
    return { tone: 'green', label: `${connected} connected` };
  }
  const pending = devices.filter((d) =>
    ['connecting', 'detecting', 'unauthorized'].includes(d.connectionState),
  ).length;
  if (pending > 0) return { tone: 'amber', label: 'Connecting…' };
  return { tone: 'red', label: 'No device connected' };
}

export function DeviceStatusPill({ devices, loading }: DeviceStatusPillProps) {
  const { tone, label } = summarize(devices, loading);
  return (
    <div className={`status-pill status-pill--${tone}`} role="status">
      <span className="status-pill__dot" aria-hidden="true" />
      {label}
    </div>
  );
}
