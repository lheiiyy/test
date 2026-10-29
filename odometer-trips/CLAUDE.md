# Odometer Trip Log: rules for Claude Code

A single-user web app that records trips as start and end odometer readings, plus fuel, service and a monthly report. Full plan: `odometer-trips/specs/plan.md`. The owner approved the plan on 2026-10-29 and does not want to be asked again before work starts.

## Stack and layout

- Plain HTML, CSS and JavaScript. No build step and no new dependencies unless the plan says so. React is out of scope for now.
- Work only inside `odometer-trips/`. Leave `android/`, `desktop/`, `shared/`, `docs/`, `.github/` and the root config files alone.
- Four layers: screens, then `api.js`, then services (rules), then repository (storage). Only the repository reads or writes storage.
- `api.js` has a `transport` setting: `mock` (fixtures in `tests/fixtures/`), `local` (browser storage, version 1), later `appsscript` and `rest`.
- Data rules: prefixed IDs (VEH, TRP, FUE, SVR, SVC, LKP, AUD), dates `yyyy-mm-dd`, odometer in whole kilometres, soft delete only, audit columns on every table, every change written to `audit_log`. Distance, km per litre and km to next service are calculated, never stored.
- The app must be usable on a tablet. Check 1280, 768 and 375 pixel widths.

## Loop rules

Follow `.claude/skills/github-loop/SKILL.md`. The repository owner is `lheiiyy`. Never push to `main`; use `claude/` branches and open a pull request. Stop and use `needs-leo` only for: deleting files, changing the data model, touching anything outside `odometer-trips/`, or editing `.github/`. Everything else, decide and continue.

## Build pipeline

| Stage | Use | Fallback if not installed | Gate |
|---|---|---|---|
| Start | Check the repo is `lheiiyy/test` and the work is inside `odometer-trips/` | Same | Stop on a mismatch, before any change |
| Plan the build | `superpowers:writing-plans`, with `specs/plan.md` as the spec | A task list with exact file paths and one test per task | The owner pre-approved the plan; proceed |
| Isolate | `superpowers:using-git-worktrees` on a `claude/` branch | A plain `claude/` branch | Never work on `main` |
| Build | `superpowers:test-driven-development` for services and repository; `superpowers:executing-plans` for the tasks | Write the failing test first, then the code | Patch surgically; keep the layers |
| UI | `frontend-design` for screens with no approved design | Plain HTML and CSS | Screens work at three widths |
| Prove | Playwright against localhost with the `mock` or `local` transport | Claude in Chrome or the built-in browser, manual walkthrough | The Playwright rules below pass |
| Verify | `superpowers:verification-before-completion` | Run the test command and read the output | No "done" without fresh passing output |
| Review | `superpowers:requesting-code-review` | Re-read the diff as a reviewer | Fix critical and major findings |
| Ship | `superpowers:finishing-a-development-branch`, then a PR to `main` | A plain PR | The owner merges |

Playwright rules:
- Run on localhost with the `mock` transport; no sign-in is needed.
- Check widths 1280, 768 and 375 pixels: the main flow completes, with no console errors and no failed network calls.
- Save each explored flow as a test in `odometer-trips/tests/e2e/` so it reruns without Claude.

Keep runs short: read only the files the issue names, and keep issue replies to the 150-word format.
