# Plan: smoke-readme (one README line)

Issue: #36. Repo: `lheiiyy/test`. Smoke test of the refreshed github-loop skill (PR #35). Docs only.

## 1. Business plan
- **Problem:** after the skill refresh we need proof that the loop (plan, approve, build, review, merge-stop) works end to end.
- **Users:** Leo (owner), reading the README on desktop, tablet and phone.
- **Value:** a visible, harmless change that exercises every loop step.
- **Scope:** `README.md` only. Add a `Loop status` heading with the line `github-loop skill refreshed on 2026-11-06 (smoke test).`
- **Out of scope:** application code, `trip-monitoring/`, `.github/`, the skill itself, any deploy.
- **Success metrics:** README shows the heading and exact line; one file changed; Lead verdict on the exact head; the merge stops for Leo's tap.
- **Risks:** `README.md` does not exist on main, so Code creates it (a new file, not a delete). Low. `Risk: high` is declared on purpose by the request.
- **Effort:** under 10 minutes, 1 task.

## 2. Architecture
- No components, data flow, schema or integrations. A Markdown file only.
- Migration path: none. No data or schema moves; rollback is reverting the one file.
- Decision: keep the README to a title plus the one section. Reason: it is a smoke test and the diff stays one screen.
- Decision: create `README.md` at the repo root. Reason: the issue names no project folder.

## 3. Task breakdown
1. Code: create or edit `README.md` with a `## Loop status` heading and the exact line above. Files: `README.md`. Check: `grep -n "github-loop skill refreshed on 2026-11-06 (smoke test)." README.md` finds 1 line, and `git diff --stat origin/main` lists only `README.md` and this plan.

Model plan: build haiku (documentation only); review sonnet (score 0, sonnet is the review floor); fix haiku, opus on a second attempt

## 4. Test plan
- No code, so no test suite. `trip-monitoring/` is not touched, so `npm test` is not required.
- "Tests pass" = the grep check in task 1 passes and the diff lists only the in-scope files.
- Nothing needs a cloud-only tool. No screen changes, so no screenshots.

## 5. Merge plan
- Branch: `claude/smoke-readme`. Merge method: merge commit.
- Conditions: owner's `APPROVED` on this plan, a Lead verdict `APPROVED` on the exact head, no failing checks.
- Risk: high
- CI required: no
- Files in scope: README.md, docs/plan-smoke-readme.md
- Release policy: no deploy
- Because Risk is high, the merge stops (exit 8) and Leo taps Merge himself.

## 6. Readiness
| Item | Status | Note |
|---|---|---|
| Repository access, labels, skill on main, issue form | READY | checked by readiness.py |
| Merge method (merge commit) | READY | allowed |
| CI workflows | NOT REQUIRED | docs only |
| Branch protection on main | UNVERIFIED | token cannot read it; the merge script will report |
| Hosting / Pages, Drive, Sheets, secrets, database, external APIs | NOT REQUIRED | no deploy |

Owner checklist:
- [ ] Reply `APPROVED` on #36.
- [ ] Tap Merge on the PR at the end, then reply `CONTINUE: merged`.

APPROVED by Leo on 2026-11-07

## Status
- Built: README.md created with `## Loop status` and the exact line (T1).
- Decision: new README at repo root; title `# test`.
- Test: grep check found 1 line; diff lists only README.md and this plan.
