import type { NavSection } from '../state/appStore.js';

interface NavItem {
  id: NavSection;
  label: string;
}

// Phase 2 nav set, per the Phase 2 brief. UI_SPEC.md's fuller breakdown
// (Devices / Apps / Monitoring / Screen Mirror / Files / Settings) lands
// later: "Tools" here is a placeholder that will split into Apps, Shell/Logs,
// and Files as those features are implemented (see docs/ARCHITECTURE.md
// "Known deviations from UI_SPEC.md").
const NAV_ITEMS: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'devices', label: 'Devices' },
  { id: 'mirror', label: 'Screen Mirror' },
  { id: 'tools', label: 'Tools' },
  { id: 'settings', label: 'Settings' },
];

interface SidebarProps {
  active: NavSection;
  onSelect: (section: NavSection) => void;
}

export function Sidebar({ active, onSelect }: SidebarProps) {
  return (
    <nav className="sidebar" aria-label="Primary">
      <div className="sidebar__brand">DroidBridge</div>
      <ul className="sidebar__list">
        {NAV_ITEMS.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              className={`sidebar__item${active === item.id ? ' sidebar__item--active' : ''}`}
              onClick={() => onSelect(item.id)}
              aria-current={active === item.id ? 'page' : undefined}
            >
              {item.label}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
