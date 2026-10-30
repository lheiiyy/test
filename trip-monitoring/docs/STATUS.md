# Status: Trip Monitoring

## M1 Trips (issue #25): merged

- Done: schema (8 tables, ID keys, six audit columns), mock transport, repositories, trip status flow, role check, audit log.
- Not in M1: real Sheets transport, deploy (manual step for the owner, later).

## M1 screens (issue #27, PR #28): merged (a41046c), Lead approved head f397295

- Done: `listTrips`, `getTrip`, `lookups`, `updateTrip` services; `src/api.js` (mock transport, `{ok, data}` or `{ok:false, error}`); trip list and trip form in `src/web/` with a role switcher for the mock user; design tokens in `app.css` and `CLAUDE.md`.
- Not in this slice: expenses, liquidation, monitoring, real Sheets transport, Apps Script deploy.

## Decisions

- Folder `trip-monitoring/` (the request left it blank).
- Plain JavaScript, no dependencies; tests use Node's built-in `node:test`.
- Status flow lives in one table in `src/services/trips.js`; a wrong status always reports an illegal transition first.
- Travellers can change only while the trip is Draft. Readings: start and end, end not below start, checked on Completed.
- Roles: requestor or driver create and submit; supervisor validates and returns to Draft; accounting completes; admin may do all. Requestor-only for own trips.
- Round 1 fixes: readings change only while Draft, one start and one end per trip; only a Draft trip can be deleted; audit time uses the injected clock.
- `audit_log` is append-only by convention: services only insert, but its repository still exposes `update` and `softDelete` (a known limitation, to harden later).
- IDs are never reused: soft-deleted rows stay, so the next ID is row count + 1.
- Sheets has no transactions: every write goes through `transport.withLock`.

## Test results

Command: `npm test` (or `node --test 'tests/*.test.js'`) in `trip-monitoring/`.
Result: 22 tests, 22 pass, 0 fail, 0 skipped.

## M1 screens decisions

- No dependency: a small loader in `src/web/app.js` runs the CommonJS `src/` files in the browser, each in its own hidden iframe so top-level names cannot clash.
- Mock state and the acting user are kept in `sessionStorage` so list and form pages share data; closing the tab resets it. `api.exportState()` and `transport.snapshot()` are mock only.
- `src/web/seed.js` repeats the dummy fixture for the browser; a test keeps it equal to `tests/fixtures/seed.json`.
- The UI hides actions by role but the services still refuse every wrong call (tested).
- Requestor or driver see their own trips; supervisor, accounting and admin see all.
- Found while testing: `.btn` overrode `hidden`, so a supervisor saw "New trip"; fixed with `[hidden]` in `app.css`.
- Playwright is used by `tests/screens.test.js` but is not a project dependency; it must be installed where tests run (preinstalled in cloud sessions).

## M1 screens test results

Command: `npm test` in `trip-monitoring/`. Result: 38 tests, 38 pass, 0 fail, 0 skipped. Browser flows run with no console errors; 15 screenshots at 1280, 768 and 375 px.

## Not run (cloud session)

Any real Google Sheets or Apps Script call.
