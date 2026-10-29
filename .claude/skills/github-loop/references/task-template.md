# Autopilot request template (Leo's)

File it with the **Autopilot request** issue form (Issues → New issue), which applies `to-code` for you. Or paste it into a new issue, fill every `[PLACEHOLDER]`, and add the `to-code` label. The executor answers with a plan within about an hour. Reply `APPROVED` (capitals) to build and merge, `REVISE: <notes>` to change the plan, or `CONTINUE: <answer>` to answer a question.

The `## Phase 1` and `## Phase 2` headings are what switch the loop into autopilot mode, so keep them.

```markdown
## Objective
Take this automation from business plan to merged, tested code in two phases, with one approval gate between them: [AUTOMATION GOAL, one sentence].

## Context
- Project: [PROJECT NAME], repo: [REPO NAME].
- Stack: [STACK, e.g. Frontend → service/API layer → Google Apps Script → Google Sheets, kept migration-ready for a REST backend and database].
- Users: [WHO USES IT]. Must work on desktop, tablet and phone.
- The repository is the source of truth. Read the existing docs first and don't re-read the whole codebase.

## Phase 1: Plan (do this first, then stop)
Write docs/plan-[FEATURE].md with these sections, each kept tight:
1. Business plan: problem, users, value, scope, out-of-scope, success metrics, risks, effort estimate.
2. Architecture: components, data flow, schema changes, integration points, migration path, key decisions with one-line reasons.
3. Task breakdown: ordered tasks, each with the files touched and a pass/fail check.
4. Test plan: what gets tested, with which tooling, and what "tests pass" means.
5. Merge plan: branch name, merge method, and the conditions for merging.
End the file with the line "AWAITING APPROVAL". Make no code changes in Phase 1.

## Phase 2: Build, test, debug, merge (only after I reply "APPROVED")
The approved plan authorizes everything in it, including the merge.
1. Create a feature branch. Implement the tasks in order, one commit per task.
2. Set up the test harness from the test plan, write the tests, run them.
3. Debug failures: find the root cause before fixing, fix the cause and not the symptom, then re-run.
4. When every acceptance criterion passes, merge to the main branch using the plan's merge method. Update the project docs with status, decisions and test results.

## Constraints
- Repo identity gate: confirm the repo and project match [REPO NAME] before any change. If they don't, stop.
- Do only what the approved plan says. No extra features, files or dependencies.
- Never commit secrets (API keys, clasp credentials, tokens). Assume authentication is already set up.
- Never force-push, rewrite history, or delete files or data outside the plan.
- Keep docs short and structured. Report only at checkpoints.

## Stop and ask when
- Anything must change outside the approved plan (scope, schema, architecture).
- A fix needs a new dependency or external service.
- The same error survives 2 fix attempts.
- A merge conflict touches files outside the plan.

## Acceptance Criteria
- [ ] The plan file existed and was approved before any code was written
- [ ] All planned tests ran and passed, with the output shown
- [ ] Merged to main with a clean working tree
- [ ] Docs updated with status, decisions and test results
- [ ] Final summary lists every file changed and the test results

## Progress Evidence
Back every completion claim with a command output or a changed file.
```
