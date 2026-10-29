# Plan: odometer-trips README

Issue #3. First live test of github-loop autopilot.

## 1. Business plan

- **Problem:** `odometer-trips/` has no README, so a visitor cannot tell what the folder is.
- **Users:** Leo, reading on desktop, tablet and phone (GitHub renders Markdown at every width).
- **Value:** the project is identifiable at a glance; proves the autopilot plan → approve → build → merge path end to end.
- **Scope:** one file, `odometer-trips/README.md`: a title line and one sentence saying what the app does.
- **Out of scope:** setup steps, screenshots, badges, any app code, anything outside `odometer-trips/`.
- **Success metrics:** README merged to `main`; its test passes; issue #3 closed by the executor.
- **Risks:** wording drifts from `specs/plan.md` (mitigation: sentence taken from its project description); loop mechanics fail (mitigation: scripts park on `needs-leo`).
- **Effort estimate:** one short run, under 15 minutes.

## 2. Architecture

- **Components:** `README.md` (content) and `tests/readme.test.mjs` (check). No app components change.
- **Data flow:** none; static Markdown rendered by GitHub.
- **Schema changes:** none.
- **Integration points:** GitHub's Markdown renderer only.
- **Migration path:** none; new file, nothing to migrate.
- **Key decisions:**
  - Title `# Odometer Trip Log` — matches the project name in the issue and `specs/plan.md`.
  - Test with Node's built-in `node:test` — no new dependencies, no build step (project rule).

## 3. Task breakdown

1. **T1: Write the README.** Files: `odometer-trips/README.md`. Content: `# Odometer Trip Log`, a blank line, then one sentence: "A single-user web app that records each trip as start and end odometer readings and reports distance, fuel use and service timing." Check: file exists; pass/fail by T2's test.
2. **T2: Add the README test.** Files: `odometer-trips/tests/readme.test.mjs`. Check: test passes against T1 and fails if the title or sentence is missing.
3. **T3: Update docs.** Files: `odometer-trips/docs/plan-readme.md` (approval line, `## Status` with decisions and test results). Check: `## Status` present; diff limited to `odometer-trips/`.

## 4. Test plan

- **Tool:** `node --test odometer-trips/tests/readme.test.mjs` (Node built-in runner, no install).
- **What is tested:** README exists; first line is exactly `# Odometer Trip Log`; there is exactly one non-empty line after the title, and it is a single sentence ending with a full stop that mentions "odometer".
- **Tests pass means:** the runner reports `fail 0` and exit code 0. Also `git diff --name-only origin/main` lists only files under `odometer-trips/`.

## 5. Merge plan

- **Branch:** `claude/readme`.
- **Method:** merge commit.
- **Conditions:** Leo's `APPROVED` comment follows this plan; tests pass with output in the PR body; PR is open, not a draft, and mergeable; only `odometer-trips/` files changed. Merge via `scripts/loop_gh.py merge` only.

AWAITING APPROVAL
