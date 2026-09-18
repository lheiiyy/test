import type { DroidBridgeIpcApi } from '@droidbridge/shared';

declare global {
  interface Window {
    /** Exposed by src/preload/index.ts via contextBridge — the entire privileged surface. */
    droidbridge: DroidBridgeIpcApi;
  }
}

export {};
