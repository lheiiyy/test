# Plan: m1-screens (Trip Monitoring, M1 part 2: Trips screens and api.js)

Issue #27. Project folder: `trip-monitoring/`. Status document Code updates: `trip-monitoring/docs/STATUS.md`. Builds on PR #26 (22 tests pass).

## 1. Business plan

- **Problem:** the trip rules exist (PR #26) but nobody can use them; there is no screen.
- **Users:** requestor or driver (create, edit while Draft, submit), supervisor (validate, return), Accounting (complete), Admin (all). Desktop, tablet and phone.
- **Value:** a working trip register UI on the mock transport, with no Google sign-in, that proves the flow end to end before the real Sheets transport.
- **Scope:** trip list screen, trip form screen, role switcher for the mock user, `api.js` with the `mock` transport, small service additions (list, edit Draft) the screens need.
- **Out of scope:** expenses, liquidation, monitoring, real Sheets transport, Apps Script deploy, real data, notifications.
- **Success metrics:** every role completes its actions in the UI on the mock; all tests pass; screenshots at 1280, 768 and 375 px; no console errors; no real data.
- **Risks:** the services lack `listTrips` and `updateTrip` (mitigated: added in task 1, no schema change); design tokens not set (mitigated: proposed below); UI trusted for roles (mitigated: services still check every call).
- **Effort estimate:** 6 tasks, one Code session of about 1 to 2 days.

## 2. Architecture

- **Components:** `src/api.js` (client: `createApi(transportName)`, `mock` only), `src/web/` (plain HTML, CSS, JS: `index.html` list, `trip.html` form, `app.css`, `app.js` shared helpers), `src/services/trips.js` (+ `listTrips`, `updateTrip`).
- **Data flow:** screen -> `api.js` -> service -> repository -> mock transport. Screens never touch the repository. `api.js` returns `{ok, data}` or `{ok:false, error}` so a REST transport can replace `mock` without screen changes.
- **Schema changes:** none. Seed data stays dummy (`tests/fixtures/seed.json`); the role switcher lists seed users.
- **Integration points:** none live. The `google.script.run` and REST transports are later steps behind the same `api.js` interface.
- **Migration path:** greenfield UI; rollback is removing `src/web/` and `src/api.js`.
- **Design tokens (proposed; recorded in `CLAUDE.md` once approved):**
  - Colors: text `#1f2933`, background `#f7f8fa`, surface `#ffffff`, accent `#1f6feb`, danger `#b42318`, success `#157347`, border `#d0d5dd`.
  - Fonts: system UI stack for body, system monospace for IDs and readings; scale 14/16/20/28 px.
  - Spacing: 4, 8, 16, 24 px. Corner radius: 6 px. Touch targets at least 44 px.
- **Key decisions:**
  - Plain HTML and CSS, no framework or dependency, as the stack says.
  - Services stay the only place for rules; the UI hides actions but never decides.
  - `api.js` wraps errors into one shape so screens show one message style.
  - Mock state is in memory per page load, so flows are repeatable in tests.

## 3. Task breakdown

| # | Task | Agent | Files | Pass/fail check |
|---|---|---|---|---|
| 1 | Service additions: `listTrips` (by role: own, or all for supervisor/accounting/admin), `updateTrip` (Draft only, owner) | Code | `trip-monitoring/src/services/trips.js`, `trip-monitoring/tests/trips-service.test.js` | new tests pass; the 22 existing tests still pass |
| 2 | `api.js` with `mock` transport, role switcher user, error shape | Code | `trip-monitoring/src/api.js`, `trip-monitoring/tests/api.test.js` | api tests: each action succeeds for its role and is refused for others |
| 3 | Shared CSS tokens and layout, role switcher component | Code | `trip-monitoring/src/web/app.css`, `trip-monitoring/src/web/app.js` | page loads at 3 widths, no console errors |
| 4 | Trip list screen with status filter, loading, empty and error states | Code | `trip-monitoring/src/web/index.html` | Playwright: list shows role-visible trips |
| 5 | Trip form: create, edit while Draft, submit, validate, return, with readings and travellers | Code | `trip-monitoring/src/web/trip.html` | Playwright: full flow Draft to Completed and a return to Draft |
| 6 | Screenshots, `CLAUDE.md` tokens, `STATUS.md` | Code | `trip-monitoring/docs/screens/m1-screens/`, `trip-monitoring/docs/STATUS.md`, `CLAUDE.md` | 6 PNGs saved; `npm test` exits 0 |

Model plan: build sonnet; review sonnet (normal risk, moderate diff); fix sonnet, opus on a second attempt.

## 4. Test plan

- **Tested:** service additions, `api.js` per role, list and form flows in a browser on the mock, three widths, console errors, empty and error states.
- **Tooling:** `node:test` for services and `api.js` (`node --test 'tests/*.test.js'`); Playwright (preinstalled, not a project dependency) for screens, loading `src/web/` via `file://`.
- **"Tests pass" means:** the test command exits 0 with no failures or skips, the browser flow runs with no console errors, and screenshots exist at 1280, 768 and 375 px for each screen.
- **Cannot run in a cloud session:** real Google Sheets, Apps Script, Google sign-in.

## 5. Merge plan

- **Branch:** `claude/m1-screens-build`.
- **Merge method:** merge commit.
- **Conditions:** the owner's APPROVED on this plan, an approved Lead verdict on the exact head, green checks if CI exists.
- **Release policy:** no deploy.

Risk: normal
CI required: no
Files in scope: trip-monitoring/, CLAUDE.md

## 6. Readiness

| Item | Status | Evidence / note |
|---|---|---|
| Repository access, default branch main | READY | public, merge commits allowed |
| Loop labels, skill, issue form | READY | all present |
| M1 repository and services (PR #26) | READY | merged, 22 tests |
| Node and Playwright | UNVERIFIED | Code runs `node --version` at the start; Playwright is preinstalled in cloud sessions |
| Branch protection on main | UNVERIFIED | token cannot read it; merge script reports a refusal |
| CI workflow for tests | NOT REQUIRED | `CI required: no` |
| Design tokens | NEEDS SETUP | proposed in section 2; owner approves by replying APPROVED |
| Google Sheet, Apps Script, clasp, sign-in | NOT REQUIRED | mock transport only |
| Hosting, external APIs, costs | NOT REQUIRED | none; repo is public, dummy data only |

**Owner checklist (by hand):**
- [ ] Check the proposed design tokens (section 2); reply `REVISE:` to change them.
- [ ] Later: real Sheet, Apps Script project and deploy (not in this slice).

APPROVED by lheiiyy on 2026-10-30

## Status

Built on branch `claude/m1-screens` (PR #28), ready for review. Tasks 1 to 6 done. `npm test`: 38 tests, 38 pass, 0 fail, 0 skipped (22 existing, 4 service, 9 api, 3 browser flows). Screenshots: `trip-monitoring/docs/screens/m1-screens/` (list, list-empty, form-draft, form-submitted, form-completed at 1280, 768, 375).
