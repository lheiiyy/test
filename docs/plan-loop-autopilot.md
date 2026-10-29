# Plan: github-loop autopilot

Repo `lheiiyy/test` · written 2026-10-29 · Phase 1 only: no code changed.

**Objective:** make the github-loop skill take one GitHub issue from business plan to merged, tested code, where Leo's only action after the request is one `APPROVED` comment.

## 1. Business plan

**Problem.** Each feature needs about five manual steps from Leo today, all on a tablet: paste the issue, add the `to-code` label, open chat to "check the loop", write follow-ups, and merge the PR.

**Users.** Leo, the owner, using the GitHub app or a browser on a tablet or phone. The Claude Code executor, run by an hourly scheduled task.

**Value.** Leo writes one request and types one word. Planning, building, testing, debugging, merging and docs then run unattended.

**In scope**
- Autopilot mode in github-loop: Phase 1 plan, then an approval gate, then Phase 2 build, test, debug, merge and docs.
- Owner keyword comments: `APPROVED`, `REVISE: <notes>`, `CONTINUE: <answer>`.
- Scripted safety checks: a plan checker, and a merge that runs only after a verified owner `APPROVED`.
- A GitHub issue form that files the request with `to-code` already applied.
- The hourly scheduled task, and one live end-to-end test.

**Out of scope:** GitHub App or event triggers, waking Claude chat, the GitHub Actions or API-key route, more than one issue per run, other repos (until the live test passes), and odometer app changes beyond the live-test README.

**Success metrics**

| Metric | Target | Measured by |
|---|---|---|
| Human actions after the request | 1 of 9 steps (`APPROVED`), about 90% automated | Live test issue timeline |
| Merges without a verified owner `APPROVED` | 0 | Unit tests; the merge script refuses |
| Idle hourly run | 1 triage call, 1 line of output | Scheduled run log |
| Small feature, `APPROVED` to merged | 2 hourly runs or fewer | Live test timestamps |
| A stuck run is surfaced | Within 3 h for builds, 90 min otherwise | Stale-claim tests |

The 9 steps are: trigger, plan, plan check, plan PR and comment, `APPROVED` (Leo), build, test and debug, verified merge, then docs, summary and close.

**Risks**

| Risk | Mitigation |
|---|---|
| Claude's permission rules block the merge. This already happened once in this session ("merge without review"). | The merge script cites the owner's `APPROVED` comment. If the merge is still denied, the executor labels `ready-to-merge` and Leo taps Merge once, which drops automation to about 80%. |
| Creating the scheduled task from chat was denied once | Leo approves creation in chat, or creates the task once in claude.ai using the prompt in setup.md. |
| The repo is public, so anyone can comment `APPROVED` | Only comments from the owner login with `author_association` OWNER count. This is tested. |
| Large builds use up the Pro token budget | Each feature is capped at about 6 tasks. The plan splits bigger requests. |
| The actor recorded for the issue-form label is unknown | Tested live in task 6. The guard falls back to checking that the issue author is the owner. |
| Hourly latency | Accepted. When Leo is watching, chat can start the task early. |

**Effort estimate.** Phase 2 is about 8 tasks in one working session (a few hours of agent time). The live test then runs over the next 2-3 hourly runs.

## 2. Architecture

| Component | File (under `.claude/skills/github-loop/` unless noted) | Change |
|---|---|---|
| Issue form | `.github/ISSUE_TEMPLATE/autopilot.yml` (repo root) | New. Has the fields of Leo's template and applies `to-code`. |
| Guard | `scripts/loop_guard.py` | Phase state machine, owner keywords, caps |
| Triage | `scripts/triage.py` | Returns work typed `plan`, `revise`, `build` or `continue` |
| Writes | `scripts/loop_gh.py` | New subcommands: `post-plan`, `merge` (verified), `finish` |
| Reply check | `scripts/check_reply.py` | New types `plan` and `summary`; summaries may run to 250 words |
| Plan check | `scripts/check_plan.py` | New. Checks the 5 sections, the final `AWAITING APPROVAL` line, and that the Phase 1 diff is only the plan file |
| Procedure | `references/autopilot.md` | New. Phase 1 and 2 executor steps, identity gate, stop rules |
| Request template | `references/task-template.md` | New. Leo's template with placeholders |
| Entry | `SKILL.md`, `references/setup.md` | Route to autopilot mode, add setup steps |
| Tests | `evals/test_scripts.py` | Extended. Kept out of the packaged skill. |

**Data flow**

```
issue form --to-code--> PLAN run --> plan file + draft PR + comment --> label awaiting-approval
awaiting-approval + owner "REVISE: ..." --> REVISE run (max 3) --> awaiting-approval
awaiting-approval + owner "APPROVED" --> BUILD run --> one commit per task --> tests
    --> debug (2 tries per error) --> verified merge --> docs --> summary --> done, close
any stop rule --> needs-leo + one batched question
needs-leo + owner "CONTINUE: ..." --> resume the parked phase
```

**Schema changes.** No app data changes. The message header gains `phase=1|2` and the types `plan` and `summary`, for example `<!-- loop:v1 from=code type=plan phase=1 turn=N -->`. One new label: `awaiting-approval`. A keyword counts only at the start of an owner comment, in capitals, and only when posted after the executor's latest reply.

**Integration points.** GitHub REST (issues, comments, labels, events, pulls, merge), the Claude Code hourly scheduled task, and GitHub issue forms.

**Migration path.** Classic mode (Goal and Acceptance issues, `to-chat`, turn cap 4) stays as it is. An issue is in autopilot mode when its body has both `## Phase 1` and `## Phase 2` headings. PR #4's scripts and the existing issues keep working.

**Key decisions**
- Approval is a comment keyword, not a label. One word can be typed from the GitHub app on a phone, with no label menus.
- Only the owner's comments count, because the repo is public.
- Merging goes only through `loop_gh.py merge`, which re-checks the `APPROVED` comment, the PR's mergeable state and the pinned head SHA. This is a scripted gate, not model judgment.
- Merges use a merge commit, not a squash. This keeps one commit per task on `main` and rewrites no history.
- The plan lives at `<project folder>/docs/plan-<feature>.md`, so the repo stays the source of truth. Repo-wide work like this plan uses the root `docs/` folder, adding a new file only. The Android docs there stay untouched.
- The executor never triggers itself. It acts only on `to-code` or on an owner keyword newer than its own last reply, with a hard cap of 10 executor replies per issue.
- The trigger is an hourly cron, not GitHub events. It needs no GitHub App, and an idle run costs one triage call.

## 3. Task breakdown (Phase 2)

| # | Task | Files | Pass/fail check |
|---|---|---|---|
| 0 | Merge PR #4 (merge commit), then merge `main` into `claude/loop-autopilot` | none | `pulls/4` shows `merged: true`; the branch contains the PR #4 merge |
| 1 | Phase state machine and keywords | `scripts/loop_guard.py`, `evals/test_scripts.py` | Guard cases in section 4 pass |
| 2 | Typed work, `awaiting-approval` scan, build stale threshold of 180 min | `scripts/triage.py`, `evals/test_scripts.py` | Triage fixture tests pass |
| 3 | `post-plan`, verified `merge`, `finish`; new reply types | `scripts/loop_gh.py`, `scripts/check_reply.py`, `evals/test_scripts.py` | Dry-run tests pass; merge refuses without `APPROVED` |
| 4 | Plan checker | `scripts/check_plan.py`, `evals/test_scripts.py` | Rejects a missing section, a missing final line, and code files in a Phase 1 diff |
| 5 | Procedure, template and entry docs | `SKILL.md`, `references/autopilot.md`, `references/task-template.md`, `references/setup.md` | quick_validate passes; package builds; SKILL.md under 500 lines |
| 6 | Issue form and label | `.github/ISSUE_TEMPLATE/autopilot.yml`; label `awaiting-approval` via REST | Contents API returns the form; label is listed; form tried in the browser |
| 7 | Hourly scheduled task | none (claude.ai) | Task listed and enabled. Fallback: Leo creates it from setup.md. |
| 8 | Live end-to-end test: issue #3 rewritten as an autopilot request | `odometer-trips/docs/plan-readme.md`, `odometer-trips/README.md` (both written by the loop) | Plan PR and `awaiting-approval` in 1 run; after Leo's `APPROVED`, merged and `done` within 2 runs |

## 4. Test plan

**Tooling.** Python `unittest` (standard library, no new dependencies), JSON fixtures in place of GitHub, `--dry-run` for every write, skill-creator `quick_validate` and `package_skill`, and one read-only live triage against `lheiiyy/test`.

**Guard and triage cases**
- An autopilot issue with `to-code` gives `plan`. A plan with no owner reply gives nothing.
- Owner `APPROVED` after the plan gives `build`. `APPROVED` from another user is ignored. `APPROVED` posted before the plan is ignored.
- Lowercase `approved`, or the word in mid-sentence, is ignored.
- `REVISE` gives `revise`. A 4th `REVISE` gives `needs-leo`.
- `needs-leo` followed by `CONTINUE` resumes the parked phase. 10 executor replies give `needs-leo`.
- Classic issues behave as before: the existing 14 tests still pass.
- An API failure exits 2.

**Write cases**
- `merge` refuses without a verified `APPROVED`, refuses when the PR is not mergeable, and pins the head SHA.
- `post-plan` and `finish` plan the right label changes.
- No command can add `to-code`.

**Checker cases**
- The plan checker rejects each defect listed in task 4 and accepts a valid plan.
- The reply checker allows `plan`, and allows `summary` up to 250 words.

**"Tests pass" means** every `unittest` run prints `OK`, with the output shown in the PR and in the final summary. Packaging validates, and the live triage exits 0.

## 5. Merge plan

- **Branch:** `claude/loop-autopilot`, created in Phase 1 with this plan. `main` is merged into it after PR #4 merges.
- **Method:** merge commit through REST: `PUT /repos/lheiiyy/test/pulls/<N>/merge` with `merge_method=merge` and the head `sha` pinned. No squash, rebase or force-push.
- **Merge when:** all section 4 tests pass with output shown, the package validates, the PR is `clean`, the diff touches only files listed in section 3, and Leo has replied `APPROVED` to this plan.
- **If a permission rule refuses the merge:** stop and ask Leo for one Merge tap. Do not work around it.
- **After merge:** update this file with status, decisions and test results, and leave the working tree clean. The final summary lists every changed file and the test output.
- **Task 8 runs after the merge,** because the scheduled task reads `main`.

**Assumptions accepted by approving:** merge commit; reply cap 10 and revision cap 3; build stale threshold of 180 minutes; keywords in capitals at the start of a comment; plan path `<project folder>/docs/plan-<feature>.md`.

AWAITING APPROVAL
