import { useAppStore } from '../state/appStore.js';
import { EmptyState } from '../components/EmptyState.js';

export function ScreenMirror() {
  const appStatus = useAppStore((s) => s.appStatus);
  const devices = useAppStore((s) => s.devices);
  const connected = devices.filter((d) => d.connectionState === 'connected');

  return (
    <div className="page">
      <div className={`banner ${appStatus?.scrcpyAvailable ? 'banner--info' : 'banner--warning'}`}>
        {appStatus?.scrcpyAvailable
          ? `scrcpy detected (${appStatus.scrcpyPath}).`
          : 'scrcpy was not found on this machine. Install it to enable screen mirroring — see docs/DEVELOPMENT.md.'}
      </div>

      {connected.length === 0 ? (
        <EmptyState
          title="No device to mirror"
          description="Connect a device first, then start a mirror session from here."
        />
      ) : (
        <EmptyState
          title="Screen mirroring is not implemented in Phase 2"
          description="The session state machine and scrcpy integration boundary exist (ScreenMirrorService, ScrcpyService) but launching a real mirrored view is scheduled for a later phase."
        />
      )}
    </div>
  );
}
