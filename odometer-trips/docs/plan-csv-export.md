# Plan: Odometer Trip Log, slice 2 (CSV export)

Request: issue #14. Spec: `odometer-trips/specs/plan.md` (approved 2026-10-29). Project rules: `odometer-trips/CLAUDE.md`. Earlier slice: `odometer-trips/docs/plan-trip-log-core.md` (merged, PR #10). Status document: this file's `## Status` section (Code adds it) and `odometer-trips/README.md`.

## 1. Business plan

- **Problem:** all data lives in browser storage, which can be cleared, and slice 1 has no way to copy it out or check it in a spreadsheet.
- **Users:** Leo, one user on one tablet (also desktop and phone).
- **Value:** a copy of every table that Leo can download, keep and open in a spreadsheet. It finishes the CSV part of Phase 1 in `specs/plan.md`.
- **Scope:** one Export button per table (vehicles, trips, lookups, audit_log). Each downloads one CSV file with a header row and one row per stored row, voided rows included. The page shows how many rows each table has.
- **Out of scope:** importing a CSV back (Phase 3), fuel, service, monthly report, open trips, editing a trip, Sheets sync, a zip of all files, a distance column (distance is calculated, never stored), deploy.
- **Success metrics:** (1) four CSV files download from the page; (2) each file has the table's column names in a fixed order as the header; (3) values with commas, quotes or line breaks are quoted and read back identical in a unit test; (4) an export leaves `row_version` and `audit_log` unchanged; (5) the flow completes at 1280, 768 and 375 px with no console errors. Opening a file on Leo's tablet is his hand check.
- **Risks:** (1) the app cannot restore from a CSV in this slice, so the export is a copy and a check, not a restore; import comes with Phase 3; (2) how the tablet's browser handles downloads cannot be tested in a cloud session; (3) text that starts with `=`, `+`, `-` or `@` can run as a formula when a CSV is opened in a spreadsheet, so the export prefixes it with an apostrophe, and the Phase 3 import must remove that apostrophe; (4) an exported file holds whatever data is on the device, so tests use dummy data only because the repository is public; (5) Playwright and subagents in scheduled runs are UNVERIFIED (see Readiness).
- **Effort estimate:** six tasks, about 2 hourly Code cycles, plus one review round.

## 2. Architecture

- **Components:** new `app/csv.js` (a pure function that turns columns and rows into CSV text, no storage); `app/services.js` (which tables and columns to export); `app/api.js` (API client); `app/index.html`, `app/main.js` and `app/styles.css` (the Export section and the file download). `app/repository.js` is not changed. Only the repository touches storage.
- **Data flow:** an Export button calls `api.js`, which calls the service, which reads rows through the repository (voided rows included) and passes them to `csv.js`. `main.js` turns the returned text into a file download, the only browser-specific step.
- **Schema changes:** none. No table, column or ID changes, so there is no migration. Rollback is reverting the pull request.
- **Integration points:** none. No external service, secret or network call.
- **Migration path:** the export reads through the repository's existing `list` function, so the Phase 3 Apps Script repository supports it unchanged.
- **Key decisions:**
  - One button per table, not a zip or several downloads at once, because browsers often block multiple automatic downloads and a zip needs a new dependency.
  - Columns are listed explicitly per table in the service, so the header order is stable and a new column is a deliberate change.
  - All stored rows are exported, including voided ones (`is_active` false), so the file is a full copy. Derived values such as distance are not exported because they are never stored.
  - UTF-8 with a byte order mark, CRLF line ends and RFC 4180 quoting, so Excel and Sheets read the file correctly.
  - An export is read-only: it writes no audit row and does not change `row_version`, because it changes no data.
  - File name `odometer-<table>-<yyyy-mm-dd>.csv`, with the date from the injected clock so tests are stable.
  - No new dependency; tests use Node's built-in `node:test`, as `CLAUDE.md` requires.

## 3. Task breakdown

| # | Task | Agent | Files | Pass/fail check |
|---|---|---|---|---|
| 1 | CSV text builder: header, RFC 4180 quoting, CRLF, byte order mark, apostrophe guard, empty values | Code | `app/csv.js`, `tests/unit/csv.test.mjs` | A test-only parser reads back the original values for commas, quotes, line breaks, empty and non-ASCII text; a value starting with `=` is prefixed |
| 2 | Services: list the four exportable tables with row counts; build one table's CSV and file name | Code | `app/services.js`, `tests/unit/services.test.mjs` | Voided rows are included; the header order is fixed; `row_version` and `audit_log` are unchanged after an export; an unknown table is rejected |
| 3 | API client: `listExportTables` and `exportCsv` on both transports | Code | `app/api.js`, `tests/unit/api.test.mjs` | `local` and `mock` return the same shapes; an unknown table returns the error shape |
| 4 | Screens: Export section with four buttons, row counts, an empty-table note, and the file download | Code | `app/index.html`, `app/main.js`, `app/styles.css` | Page loads over localhost with no console errors; a click downloads a file |
| 5 | Browser check at 1280, 768 and 375 px, added to the existing rerunnable test | Code | `tests/e2e/trip-flow.cjs` | Save a trip with a comma and a quote in the destination (dummy data), download the trips CSV, and see the header, one row and the quoting at all three widths, with no console errors or failed requests |
| 6 | Docs: run instructions, status and test results in this plan file | Code | `docs/plan-csv-export.md` | The Status section names the run commands and the results |

Model plan: build sonnet for tasks 1 to 5 and haiku for task 6 (documentation only); review opus (11 files, a big diff); fix sonnet, opus on a second attempt.

## 4. Test plan

- **Unit tests:** `node --test 'odometer-trips/tests/unit/*.test.mjs' odometer-trips/tests/readme.test.mjs` covers the CSV builder, the services and the API client with dummy data (a vehicle named "Test Bike", plate "TEST-001"). The 30 existing tests must still pass.
- **Browser check:** `node odometer-trips/tests/e2e/trip-flow.cjs` serves the folder with a small Node server, opens the page with Playwright and the `mock` transport, runs the existing trip flow, then downloads the trips CSV and checks it, at 1280, 768 and 375 px.
- **Tests pass** means every unit test passes, the browser check exits 0, there are no console errors and no failed network calls.
- **Cannot run in a cloud session:** how Leo's tablet browser saves and opens the downloaded file. If Playwright is missing from the run, the browser check is reported as not run, and the Lead says so in the verdict.

## 5. Merge plan

- **Branch:** `claude/csv-export`, the branch of this plan PR.
- **Merge method:** merge commit.
- **Merge conditions:** Leo approved this plan; the Lead's verdict approves the exact head; the PR is clean and mergeable; only files in scope changed. No data-model change, so no migration check applies.
- **Release policy:** no deploy.

Risk: normal
CI required: no
Files in scope: odometer-trips/app/, odometer-trips/tests/, odometer-trips/docs/plan-csv-export.md

## 6. Readiness

| Item | Status | Note |
|---|---|---|
| Repository access, public repository, labels, skill on `main`, issue form, merge commits | READY | Readiness check on 2026-10-30: `lheiiyy/test`, default branch `main`, all labels present, merge commits allowed |
| Open PR #1 (android-parental-monitor) | READY | It touches no file under `odometer-trips/` |
| Baseline tests | READY | 30 of 30 pass on Node 22.23.4 on 2026-10-30 |
| Playwright in this chat session | READY | The module loads |
| Playwright in the scheduled Code run | UNVERIFIED | Not confirmed for scheduled runs |
| Subagent for the opus review in a scheduled run | UNVERIFIED | Without one, the review runs on the task's model and says so |
| CI workflows | NEEDS SETUP | Optional. Adding one means editing `.github/`, which needs Leo's word |
| Branch protection on main | UNVERIFIED | The session token cannot read it (403); the merge script reports a refusal |
| GitHub Pages | UNVERIFIED | The session proxy blocks the Pages API; needed only to open the app on a tablet |
| Connectors, secrets, database, external APIs, formal GitHub approval | NOT REQUIRED | None used; all agents share one account |

**What Leo does by hand:**
1. Reply `APPROVED` on issue #14 to build and merge.
2. After the merge, on the tablet: open the app (Settings → Pages → deploy from branch `main`, folder root, then `/odometer-trips/app/`), tap each Export button, and check that the file downloads and opens. Use test data only until you have checked this.
3. Do not turn on "required approvals" on `main`.

AWAITING APPROVAL
