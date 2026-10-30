# Plan: m1-trips (Trip Monitoring, M1 Trips at the repository layer)

Issue #25. Project folder (the request left it blank, so this plan sets it): `trip-monitoring/`. Status document Code updates: `trip-monitoring/docs/STATUS.md` (new).

## 1. Business plan

- **Problem:** trips are tracked by hand; there is no single register with a clear status, validation or audit trail.
- **Users:** requestor or driver (creates and submits), supervisor (validates), Accounting (completes), Admin (users, lookups). Must work on desktop, tablet and phone.
- **Value:** one trip register with ID-keyed data, an enforced status flow and an audit log.
- **Scope (v1, M1 only):** tables trips (TRP), trip_travellers (TTV), vehicle_readings (ODO), plus users, teams, vehicles, lookups, audit_log. Status flow Draft, Submitted, Trip validated, Completed, and a return to Draft when a trip has a problem. Work stops at the **repository layer** with a mock transport and tests, plus the service rules the issue names (role check, validation).
- **Out of scope:** screens, `api.js`, live Sheets or Apps Script deploy, real data, reports, notifications, other modules (M2+), hard delete.
- **Success metrics:** every planned test passes on the mock transport; every table carries audit columns; no hard delete anywhere; zero tokens or real data in the repo.
- **Risks:** a data model change later is costly (mitigated: one schema file, versioned); Sheets has no transactions (mitigated: single-writer lock in the repository); role checks done only in the UI (mitigated: server-side check in the service layer).
- **Effort estimate:** 6 tasks, one Code session of roughly 1 to 2 days.

## 2. Architecture

- **Components:** four layers: screens, `api.js`, services, repository. This slice builds the repository (`src/repository/`) and the services that enforce rules (`src/services/`); screens and `api.js` are not touched.
- **Data flow:** service, then repository, then transport. The transport is an interface; the mock transport reads and writes in-memory sheets loaded from `tests/fixtures/`. The real Sheets transport is a later manual step for the owner.
- **Schema (new, M1):** one sheet per table, a header row, one value per cell. Key columns are IDs (`TRP-0001`, `TTV-0001`, `ODO-0001`), never names. Every table has audit columns `created_at`, `created_by`, `updated_at`, `updated_by`, `deleted_at`, `deleted_by`. trips holds `status`, `requestor_id`, `vehicle_id`, `team_id`; trip_travellers links `trip_id` and `user_id`; vehicle_readings holds `trip_id`, `vehicle_id`, `kind` (start or end) and `reading`. audit_log is append-only.
- **Integration points:** none live. Google Sheets and Apps Script are reached only through the transport interface.
- **Migration path:** greenfield, so no data migration. Later schema changes go through a `schema_version` lookup row. Rollback note: nothing to roll back in this slice; removing the new folder restores the repo.
- **Key decisions:**
  - IDs as keys, so renaming a person or vehicle never breaks a trip.
  - Soft delete only (`deleted_at`), so history and audit stay intact.
  - Status transitions live in one table in the service, so the flow is testable.
  - Role check in the service on every call, since the UI is not trusted.
  - Plain JavaScript (Apps Script V8) with no dependencies, so the plan adds none.

## 3. Task breakdown

| # | Task | Agent | Files | Pass/fail check |
|---|---|---|---|---|
| 1 | Schema and fixtures: table definitions, audit columns, sample fake rows | Code | `trip-monitoring/src/schema.js`, `trip-monitoring/tests/fixtures/` | schema test: each table has its ID key and the six audit columns |
| 2 | Mock transport and repository base: get, list, insert, update, soft delete, ID generation | Code | `trip-monitoring/src/repository/` | repository tests: CRUD works, delete only sets `deleted_at` |
| 3 | Trips, travellers and readings repositories | Code | `trip-monitoring/src/repository/` | tests: a trip with travellers and readings saves and loads by ID |
| 4 | Status flow and validation service | Code | `trip-monitoring/src/services/trips.js` | tests: legal transitions pass, illegal ones fail, return to Draft works |
| 5 | Role check and audit log on every write | Code | `trip-monitoring/src/services/` | tests: wrong role is refused; each write adds an audit row |
| 6 | Test runner, CLAUDE.md fill-in and STATUS.md | Code | `trip-monitoring/package.json` (scripts only), `trip-monitoring/docs/STATUS.md`, `CLAUDE.md` | `node --test` exits 0 and prints the pass count |

Model plan: build sonnet; review opus (a big diff); fix sonnet, opus on a second attempt.

## 4. Test plan

- **Tested:** schema shape, repository CRUD, soft delete, ID generation, status transitions, role checks, audit rows, one value per cell, no real data.
- **Tooling:** Node's built-in `node:test` (no dependency) on the mock transport with `tests/fixtures/`.
- **"Tests pass" means:** the test command (`node --test` in `trip-monitoring/`) exits 0 with no failures or skips.
- **Cannot run in a cloud session:** any real Google Sheets or Apps Script call; deploy is a manual step for the owner. No screen changes, so no 1280/768/375 screenshots are needed.

## 5. Merge plan

- **Branch:** `claude/m1-trips`.
- **Merge method:** merge commit.
- **Conditions:** an approved Lead verdict on the exact head, green checks if CI exists, and the owner's APPROVED on this plan.
- **Release policy:** no deploy.

Risk: normal
CI required: no
Files in scope: trip-monitoring/, CLAUDE.md

## 6. Readiness

| Item | Status | Evidence / note |
|---|---|---|
| Repository access, default branch main | READY | repo is public, merge commits allowed |
| Loop labels, skill, issue form | READY | all present |
| Node for the test runner | UNVERIFIED | Code confirms `node --version` when the build starts |
| Mock transport and fixtures | READY | built in this plan, fake data only |
| Branch protection on main | UNVERIFIED | the session token cannot read it; the merge script reports a refusal |
| CI workflow for tests | NOT REQUIRED | `CI required: no`; tests run in the Code session |
| Google Sheet, Apps Script project, clasp | NOT REQUIRED | no live deploy in M1 |
| Hosting, external APIs, costs | NOT REQUIRED | none used; the repo is public, so only fake data |
| Project folder name | NEEDS SETUP | the issue left it blank; this plan uses `trip-monitoring/` |

**Owner checklist (by hand):**
- [ ] Confirm the folder name `trip-monitoring/` (or reply `REVISE:` with another).
- [ ] Later, for M2: create the real Sheet and Apps Script project; nothing is needed for M1.

APPROVED by lheiiyy on 2026-10-30
