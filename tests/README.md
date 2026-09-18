# tests/

Cross-package integration tests only. Package-internal unit tests live
colocated with their source (`shared/src/**/*.test.ts`,
`desktop/src/**/*.test.ts`) so they're easy to find and keep in sync with the
code they test — see `docs/ARCHITECTURE.md` "Testing strategy" for the full
rationale on this split.

Run everything (unit + integration): `npm test` from the repo root.
Run just this folder: `npm run test:integration` from the repo root.
