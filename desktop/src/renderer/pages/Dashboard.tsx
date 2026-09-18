import { useAppStore } from '../state/appStore.js';
import { EmptyState } from '../components/EmptyState.js';

export function Dashboard() {
  const devices = useAppStore((s) => s.devices);
  const appStatus = useAppStore((s) => s.appStatus);
  const loading = useAppStore((s) => s.loading);
  const error = useAppStore((s) => s.error);
  const setActiveSection = useAppStore((s) => s.setActiveSection);

  const connected = devices.filter((d) => d.connectionState === 'connected');

  return (
    <div className="page">
      {error ? <div className="banner banner--error">{error}</div> : null}

      {appStatus && !appStatus.adbAvailable ? (
        <div className="banner banner--warning">
          adb was not found on this machine. Install Android platform-tools or set its path in
          Settings to detect real devices.
        </div>
      ) : null}

      {connected.length === 0 && !loading ? (
        <EmptyState
          title="No Android device connected"
          description="Connect a device to begin."
          action={{ label: 'Connect a device', onClick: () => setActiveSection('devices') }}
        />
      ) : (
        <div className="card-grid">
          {connected.map((device) => (
            <div className="card" key={device.serial}>
              <h3>{device.model ?? device.serial}</h3>
              <dl className="card__stats">
                <div>
                  <dt>Manufacturer</dt>
                  <dd>{device.manufacturer ?? '—'}</dd>
                </div>
                <div>
                  <dt>Android version</dt>
                  <dd>{device.androidVersion ?? '—'}</dd>
                </div>
                <div>
                  <dt>API level</dt>
                  <dd>{device.apiLevel ?? '—'}</dd>
                </div>
                <div>
                  <dt>Transport</dt>
                  <dd>{device.transport}</dd>
                </div>
                <div>
                  <dt>Battery</dt>
                  <dd>
                    {device.battery
                      ? `${device.battery.levelPercent}%${device.battery.isCharging ? ' (charging)' : ''}`
                      : 'Not yet implemented'}
                  </dd>
                </div>
              </dl>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
