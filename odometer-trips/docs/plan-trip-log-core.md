# Plan: Odometer Trip Log, slice 1 (vehicles and trips)

Request: issue #9. Spec: `odometer-trips/specs/plan.md` (approved 2026-10-29). Project rules: `odometer-trips/CLAUDE.md`. Status document: this file's `## Status` section (Code adds it) and `odometer-trips/README.md`.

## 1. Business plan

- **Problem:** trips are logged by hand, and nothing checks that odometer readings agree with each other.
- **Users:** Leo, one user on one tablet (also desktop and phone).
- **Value:** record a trip in about 30 seconds, with bad readings rejected at once.
- **Scope:** modules M1 Vehicles (add, list, void) and M2 Trips (add with date, vehicle, start km, end km, purpose and destination; list with the distance of each trip; void). One page, data kept in browser storage.
- **Out of scope:** fuel, service, monthly report, CSV export, open trips (start now, end later), editing a trip (void and re-enter), sign-in, Sheets sync, deploy.
- **Success metrics:** an end reading below the start reading and a start reading below the vehicle's last end reading are both rejected; distance is calculated, never stored; data survives a reload; the main flow completes at 1280, 768 and 375 px with no console errors. The 30-second target is Leo's hand check on his tablet.
- **Risks:** (1) browser storage can be cleared and this slice has no export, so use test data only until CSV export is added (first task of slice 2, Leo decides); (2) the page loads ES modules, so it must be served over http(s), not opened as a file; (3) an odometer replacement or reset is blocked by the rules and is not handled; (4) Playwright and subagents in scheduled runs are UNVERIFIED (see Readiness).
- **Effort estimate:** six tasks, about 2 to 3 hourly Code cycles, plus one review round.

## 2. Architecture

- **Components:** `app/index.html`, `app/styles.css` and `app/main.js` (screens); `app/api.js` (API client); `app/services.js` (rules); `app/repository.js` (storage). Only the repository touches storage.
- **Data flow:** screen calls `api.js`, which calls a service, which calls the repository. The `transport` setting is `local` (browser storage) or `mock` (fixtures in `tests/fixtures/seed.json`).
- **Schema changes:** a new data model with four tables, each with the six audit columns (`created_at`, `created_by`, `updated_at`, `updated_by`, `is_active`, `row_version`): `vehicles` (VEH: name, plate, fuel_type, start_odometer_km), `trips` (TRP: vehicle_id, trip_date, start_km, end_km, purpose_id, destination, status Closed or Voided), `lookups` (LKP: group_name, value; seeded with trip purposes Work, Personal, Other) and `audit_log` (AUD: table_name, record_id, action, changed_at). This implements the model in `specs/plan.md` and changes nothing in it.
- **Integration points:** none. No external service, secret or network call.
- **Migration path:** the repository keeps one function set, so Phase 3 swaps in an Apps Script repository without touching services or screens. `row_version` is incremented on every update.
- **Key decisions:**
  - ES modules with the storage object passed in, so Node tests run without a browser or a new dependency.
  - Node's built-in `node:test`, because `CLAUDE.md` allows no new dependencies.
  - Trips are entered complete (both readings), to keep the slice small; the open-trip flow waits for slice 2.
  - Voiding sets `is_active` to false and writes an audit row; nothing is deleted.
  - The last end reading of a vehicle comes from its active closed trips, or from its starting odometer when it has none.
  - Dummy data only in tests and fixtures, because the repository is public.

## 3. Task breakdown

| # | Task | Agent | Files | Pass/fail check |
|---|---|---|---|---|
| 1 | Repository: tables, prefixed IDs, audit columns, audit_log, soft delete, purpose seed | Code | `app/repository.js`, `tests/unit/repository.test.mjs` | `node --test odometer-trips/tests/unit` passes; a second repository over the same storage returns the same rows |
| 2 | Services: vehicle rules, trip rules (both rejections), distance calculation, void | Code | `app/services.js`, `tests/unit/services.test.mjs` | Both invalid readings are rejected; distance equals end minus start and is not stored |
| 3 | API client with `local` and `mock` transports | Code | `app/api.js`, `tests/fixtures/seed.json`, `tests/unit/api.test.mjs` | Both transports return the same shapes |
| 4 | Screens: vehicle form and list, trip form and list, void button | Code | `app/index.html`, `app/styles.css`, `app/main.js` | Page loads over localhost with no console errors; a trip can be saved |
| 5 | Browser check at 1280, 768 and 375 px, saved as a rerunnable test | Code | `tests/e2e/trip-flow.cjs` | The flow completes at all three widths, with no console errors and no failed requests |
| 6 | Docs: run instructions, status and test results | Code | `README.md`, this plan file | Both name the run command and the results |

Model plan: build sonnet for tasks 1 to 5 and haiku for task 6 (documentation only); review opus (13 files, a big diff); fix sonnet, opus on a second attempt.

## 4. Test plan

- **Unit tests:** `node --test odometer-trips/tests/unit` covers the repository, the services and the API client with dummy data (a vehicle named "Test Bike", plate "TEST-001").
- **Browser check:** `node odometer-trips/tests/e2e/trip-flow.cjs` serves the folder with a small Node server, opens the page with the preinstalled Playwright and the `mock` transport, adds a vehicle, adds a trip, triggers both rejections, reloads, voids the trip, and repeats at 1280, 768 and 375 px.
- **Tests pass** means every unit test passes, the browser check exits 0, there are no console errors and no failed network calls.
- **Cannot run in a cloud session:** real touch on Leo's tablet and the 30-second hand timing. If Playwright is missing from the run, the browser check is reported as not run, and the Lead says so in the verdict.

## 5. Merge plan

- **Branch:** `claude/trip-log-core`, the branch of this plan PR.
- **Merge method:** merge commit.
- **Merge conditions:** Leo approved this plan; the Lead's verdict approves the exact head; the PR is clean and mergeable; only files under `odometer-trips/` changed. CI required: no (no workflow exists, and `.github/` is outside this project's allowed folder).
- **Release policy:** no deploy.

## 6. Readiness

| Item | Status | Note |
|---|---|---|
| Repository, labels, skill, issue form, merge commits | READY | Evidence from the readiness check on 2026-10-29 |
| Open PR #1 (android-parental-monitor) | READY | It touches no file under `odometer-trips/` |
| CI workflows | NEEDS SETUP | Optional. Adding one means editing `.github/`, which needs Leo's word |
| Branch protection on main | UNVERIFIED | The session token cannot read it (403); the merge script reports a refusal |
| Playwright in the scheduled Code run | UNVERIFIED | Installed in chat sessions; not confirmed for scheduled runs |
| Subagent for the opus review in a scheduled run | UNVERIFIED | Without one, the review runs on the task's model and says so |
| GitHub Pages | UNVERIFIED | The session proxy blocks the Pages API; needed only to open the app on a tablet |
| Connectors, secrets, database, external APIs, formal GitHub approval | NOT REQUIRED | None used; all agents share one account |

**What Leo does by hand:**
1. Reply `APPROVED` on issue #9 to build and merge.
2. After the merge, to try the app on the tablet: Settings → Pages → deploy from branch `main`, folder root. Then open `/odometer-trips/app/` on the site. Use test data only.
3. Decide later whether CSV export is the first task of slice 2.
4. Do not turn on "required approvals" on `main`.

APPROVED by lheiiyy on 2026-10-29

## Status

**Status:** built on `claude/trip-log-core` (tasks 1 to 6), waiting for the Lead's review. Not merged, no deploy.

**Run it**
- Unit tests: `node --test 'odometer-trips/tests/unit/*.test.mjs'`
- Browser check: `node odometer-trips/tests/e2e/trip-flow.cjs` (needs the preinstalled Playwright)
- App: serve the repo root over http (for example `python3 -m http.server`), open `/odometer-trips/app/`. Add `?transport=mock` for the test fixtures.

**Test results (2026-10-29, Node 22.23.4)**
- Unit: 27 of 27 passed (repository 10, services 10, API 7); the existing README test also passes (30 in all).
- Browser: passed at 1280, 768 and 375 px with the mock transport (add vehicle, both rejections, save trip, reload, two-tap void), plus a local-transport reload check. No console errors, failed requests or sideways scroll.
- Not run: real touch on Leo's tablet and the 30-second hand timing.

**Decisions made while building**
- The test command takes a glob: `node --test odometer-trips/tests/unit` (a folder) fails on Node 22.
- Node prints a `MODULE_TYPELESS_PACKAGE_JSON` warning for `app/*.js`; adding a `package.json` would be a new file outside the plan, so the warning stays.
- `odometer-trips/README.md` is unchanged: `tests/readme.test.mjs` requires a title and exactly one sentence, so run instructions and results live here.
- The mock transport keeps its own store (`sessionStorage`, key `odometer-trips:mock`) so a reload works in the browser check and test data never mixes with real data.
- Plates are stored in capitals and must be unique among active vehicles. Fuel type is one of Gasoline, Diesel, Electric, Hybrid, Other.
- Void needs two taps (Void, then Confirm void); there is no pop-up dialog.
