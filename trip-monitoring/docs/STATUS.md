# Status: Trip Monitoring

## M1 Trips (issue #25): built, awaiting review and merge

- Done: schema (8 tables, ID keys, six audit columns), mock transport, repositories, trip status flow, role check, audit log.
- Not in M1: screens, `api.js`, real Sheets transport, deploy (manual step for the owner, later).

## Decisions

- Folder `trip-monitoring/` (the request left it blank).
- Plain JavaScript, no dependencies; tests use Node's built-in `node:test`.
- Status flow lives in one table in `src/services/trips.js`; a wrong status always reports an illegal transition first.
- Travellers can change only while the trip is Draft. Readings: start and end, end not below start, checked on Completed.
- Roles: requestor or driver create and submit; supervisor validates and returns to Draft; accounting completes; admin may do all. Requestor-only for own trips.
- IDs are never reused: soft-deleted rows stay, so the next ID is row count + 1.
- Sheets has no transactions: every write goes through `transport.withLock`.

## Test results

Command: `npm test` (or `node --test 'tests/*.test.js'`) in `trip-monitoring/`.
Result: 19 tests, 19 pass, 0 fail, 0 skipped.

## Not run (cloud session)

Any real Google Sheets or Apps Script call.
