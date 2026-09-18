import { useEffect } from 'react';
import { Sidebar } from './components/Sidebar.js';
import { TopBar } from './components/TopBar.js';
import { Dashboard } from './pages/Dashboard.js';
import { Devices } from './pages/Devices.js';
import { ScreenMirror } from './pages/ScreenMirror.js';
import { Tools } from './pages/Tools.js';
import { Settings } from './pages/Settings.js';
import { useAppStore } from './state/appStore.js';

const SECTION_TITLES: Record<string, string> = {
  dashboard: 'Dashboard',
  devices: 'Devices',
  mirror: 'Screen Mirror',
  tools: 'Tools',
  settings: 'Settings',
};

export function App() {
  const activeSection = useAppStore((s) => s.activeSection);
  const setActiveSection = useAppStore((s) => s.setActiveSection);
  const devices = useAppStore((s) => s.devices);
  const loading = useAppStore((s) => s.loading);
  const refresh = useAppStore((s) => s.refresh);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="app-shell">
      <Sidebar active={activeSection} onSelect={setActiveSection} />
      <div className="app-shell__main">
        <TopBar
          title={SECTION_TITLES[activeSection] ?? 'DroidBridge'}
          devices={devices}
          loading={loading}
          onRefresh={() => void refresh()}
        />
        <main className="app-shell__content">
          {activeSection === 'dashboard' && <Dashboard />}
          {activeSection === 'devices' && <Devices />}
          {activeSection === 'mirror' && <ScreenMirror />}
          {activeSection === 'tools' && <Tools />}
          {activeSection === 'settings' && <Settings />}
        </main>
      </div>
    </div>
  );
}
