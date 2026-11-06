# Smoke test

Run this once after installing or upgrading the skill in a repository, and before you trust the loop with real work. It takes about an hour and one or two Opus runs. Tick every box; a box you cannot tick is a finding, not a pass.

**Before you start (the order matters).** Refresh `.claude/skills/github-loop/` from the skill's source **and** update the Lead and Code scheduled tasks in the same sitting. A Lead that still follows the old instructions writes verdicts without `Why:` or `Confidence:`, and `check_reply.py` refuses them, so the loop stops at review.

## 1. Events (from `references/events.md`)

- [ ] **Dry run.** Actions, Loop fire, Run workflow, role `lead`, dry run on. The log says `dry run: would fire lead ...` and nothing fires.
- [ ] **One real fire per role.** Dry run off, role `lead`: a Lead run appears in the scheduled-task list and ends "No new work." Repeat for `code`.
- [ ] **A tiny live request.** File one docs-only request with the Autopilot form, with `Risk: high` and no deploy (for example "add one line to the README"). The Lead posts a plan within a minute; reply `APPROVED`; Code builds; the Lead reviews; the gate stops at exit 8 (high risk) and you merge it yourself.

## 2. Negative test: nothing fires

- [ ] Ask another account (or a collaborator) to comment `APPROVED` on the test issue. No run starts, and the issue does not move.
- [ ] Comment `approved` (lowercase) yourself. No build starts: only `APPROVED` in capitals approves a plan.

## 3. Model check

File three small test requests and compare each review's `Model:` line and `Why:` with the score table (`references/models.md`, Review routing v2).

| Request | Expected review | Expected Why |
|---|---|---|
| Easy: change one sentence in a doc | sonnet | `score 0 (documentation only)` |
| Three features: a small change in three different source folders, with a test | opus | `score 3 (3 feature areas)` or higher |
| Sensitive: touch a file such as `src/auth.js` (or a `risk_paths` file), **with `Model: sonnet` in the request** | opus | `hard stop (risk path ...)`: the owner's lower Model line cannot lower a hard stop |

- [ ] 3 of 3 Model lines match the table.
- [ ] Every sonnet verdict carries `Confidence:` and `Unchecked:`.
- [ ] **Defect link, dry run:** `python scripts/loop_gh.py defect --repo <o>/<r> --issue <a test issue> --pr <a merged loop PR> --turn <next turn> --dry-run` prints a `Galing sa #<PR>` note and a `bug` label, and refuses a PR that is not merged or not from a loop branch.

## 4. Cost log

Note your plan usage (wherever your Claude account shows it) right before and right after each run, so you know what a request really costs.

| Run | Role | Model | Usage before | Usage after | Delta |
|---|---|---|---|---|---|
| Part 1 live request: plan | Lead | | | | |
| Part 1 live request: build | Code | | | | |
| Part 1 live request: review | Lead | | | | |
| Part 3 easy: review | Lead | | | | |
| Part 3 three features: review | Lead | | | | |
| Part 3 sensitive: review | Lead | | | | |

- [ ] Every row is filled. (There is no Opus cap by default, so no run is held and no row is skipped. If you set `max_opus_per_window`, a held run gets the row "held", with no delta.)

## 5. Notes before relying on the loop

- The install in a real project (for example TDMS: its settings profile, the four repository secrets and the workflow) comes later, in that project's own setup PR. Check every path in `references/profiles/tdms.example.json` against the real repository first.
- The scheduled tasks' **API trigger** is a research preview: it can change or stop. The 6-hour backup schedule keeps the loop moving if a fire is missed.
- A finished check run is **not** an event: when CI finishes, nothing fires. Reply `CONTINUE:` on the issue, or wait for the backup run.
- `merge_phrase` (when set): the gate waits with exit 10 until you comment the phrase, exactly as written, on the PR or the issue, after the last push.

## 6. Pass criteria

- [ ] Every box in parts 1 to 3 is ticked with the expected result.
- [ ] Part 2 fired nothing.
- [ ] 3 of 3 Model lines in part 3 match the table.
- [ ] Every row of the cost log in part 4 is filled.

When all four pass, put the two scheduled tasks on their 6-hour schedule (`references/events.md`, step 4).
