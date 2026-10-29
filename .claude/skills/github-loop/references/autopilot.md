# Autopilot mode: plan, one approval, then build, test, debug and merge

Read this when a triage `work` entry has a `work_type`. The issue is Leo's request in the template format (`references/task-template.md`, or the Autopilot issue form): it has Phase 1 and Phase 2 headings. Leo's only action after filing it is one comment: `APPROVED`.

Commands below run from the skill folder with `export PYTHONDONTWRITEBYTECODE=1` set. `<o>/<r>` is the repo, `<N>` the issue, `<P>` the PR.

## Every run

1. **Repo identity gate.** The request's repo must be the repo you are running in, and the project folder must exist (or be new because the request says so). On a mismatch: `python scripts/loop_gh.py park --repo <o>/<r> --issue <N> --turn <next_turn> --phase 1 --reason "repo mismatch: ..."`, then stop before any change.
2. **Claim:** `python scripts/loop_gh.py claim --repo <o>/<r> --issue <N>`. Exit code 3 → stop.
3. **Read only what is needed:** the issue, the project's `CLAUDE.md`, and the docs the request names. Do not re-read the whole codebase.
4. **Names:** the feature slug comes from the request's feature name (lowercase, hyphens), for example `readme`. Plan path: `<project folder>/docs/plan-<slug>.md`. Branch: `claude/<slug>`.

## Phase 1: `plan`, `revise`, and `continue` with phase 1

1. Create `claude/<slug>` from `main`, or check out the existing branch for a revision.
2. Write the plan file, keeping every section tight:
   1. Business plan: problem, users, value, scope, out of scope, success metrics, risks, effort estimate.
   2. Architecture: components, data flow, schema changes, integration points, migration path, key decisions, each with a one-line reason.
   3. Task breakdown: ordered tasks, each with the files touched and a pass/fail check. Keep it to 6 tasks or fewer. If the request is bigger, split it and say so under scope.
   4. Test plan: what is tested, with which tooling, and what "tests pass" means.
   5. Merge plan: branch name, merge method (default: merge commit), and the merge conditions.
   End with the line `AWAITING APPROVAL`. For `revise`, apply the entry's `notes`. For `continue`, use the answer in `notes`.
3. `python scripts/check_plan.py <plan path> --git-base origin/main`. Fix it until it passes. Phase 1 changes only the plan file.
4. Commit once (`Plan: <slug> (awaiting approval)`) and push.
5. On the first plan, open a normal PR with REST, never a draft: drafts cannot be marked ready without GraphQL. Title: `Plan: <feature> (awaiting approval)`. Body: `Refs #<N>` and the plan path.
6. Write `reply.md` with the entry's `reply_header` line, then at most 150 words: the plan link, the PR link, a 3-line summary, and the assumptions to confirm. End with: "Reply `APPROVED` (capitals) to build and merge, or `REVISE: <notes>`."
7. `python scripts/loop_gh.py post-plan --repo <o>/<r> --issue <N> --file reply.md --turn <next_turn>`. Stop here. Never start Phase 2 in the same run.

## Phase 2: `build`, and `continue` with phase 2

The approved plan authorizes everything in it, including the merge, and nothing beyond it.

1. Check out `claude/<slug>`. If `main` moved, merge `origin/main` into the branch (a merge commit; never rebase or force-push).
2. Re-read the plan file: it is the spec. Apply any `notes` from a `CONTINUE:`.
3. Implement the tasks in order, one commit per task (`T<n>: <task>`), and push after each commit.
4. Set up the test harness from the test plan, write the tests, run them, and keep the output.
5. Debug: find the root cause before fixing, fix the cause and not the symptom, then re-run. If the same error survives 2 fix attempts, park.
6. Update the docs before merging. In the plan file, replace the last line with `APPROVED by <owner> on <date>` and add a `## Status` section with the status, decisions and test results. Update any project docs the plan names. Commit `Docs: status and test results`.
7. Retitle the PR to `<feature>` and add the test output to its body: `gh api -X PATCH repos/<o>/<r>/pulls/<P> -f title=... -F body=@pr.md`.
8. Merge only through the script: `python scripts/loop_gh.py merge --repo <o>/<r> --issue <N> --pr <P> --owner <owner> --method <plan's method>`. It re-checks the owner's `APPROVED` and the PR's state, and pins the head SHA.
   - Exit code 4 or 5: park with its reason (`--phase 2`).
   - If a permission rule refuses the command itself: `park --phase 2 --reason "Merge needs one tap from you: <PR link>. Tap Merge, then reply CONTINUE: merged"`. Do not work around it. On the next `continue`, if the PR is already merged, go straight to step 9.
9. Write `summary.md` with the entry's `reply_header` (type=summary phase=2), then at most 250 words: every changed file (`git diff --name-only <base>..<merge commit>`), the test command with its result line, and the PR and merge-commit links.
10. `python scripts/loop_gh.py finish --repo <o>/<r> --issue <N> --file summary.md --turn <next_turn>`. This labels the issue `done` and closes it.

## Stop and ask (park with `--phase` and one batched question)

- Anything must change outside the approved plan (scope, schema, architecture).
- A fix needs a new dependency or an external service.
- The same error survives 2 fix attempts.
- A merge conflict touches files outside the plan.
- The repo identity gate fails.

Also: never commit secrets (API keys, clasp credentials, tokens), never force-push or rewrite history, and never delete files or data outside the plan.

## What Leo types (say this in every plan reply and park)

| Comment, at the very start and in capitals | Effect |
|---|---|
| `APPROVED` | Build, test, debug and merge the latest plan |
| `REVISE: <notes>` | Rewrite the plan (up to 3 times) |
| `CONTINUE: <answer>` | Answer a parked question and resume the parked phase |

Only the repo owner's comments count. Leo never has to touch a label.
