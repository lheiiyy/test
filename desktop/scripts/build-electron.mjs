// Bundles the Electron main process and preload script with esbuild.
//
// Why esbuild directly, instead of `tsc` emitting JS: the main/preload code
// imports the `@droidbridge/shared` workspace package by its TypeScript
// source (no separate compiled dist step for that package — see
// docs/ARCHITECTURE.md "Desktop architecture" for the rationale). esbuild
// resolves and inlines that TS source directly, the same way Vite already
// does for the renderer; `tsc` alone cannot execute the result, only type-check it.
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');

const shared = {
  bundle: true,
  platform: 'node',
  target: 'node18',
  format: 'cjs',
  sourcemap: true,
  external: ['electron'],
  logLevel: 'info',
};

await build({
  ...shared,
  entryPoints: [path.join(root, 'src/main/index.ts')],
  outfile: path.join(root, 'dist-electron/main/index.js'),
});

await build({
  ...shared,
  entryPoints: [path.join(root, 'src/preload/index.ts')],
  outfile: path.join(root, 'dist-electron/preload/index.js'),
});
