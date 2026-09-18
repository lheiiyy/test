import { useAppStore } from '../state/appStore.js';
import { EmptyState } from '../components/EmptyState.js';

const STATE_LABEL: Record<string, string> = {
  disconnected: 'Disconnected',
  detecting: 'Detecting…',
  connecting: 'Connecting…',
  connected: 'Connected',
  unauthorized: 'Unauthorized on device',
  offline: 'Offline',
  error: 'Error',
};

export function Devices() {
  const devices = useAppStore((s) => s.devices);
  const loading = useAppStore((s) => s.loading);

  return (
    <div className="page">
      <p className="page__intro">
        Devices detected via <code>adb devices -l</code>. Pairing a new device (QR / manual code)
        lands in a later phase — see docs/UI_SPEC.md "Screen: Pairing".
      </p>

      {devices.length === 0 ? (
        <EmptyState
          title="No devices detected"
          description={loading ? 'Checking for devices…' : 'Connect a device over USB or the same Wi-Fi network.'}
        />
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Serial</th>
              <th>Transport</th>
              <th>State</th>
              <th>Model</th>
              <th>Android</th>
            </tr>
          </thead>
          <tbody>
            {devices.map((d) => (
              <tr key={d.serial}>
                <td>{d.serial}</td>
                <td>{d.transport}</td>
                <td>{STATE_LABEL[d.connectionState] ?? d.connectionState}</td>
                <td>{d.model ?? '—'}</td>
                <td>{d.androidVersion ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
