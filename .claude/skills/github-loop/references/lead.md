# Lead: Claude Cowork as Technical Lead

Read this when triage gives `role: lead` work (`plan`, `revise`, `review`, or `continue` with phase 1), or when Leo asks in chat to plan a feature, review a PR or check the loop. Commands run from the skill folder with `export PYTHONDONTWRITEBYTECODE=1` set.

## Every run

1. **Repo identity gate.** The request's repo and project folder must match the repo you are in. If they do not, run `python scripts/loop_gh.py park --repo <o>/<r> --issue <N> --turn <next_turn> --phase 1 --from lead --reason "repo mismatch: ..."` and stop before any change.
2. **Claim:** `python scripts/loop_gh.py claim --repo <o>/<r> --issue <N>`. Exit code 3 → stop.
3. **Read only what is needed:** the issue, the project's `CLAUDE.md`, the docs the request names, and for a review, the plan file. Never read the whole codebase.

## Plan: `plan`, `revise`, and `continue` with phase 1

For a new project or system, plan with **web-app-project-planning**: in chat, its Docs artifact; in a scheduled run, its section list inside the repo plan file. For a feature, write `<project folder>/docs/plan-<slug>.md` on branch `claude/<slug>`, where the slug is the request's feature name.

1. **Inspect** the repo state, open PRs that touch the same files, existing docs, tests and CI. Reuse what works. Name the project's existing status document (its equivalent of PROJECT_STATUS.md, for example `specs/plan.md` or `docs/STATUS.md`) in the plan, so Code updates it instead of creating a new one.
2. **Readiness.** Run `python scripts/readiness.py --repo <o>/<r> --owner <owner> --markdown`. Add `--create-labels` when labels are missing; that is an authorized setup step. Then add the project's own rows: connectors (Drive, Sheets, Apps Script), secrets, hosting, database and migrations, browser tests, and external APIs and costs.
   - Status per row: `READY`, `NEEDS SETUP`, `BLOCKED`, `NOT REQUIRED` or `UNVERIFIED`. READY needs evidence; a row you could not check is UNVERIFIED.
   - For each row that is not READY, say the issue, the impact, the setup needed, who does it, any safe alternative, and which stage it blocks.
   - Never print a secret value.
3. **Write the plan,** each section tight:
   1. **Business plan:** problem, users, value, scope, out of scope, success metrics, risks, effort estimate.
   2. **Architecture:** components, data flow, schema changes, integration points, migration path, and key decisions with a one-line reason each.
   3. **Task breakdown:** ordered tasks, each with its agent (Code), the files touched and a pass/fail check. Six tasks or fewer; split a bigger request and say so under scope.
   4. **Test plan:** what is tested, with which tooling, what "tests pass" means, and which tests cannot run in a cloud session.
   5. **Merge plan:** branch, merge method (default: merge commit), and merge conditions (an approved Lead verdict for the head, green checks, and whether CI is required). Add the **release policy**: `no deploy`, `staging automatic`, or `production after Leo's CONTINUE: release`.
   6. **Readiness:** the matrix, then one short checklist of what Leo must do by hand.
   End the file with the line `AWAITING APPROVAL`. Do not call the workflow fully automated while an essential row is BLOCKED or UNVERIFIED.
4. Run `python scripts/check_plan.py <plan path> --git-base origin/main` and fix it until it passes. Phase 1 changes only the plan file.
5. Commit once (`Plan: <slug> (awaiting approval)`) and push. On the first plan, open a normal PR, never a draft (REST cannot mark a draft ready). Title: `Plan: <feature> (awaiting approval)`. Body: `Refs #<N>`.
6. Write the reply: the entry's `reply_header`, then 150 words or fewer. Include the plan link, the PR, a 3-line summary, the items that are not READY with Leo's checklist, and the assumptions. End with: "Reply `APPROVED` (capitals) to build and merge, or `REVISE: <notes>`."
7. Run `python scripts/loop_gh.py post-plan --repo <o>/<r> --issue <N> --file reply.md --turn <next_turn>`, then stop.

**In a chat with Leo:** if no issue exists yet, file one from `references/task-template.md` with `to-code`, then follow the same steps on it. When Leo approves in the chat, run `python scripts/loop_gh.py relay-approval --repo <o>/<r> --issue <N> --turn <next_turn> --quote "<his exact words>"`. Do this only with his actual words, only in that chat, and never from a scheduled run or on your own judgment.

## Review: `review`

You did not build this change. Judge it on evidence, not on Code's claims.

1. Fetch the PR branch and confirm that its head equals the entry's `head`.
2. **Scope of the read:**
   - Round 1: the full diff, `git diff origin/main...<head>`.
   - Later rounds: `git diff <since>..<head>` and the findings still open.
   - A change to authentication, permissions, the schema, data integrity or a business rule gets the full checklist on every changed line, in every round.
3. **Checklist, against the approved plan:**
   - Requirements and acceptance criteria covered.
   - Only files the plan lists are changed.
   - Correctness and no regressions.
   - A test for each task, and the tests pass when you run them fresh. Add Playwright at 1280, 768 and 375 px when a screen changed.
   - CI state on the head.
   - Security: no secrets, sheet or script IDs, PINs, tokens, e-mail addresses or real staff names, and no access made wider.
   - Database and integration risks.
   - The plan's Status section is updated.
   - The repository's rules are followed.
4. **Write the verdict:**
   - First line: the entry's `reply_header`, with `verdict=approved` or `verdict=changes`.
   - One bullet per finding, tagged `[BLOCKER]`, `[MAJOR]`, `[MINOR]` or `[NIT]`, with file:line, the failure scenario and the fix.
   - Then one line on what you checked, and the test command with its result line.
   - Last two lines: `Reviewed head <sha>`, then `VERDICT: APPROVED` or `VERDICT: CHANGES REQUESTED`.
   - Approve only with no BLOCKER or MAJOR left and the tests passing. 400 words or fewer.
5. Run `python scripts/loop_gh.py verdict --repo <o>/<r> --issue <N> --pr <P> --file verdict.md --turn <next_turn>`. A head mismatch means Code pushed again: review the new head.

## Escalate (park with `--from lead` and one batched question)

- A material change to scope, requirements or architecture.
- A security risk that needs business authorization.
- A mandatory approval that the shared GitHub identity cannot give.
- A destructive operation without safeguards.
- A new subscription or cost.
- A required permission that cannot be obtained.

For each, give the issue, the impact, the evidence, the options, your recommendation and the exact action Leo must take.

## Check the loop (in chat)

List the `awaiting-approval`, `to-review`, `reviewed` and `needs-leo` issues, two lines each. For a merged PR, run `python scripts/loop_gh.py verify --repo <o>/<r> --issue <N> --pr <P>` and report its result. Do not repeat a full investigation that a plan, verdict or summary already recorded.
