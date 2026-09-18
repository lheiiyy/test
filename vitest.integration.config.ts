import { defineConfig } from 'vitest/config';

// Root-level config for tests/integration only — these tests deliberately
// import across the shared/ and desktop/ package boundary (by relative path,
// not package name) to check that decisions made in one package (e.g. the
// shell command allowlist in shared/) are actually honored by the other
// (AdbService in desktop/). Package-internal unit tests stay colocated with
// their source and run via each workspace's own `npm run test`.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts'],
  },
});
