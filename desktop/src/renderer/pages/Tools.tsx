const UPCOMING = [
  { name: 'App Management', detail: 'Install / uninstall / list packages / clear data / force stop' },
  { name: 'Shell & Logs', detail: 'Allowlisted shell commands, logcat viewer' },
  { name: 'File Browser', detail: 'Explicit, operator-initiated file transfer' },
];

export function Tools() {
  return (
    <div className="page">
      <p className="page__intro">
        This Phase 2 skeleton establishes navigation only. Each of the following will become its
        own screen (per docs/UI_SPEC.md) as its service is implemented in a later phase — nothing
        here performs any device operation yet.
      </p>
      <ul className="upcoming-list">
        {UPCOMING.map((item) => (
          <li key={item.name} className="upcoming-list__item">
            <strong>{item.name}</strong>
            <span>{item.detail}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
