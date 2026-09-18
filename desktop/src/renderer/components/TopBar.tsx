import type { AndroidDevice } from '@droidbridge/shared';
import { DeviceStatusPill } from './DeviceStatusPill.js';

interface TopBarProps {
  title: string;
  devices: AndroidDevice[];
  loading: boolean;
  onRefresh: () => void;
}

export function TopBar({ title, devices, loading, onRefresh }: TopBarProps) {
  return (
    <header className="top-bar">
      <h1 className="top-bar__title">{title}</h1>
      <div className="top-bar__actions">
        <DeviceStatusPill devices={devices} loading={loading} />
        <button type="button" className="button button--ghost" onClick={onRefresh} disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>
    </header>
  );
}
