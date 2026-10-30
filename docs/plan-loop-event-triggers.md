# Plan: github-loop event triggers (fire Lead and Code on GitHub events)

Request: issue #16. Earlier loop plan: `docs/plan-loop-autopilot.md`. Loop rules: `.claude/skills/github-loop/SKILL.md`. Status document: this file's `## Status` section (Code adds it).

## 1. Business plan

- **Problem:** the Lead and Code scheduled tasks poll GitHub once an hour (Code at minute 3, Lead at minute 33), so every hand-off (plan, approval, build, verdict, merge) waits up to an hour. One slice spends several hours waiting.
- **Users:** Leo (owner), and the Lead and Code scheduled tasks.
- **Value:** a hand-off starts in about a minute. Leo's `APPROVED` starts Code, Code's result starts the Lead, the Lead's verdict starts Code.
- **Scope:** one GitHub Actions workflow that, on an owner event, decides which role must run and starts that role's scheduled task through its API trigger. A small Python router decides; a small Python script does the POST. The hourly schedules stay as the backup.
- **Out of scope:** `claude-code-action`; the scheduled tasks' own GitHub triggers (they cover pull request, release and issue events, not comments, so they cannot hear `APPROVED`); a CI test workflow; changes to the scheduled task prompts or to the skill files; lowering the hourly schedules (Leo decides after a week of use); anything for `odometer-trips/`.
- **Success metrics:** (1) the router unit tests pass for every row of the decision table, including the negative cases; (2) an owner `APPROVED` starts Code within about 2 minutes in the live test, against up to 60 now; (3) no secret, task ID or token appears in the repository, the workflow log or a fire payload; (4) when a fire fails, the run goes red and the hourly schedule still picks the work up. Items 2 and 4 are Leo's smoke test after the merge; a cloud session cannot run a workflow.
- **Risks:** (1) the API trigger is a research preview, so the endpoint or beta header can change; the hourly schedule is the fallback. (2) A leaked token lets anyone start runs on Leo's usage; tokens live only in GitHub Secrets and are never printed, and Leo can regenerate a token in the task settings. (3) Agents post as Leo's account, so every loop comment fires the workflow; only recognized loop headers and capital-letter keywords fire a role, and the loop's own reply caps still apply. (4) The repository is public, so strangers can comment; every job is skipped unless the actor is the owner. (5) Event delivery is not guaranteed; a missed event costs at most the old hourly wait. (6) A fire in the same minute as an hourly run starts two sessions; `loop_gh.py claim` stops the second. (7) Each fire draws subscription usage; idle runs end at once with "No new work.". (8) Code's token may be refused for files under `.github/workflows/` (see Readiness); the fallback is a manual move by Leo.
- **Effort estimate:** four tasks, about 2 Code cycles, one opus review round, then about 15 minutes of Leo's setup.

## 2. Architecture

- **Components:**
  - `.github/workflows/loop-fire.yml`: the workflow. Triggers `issues` (`opened`, `labeled`), `issue_comment` (`created`) and `workflow_dispatch` (inputs `role`, `dry_run`).
  - `.github/loop-fire/route_event.py`: reads the event JSON from `$GITHUB_EVENT_PATH` and prints the roles to fire. It has no secrets and imports `HEADER`, `KEYWORD`, `fields_of` and `is_autopilot` from the skill's `loop_guard.py`, so keywords and headers mean exactly what the loop means.
  - `.github/loop-fire/fire.py`: sends one POST per role. It is the only code that sees the secrets.
  - Tests: `test_route_event.py`, `test_fire.py`, `test_workflow.py` in the same folder.
- **Data flow:** owner event → workflow `if` (actor is the repository owner) → checkout of the default branch → router step (no secrets) → fire step (secrets in `env`) → `POST https://api.anthropic.com/v1/claude_code/routines/<id>/fire` → a fresh scheduled-task session → `triage.py` reads GitHub and does the work, or ends with "No new work.".
- **Decision table (the router):**

| Event | Condition | Fires |
|---|---|---|
| `issues` opened or labeled | issue by the owner, label `to-code` present, not a pull request | Lead if the body has Phase 1 and Phase 2 headings (autopilot), else Code |
| `issue_comment` created | comment starts `APPROVED` (capitals, owner, no loop header) | Code |
| same | comment starts `REVISE:` | Lead |
| same | comment starts `CONTINUE:` | Lead and Code (triage picks the one with work) |
| same | header `from=lead type=approval` (approval relayed from chat) | Code |
| same | header `from=code type=result` | Lead |
| same | header `from=lead type=verdict` | Code |
| same | any other header (`plan`, `question`, `summary`), or no keyword | nobody |
| `workflow_dispatch` | owner only | the chosen role, or only a printout when `dry_run` is on |

  Every `issue_comment` row also needs: the issue is by the owner, the comment is by the owner (`author_association` OWNER), and the comment is on an issue, not a pull request.
- **Schema changes:** none. No application data, no migration. Rollback is deleting the workflow file (or disabling it in the Actions tab); the hourly schedules keep working.
- **Integration points:** GitHub Actions; the scheduled tasks' API trigger (research preview, headers `anthropic-beta: experimental-cc-routine-2026-04-01` and `anthropic-version: 2023-06-01`). Four repository secrets: `LOOP_LEAD_FIRE_URL`, `LOOP_LEAD_FIRE_TOKEN`, `LOOP_CODE_FIRE_URL`, `LOOP_CODE_FIRE_TOKEN`.
- **Migration path:** none needed. The two scheduled tasks gain an API trigger; their prompts do not change, because they ignore the fire text and read GitHub themselves.
- **Key decisions:**
  - The API trigger on the existing tasks, not their GitHub trigger, because the GitHub trigger has no comment event.
  - No `pull_request` trigger (a change from the issue's sketch). Lead opens its own plan PR, so it would fire the Lead for nothing; Code's `type=result` comment is the real "ready for review" signal.
  - The router reuses the skill's own regexes, so the two cannot drift apart.
  - Comment text never reaches a shell or the fire payload. The router reads the event file in Python; the payload is a fixed string such as `loop-fire v1 role=lead issue=16 event=issue_comment`.
  - The router runs in a step with no secrets; only the fire step has them.
  - `permissions: contents: read`; `actions/checkout` pinned to a full commit SHA that Code resolves with `gh api`; `persist-credentials: false`. Never `pull_request_target`, and no pull request code is checked out, so strangers' code never meets the secrets.
  - `fire.py` accepts only `https://api.anthropic.com/v1/claude_code/routines/trig_.../fire`, so a mistyped secret cannot send a token to another host.
  - Missing secrets give a workflow warning and exit 0 (not set up yet); a half-set pair, an HTTP error or a timeout exits 1 so the run turns red. Output never includes a header, URL or response body.
  - `concurrency` per issue, without cancelling, collapses bursts of comments.
  - Standard library only, so there is no dependency to install.

## 3. Task breakdown

| # | Task | Agent | Files | Pass/fail check |
|---|---|---|---|---|
| 1 | Router with the decision table, written test first | Code | `.github/loop-fire/route_event.py`, `.github/loop-fire/test_route_event.py` | Every table row passes; negative cases fire nothing: lowercase `approved`, keyword not at the start, header not first, comment by a stranger, comment on a pull request, issue by a stranger, `plan` / `question` / `summary` headers |
| 2 | Fire script, written test first | Code | `.github/loop-fire/fire.py`, `.github/loop-fire/test_fire.py` | With a fake opener: URL check, three headers, fixed JSON body, 20 second timeout; neither a token nor a URL in any output or error text; both secrets missing gives a warning and exit 0; half set or an HTTP error gives exit 1 after trying the other role |
| 3 | Workflow file and its static checks | Code | `.github/workflows/loop-fire.yml`, `.github/loop-fire/test_workflow.py` | Text checks pass: no `pull_request_target`; no `github.event.` expression inside a `run:` line; every action pinned to a 40-character SHA; secrets only in the fire step's `env`; `concurrency` and the owner `if` present. `actionlint` is run if it can be installed here, otherwise reported as not run |
| 4 | Docs: Status section | Code | `docs/plan-loop-event-triggers.md` | Status names the run commands, the results, the four secret names, Leo's setup steps, the smoke test and the rollback |

Model plan: build sonnet for tasks 1 to 3 and haiku for task 4 (documentation only); review opus (sensitive files: a workflow and secret handling); fix opus (sensitive files).

## 4. Test plan

- **Unit tests:** `python3 -m unittest discover -s .github/loop-fire -p 'test_*.py'`, standard library only. Uses dummy payloads (issue number 1, user `owner-test`); no real token, URL or task ID anywhere.
- **Replay:** `python3 .github/loop-fire/route_event.py --event issue_comment --payload <file>` prints the roles for a sample payload, used to check the CLI end to end.
- **Secret scan:** a search of the whole diff for `trig_`, `Bearer`, `sk-` and `ghp_` finds nothing except the URL pattern in `fire.py` and its test.
- **Tests pass** means every unittest passes, the secret scan is clean and `actionlint` is clean or reported as not run.
- **Cannot run in a cloud session:** the workflow itself (the Actions API is blocked from here), a live POST to the fire endpoint, and the event delivery. Leo's smoke test covers them.

## 5. Merge plan

- **Branch:** `claude/loop-event-triggers`, the branch of this plan PR.
- **Merge method:** merge commit.
- **Merge conditions:** Leo approved this plan; the Lead's verdict approves the exact head; the PR is clean and mergeable; only files in scope changed; **Leo taps Merge** (high risk: a workflow, secrets, the loop's own flow). After his tap he replies `CONTINUE: merged`.
- **Release policy:** no deploy. The merge to `main` is the release. Until the secrets exist, the workflow only prints a warning.

Risk: high
CI required: no
Files in scope: .github/workflows/loop-fire.yml, .github/loop-fire/, docs/plan-loop-event-triggers.md

## 6. Readiness

| Item | Status | Note |
|---|---|---|
| Repository, public, labels, skill on `main`, issue form, merge commits | READY | Readiness check on 2026-10-30: `lheiiyy/test`, default branch `main`, all labels present |
| Lead and Code scheduled tasks | READY | Both enabled and hourly; last runs succeeded or pending (checked 2026-10-30) |
| Task prompts need no change | READY | Both run `triage.py` first and never read a fire text |
| API trigger on the Lead and Code tasks | NEEDS SETUP | None exists yet. Leo adds one to each task on the web; the token is shown once |
| API trigger can be added to tasks created through the connector | UNVERIFIED | Not tried; the task settings page decides |
| Fire endpoint and beta header | UNVERIFIED | Documented as a research preview; not called yet. Limits: 30 fires per hour per task, 100 per hour per account |
| Four repository secrets | NEEDS SETUP | Leo creates them by hand (steps below) |
| GitHub Actions enabled on the repository | UNVERIFIED | The proxy blocks the Actions API; there are no workflows today |
| Code can push a file under `.github/workflows/` | UNVERIFIED | The session token may lack the `workflow` permission. If refused, Code keeps the same file at `.github/loop-fire/loop-fire.yml` and parks; Leo moves it with the GitHub web editor (rename the path to `.github/workflows/loop-fire.yml`) |
| Python 3 on the Actions runner | UNVERIFIED | Standard on `ubuntu-latest`; the smoke test shows it |
| Branch protection on `main` | UNVERIFIED | The session token cannot read it (403); the merge script reports a refusal |
| Subagent for the opus review in a scheduled run | UNVERIFIED | Without one, the review runs on the task's model and says so |
| Open PR #1 (android-parental-monitor) | READY | It touches none of the files in scope |
| Connectors, database, Playwright, formal GitHub approval | NOT REQUIRED | None used; all agents share one account |

**What Leo does by hand:**
1. Reply `APPROVED` on issue #16 to build.
2. While Code builds: for **each** of the two tasks (Lead and Code), open claude.ai/code/routines, open the task, Edit, add an **API** trigger, Generate token, and copy the URL and the token (shown once). Never paste them into chat, an issue or a file.
3. GitHub, repository Settings, Secrets and variables, Actions, New repository secret, four times: `LOOP_LEAD_FIRE_URL`, `LOOP_LEAD_FIRE_TOKEN`, `LOOP_CODE_FIRE_URL`, `LOOP_CODE_FIRE_TOKEN`. Check Settings, Actions, General allows actions.
4. After the Lead's verdict: tap Merge on the PR, then reply `CONTINUE: merged`.
5. Smoke test: Actions tab, Loop fire, Run workflow, role `lead`, dry run on (the log should say what it would fire); then dry run off and look for a new Lead run in the task's run list ("No new work." is correct).
6. The first real `APPROVED` after the merge is the live test. If nothing starts, the hourly run still does the work.
7. Do not turn on "required approvals" on `main`.

APPROVED by Leo on 2026-10-30 (relayed from chat, issue #16)

## Status

Built 2026-10-30, awaiting the Lead's review and Leo's merge tap.

- **Tests:** `python3 -m unittest discover -s .github/loop-fire -p 'test_*.py'` gives 47 tests, OK (router decision table and negative cases, fire script with a fake opener, static workflow checks).
- **Diff scan:** `trig_` appears only in the URL pattern of `fire.py` and dummy test values; no real credential value, `sk-` or `ghp_` in the diff.
- **Not run here:** `actionlint` (not installed; reported as not run), the workflow itself, a live POST. Leo's smoke test covers them.
- **Decisions:** `actions/checkout` is pinned to v4.2.2 (`11bd71901bbe5b1630ceea73d27597364c9af683`), written from knowledge, not resolved with `gh api` (that repo is outside this session's access). Lead please verify the SHA. The workflow file pushed to `.github/workflows/` without refusal.
- **Repository secrets (set by hand):** `LOOP_LEAD_FIRE_URL`, `LOOP_LEAD_FIRE_TOKEN`, `LOOP_CODE_FIRE_URL`, `LOOP_CODE_FIRE_TOKEN`. Until set, the workflow only prints a warning.
- **Leo's setup and smoke test:** steps 2 to 6 in section 6.
- **Rollback:** delete `.github/workflows/loop-fire.yml` or disable the workflow in the Actions tab; the hourly schedules keep working.
