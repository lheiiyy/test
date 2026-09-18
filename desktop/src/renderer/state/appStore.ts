import { create } from 'zustand';
import type { AndroidDevice, AppStatus, MirrorSession } from '@droidbridge/shared';

export type NavSection = 'dashboard' | 'devices' | 'mirror' | 'tools' | 'settings';

interface AppState {
  activeSection: NavSection;
  setActiveSection: (section: NavSection) => void;

  devices: AndroidDevice[];
  appStatus: AppStatus | null;
  mirrorSessions: MirrorSession[];
  loading: boolean;
  error: string | null;

  refresh: () => Promise<void>;
}

export const useAppStore = create<AppState>((set) => ({
  activeSection: 'dashboard',
  setActiveSection: (section) => set({ activeSection: section }),

  devices: [],
  appStatus: null,
  mirrorSessions: [],
  loading: false,
  error: null,

  refresh: async () => {
    set({ loading: true, error: null });
    try {
      const [devices, appStatus, mirrorSessions] = await Promise.all([
        window.droidbridge.getDevices(),
        window.droidbridge.getAppStatus(),
        window.droidbridge.getMirrorSessions(),
      ]);
      set({ devices, appStatus, mirrorSessions, loading: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to load device status',
        loading: false,
      });
    }
  },
}));
