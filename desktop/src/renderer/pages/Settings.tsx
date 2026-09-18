import { useAppStore } from '../state/appStore.js';

export function Settings() {
  const appStatus = useAppStore((s) => s.appStatus);

  return (
    <div className="page">
      <p className="page__intro">
        Editable binary paths, the shell allowlist editor, and log export settings are planned
        (see docs/UI_SPEC.md "Screen: Settings"). This Phase 2 view shows current read-only status.
      </p>
      <dl className="settings-list">
        <div>
          <dt>DroidBridge version</dt>
          <dd>{appStatus?.version ?? '—'}</dd>
        </div>
        <div>
          <dt>adb detected</dt>
          <dd>{appStatus ? (appStatus.adbAvailable ? 'Yes' : 'No') : '—'}</dd>
        </div>
        <div>
          <dt>scrcpy detected</dt>
          <dd>{appStatus ? (appStatus.scrcpyAvailable ? 'Yes' : 'No') : '—'}</dd>
        </div>
      </dl>
    </div>
  );
}
