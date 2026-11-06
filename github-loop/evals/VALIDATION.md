# Validation report: github-loop rework (2026-10-29)

Branch `claude/github-loop-rework`, based on `main` at `ee8de02` (PR #11). Everything below was run in a cloud session; nothing was merged, and the only GitHub writes were the branch push and the PR.

## Commands run and results

| Command | Result |
|---|---|
| `python3 -B evals/test_scripts.py` on `main` before any change | 112 run, 112 OK |
| `python3 -B evals/test_scripts.py` on this branch | 181 run, 181 OK (69 new; where an approved decision changed a rule, existing fixtures and three test bodies were updated, listed below) |
| 27 hand-made mutations of the new rules, each run against its test class | 26 caught. The survivor (dropping `evals` from `package.py`'s skip list) is equivalent: `evals/` is never walked |
| `ast.parse` of every script | all parse |
| `flake8 --max-line-length=120 scripts/` | 17 findings (18 on `main`); pyflakes (`--select F`) on scripts and tests: 0 |
| `ruff check scripts/` (this session's broad rule set) | 76 findings, all style (`re.I` alias, implicit string concatenation, unused `noqa`, `subprocess.run` without `check=`); 29 on `main` |
| Live, read-only: `triage.py --repo lheiiyy/test --role lead` (owner from the new config file) | `No new work.` |
| Live, read-only: `loop_gh.py verify --issue 9 --pr 10` | `ok: true, merged: true, on_base: true` |
| Live, read-only: `loop_gh.py merge --issue 9 --pr 10 --dry-run` (an already merged PR) | exit 5, "PR is not open", no write planned |
| Live, read-only: `readiness.py --repo lheiiyy/test --markdown` | runs; CI NEEDS SETUP, branch protection and Pages UNVERIFIED |
| Live, read-only: `outcomes.py --repo lheiiyy/test` then `improve.py` | 2 autopilot issues (#3, #9), 4 API calls, no proposals (fewer than 3 issues) |
| `route.py --step review --git-range origin/main...HEAD` on this PR | `risk: high` (the skill itself), experts architecture, backend, security, qa, documentation; review tier opus |

## Tests changed on purpose (approved decisions)

| Test | Why |
|---|---|
| `relayed()` helper, `test_relay_approval` | D10 b: the relayed quote must start with APPROVED; the name comes from the config |
| `GOOD_PLAN`, `ModelLineTests.PLAN`, `test_post_plan_is_the_leads` | Plans and plan replies now carry `Risk:` and `CI required:` lines; `post-plan` needs `--plan-file` |
| `test_finish_needs_the_report_lines` | D7 a: `finish` needs a merged PR (fixtures added) |
| `MergeTests` (PR fixture and PR number) | The PR must come from this repo, and the verdict must name the PR that is merged |

## Acceptance criteria (from the handoff)

| Criterion | Status | Evidence |
|---|---|---|
| Existing behavior preserved or changes documented | Complete | 112 original tests pass (fixtures and three test bodies updated as listed); CHANGELOG.md lists every behavior change |
| Routing chooses relevant expertise, not every expert | Complete | `RouterTests`: docs-only → 1 expert; auth → security, backend, qa |
| Approval and security controls cannot be bypassed by routing | Complete | Routing only adds gates; the merge gate computes risk itself from the PR's file list (`test_a_declared_low_risk_cannot_lower_a_sensitive_change`) |
| Approval tied to the latest plan and authorized scope | Complete (after D4 a) | Latest plan and REVISE rules are enforced; since the D4 a follow-up, a changed file outside the plan's `Files in scope:` makes `merge` exit 9 for the owner (`ScopeTests`) |
| No merge without authorization and checks | Complete | `MergeTests`, `MergeGateRuleTests` (fork, PR link, CI line, high risk exit 8, incomplete file list, refused merge call) |
| No close before a verified merge | Complete | `FinishRuleTests` (open PR → exit 7; `No PR: yes` only by the issue) |
| Automated regression suite, real results | Complete | 181 tests, results above |
| Pagination, concurrency, retry, API failures | Complete except concurrency | Paging and retries: `ReliabilityTests`. The claim stays best effort (GitHub has no atomic label claim); documented in loop_gh.py, setup.md and here |
| Self-improvement evidence-based, reversible, approval-gated | Complete (recommend only) | `OutcomeTests`: 3-issue threshold, guarded areas flagged, tampered records rejected, off switch, no file changed. Not called self-improving: nothing is applied automatically |
| Token efficiency measured, not asserted | Partly | Instruction size measured (below). Real token use per run is not exposed to the scripts, so it stays unmeasured |
| Documentation matches code | Complete | `DocsConsistencyTests` check every named script, reference and `loop_gh.py` command, and every script's `--help` |
| No production, destructive, permission or credential changes | Complete | None made. Scheduled tasks, installed skill, labels and protection untouched |

## Instruction size (characters divided by 4, a proxy, not measured tokens)

| Run | Before (main) | After |
|---|---|---|
| Code run: SKILL.md + autopilot.md | about 5,540 | about 4,770 |
| Lead run: SKILL.md + lead.md | about 5,900 | about 5,260 |
| Expert notes route.py adds per step | none | about 145 to 210 each, usually 2 to 4 |

SKILL.md went from 14,619 to 10,664 characters; classic mode and recovery moved to their own references, read only when needed. An idle scheduled run still reads no instructions at all (triage first, then stop).

## Metrics design (outcomes.py, improve.py)

- **Measured, from the GitHub record only:** plans and revisions, verdicts and review rounds, parks and their reason category, agent replies, merged (from the summary line), relayed approval, Model lines per reply type and how often a stronger tier was wanted, the plan's declared risk, comments from other accounts (counted as rejected evidence).
- **Sensitive data excluded:** no comment text is stored; park reasons become one of 14 fixed categories; `validate()` rejects any record field outside the fixed shape, so free text cannot reach a proposal.
- **Not observable, so not measured:** real token use, wall-clock time per step, retries inside a run, which expert notes a run actually read.
- **Evidence labels:** verified (counted from headers and labels), uncertain (park reasons and the merged line, read from free text), rejected (other accounts).

## Untested or unverified

- A full live loop with the new rules (plan → approval → build → review → merge) was not run. Since 2026-10-29 both scheduled tasks run on Sonnet and pass `--session sonnet`.
- Two runs claiming the same issue in the same second (no atomic claim exists).
- Whether a scheduled cloud run can start subagents (unchanged from before: UNVERIFIED).
- Branch protection on `main` (the token cannot read it) and GitHub Pages.
- Pushing workflow files (no workflow was added).

## Remaining risks

- **Shared identity:** every agent posts as the owner, so an unheaded comment starting with APPROVED would count. The header rule and the prompts are the barrier.
- **Relayed approval and in-chat MERGE:** a script cannot tell a chat from a scheduled run; the quote rules make misuse visible (the quote is in the summary or the merge commit) but do not prevent it.
- **Review independence:** a verdict is checked for head and PR, not for which session wrote it.

## Owner decisions after PR #12 (2026-10-29)

1. **PR #12 merged** on Leo's words in chat ("Merge or 12"), with the head pinned at `941478c` and his words in the merge commit message (`5a675e9`). `verify` reported `on_base: true`.
2. **D4 changed to a:** built on branch `claude/github-loop-scope` (follow-up below).
3. **Scheduled tasks:** the Code task moved from Opus to Sonnet; both prompts now pass `--session sonnet` and name the new merge and finish rules.
4. **Account copy of the skill:** Leo uploaded the packaged zip from PR #12 (identical SHA-256 to the one built here). Re-upload the zip from the follow-up after it merges.

## Follow-up: D4 a (scope check at merge)

| Command | Result |
|---|---|
| `python3 -B evals/test_scripts.py` | 187 run, 187 OK (6 new `ScopeTests`; plan fixtures gained a `Files in scope:` line) |
| 6 hand-made mutations of the scope rules | 5 caught on the first run; the survivor (ignoring a missing scope line) led to two more assertions, and then it was caught too |
| `flake8 --select F` on scripts and tests | 0 |

## Follow-up: portable setup (2026-10-30)

Branch `claude/loop-portable`, based on `main` at `84c8021`. The only GitHub writes are the branch push and the PR.

| Command | Result |
|---|---|
| `python3 -B evals/test_scripts.py` on `main` before any change | 187 run, 187 OK |
| `python3 -B evals/test_scripts.py` on this branch | 201 run, 201 OK (12 new `InitRepoTests`, 2 new `PostPlanRuleTests`; the package test also names the new files) |
| 8 hand-made mutations of `init_repo.py` and the path fallback in `loop_gh.py` (overwrite without `--force`, unquoted YAML value, a placeholder that ships, `lead_deep` losing `--min-tier` or opus, no repo-root fallback, a traceback for a missing plan file, an undetected self-copy) | 5 caught on the first run; the 3 survivors led to 3 new tests, and then all 8 were caught |
| `flake8 --select F` on scripts and tests | 0 |
| `init_repo.py --install-skill --prompts` into an empty folder | 3 files plus the skill written; a second run reports `unchanged`; the generated issue form parses as YAML and has the same field ids as the live form |
| Not run | A live scheduled task created from a rendered prompt; `--create-labels` against GitHub (dry run only); a second real repository |

## PR-A: settings schema, one glob matcher, source-only counting (2026-11-06)

Branch `claude/skill-fix-a`, based on `main` at `6fb85e8` (A0 merged). Plan: `docs/plan-skill-fixes.md` rev 3, section PR-A.

| Command | Result |
|---|---|
| `python3 -B evals/test_scripts.py` on `main` before any change (A0 baseline) | 213 run, 1 failure (`test_skill_frontmatter`) |
| `python3 -B evals/test_scripts.py` on this branch | 213 run, 213 OK. Two test bodies changed on purpose: `test_skill_frontmatter` accepts a quoted or bare `name:`, and `test_an_unknown_key_is_an_error` expects the new message (`unknown key` and `did you mean`). No test encoded the old file-count rule in a way that changed. |
| `python3 -B evals/test_config_rules.py` (new) | 19 run, 19 OK: every key loads, did-you-mean, 17 bad values, null means default, the 7-key file loads as before, the TDMS glob list (12 must match, 4 must not), matcher rules, file kinds, feature areas, the skill source folder, `risk_paths` only adds, source-only counting, route and the CLIs read the settings, a prefix list and `risk_paths` at the merge gate, triage and readiness run with the profile |
| `test_fire.py`, `test_route_event.py`, `test_workflow.py` | 10 OK; 30 OK; 9 OK (1 skipped: no installed workflow copy) |
| 14 hand-made mutations (glob `*` crossing `/`, `**` needing a level, case, `risk_paths` ignored, source folder not the skill, tests counted as source, the shortest feature root winning, `large` counting every file, the gate or route dropping the settings, a list prefix crashing, an unknown key accepted, `points` replacing the defaults, ranges unchecked) | 12 caught on the first run; the 2 survivors led to 2 new assertions, and then all 14 were caught |
| `flake8 --select F` on scripts and tests | 0 |
| `npm test` in `trip-monitoring/` (not edited) | 38 run, 38 pass; its regenerated screenshots restored before commit |

## PR-B: review routing v2 (2026-11-06)

Branch `claude/skill-fix-b`, based on `main` at `045cad5` (PR-A merged). Plan: `docs/plan-skill-fixes.md` rev 3, section PR-B.

| Command | Result |
|---|---|
| `python3 -B evals/test_scripts.py` on `main` before any change | 213 run, 213 OK |
| `python3 -B evals/test_scripts.py` on this branch | 213 run, 213 OK. Changed on purpose: the verdict fixture now carries `Why:`, `Confidence:` and `Unchecked:` (`VERDICT_MODEL`); the owner's review `Model: haiku` now gives sonnet; the subagent model line now ends with its Why. |
| `python3 -B evals/test_routing_v2.py` (new) | 37 run, 37 OK: the 9 rows of the plan's section 2 table and the 4 TDMS shapes (`routing_cases.json`), a Why line from route.py for every case, threshold and points from the settings, whole-word tokens, each hard stop, the owner override clamp, contract and defect signals, check_reply's new lines, the recheck cascade, the UTC-day cap and holds, the hold command, review_history.py, outcomes fields, improve proposals and `--open-issue` |
| `test_config_rules.py`, `test_fire.py`, `test_route_event.py`, `test_workflow.py` | 19 OK; 10 OK; 30 OK; 9 OK (1 skipped) |
| 32 hand-made mutations of the new rules (substring risk words, unsplit identifiers, risk words in tests, each hard stop removed, threshold ignored, haiku not lifted, contract and defect windows, doc lines counted, recheck missing or repeated, the merge gate skipping the recheck, a hold counted as a reply, the cap off by one or on a rolling 24 hours, a forced opus held, every reply counted, a sonnet recheck, check_reply and outcomes accepting free text, the hold dropping its label, improve below its minimum or posting twice, a non-loop PR counted as a defect) | 30 caught on the first run; the 2 survivors led to 2 new assertions, and then all 32 were caught |
| `flake8 --select F` on scripts and tests | 0 |
| `npm test` in `trip-monitoring/` (not edited) | 38 run, 38 pass; regenerated screenshots restored before commit |
| Not run | A live review on GitHub with the new lines; `review_history.py` and `improve.py --open-issue` against the GitHub API (fixtures and dry run only) |

### PR-B revision after Leo's review (2026-11-06)

Leo's decisions on the review checklist: R1 hold, with a 5-hour reset instead of the UTC day; R3 a hard stop always reviews on opus, even under the owner's `Model: sonnet`; R4 no Opus cap for now (it stays available as a setting); R7 the loop links a bug to the merged PR itself (`loop_gh.py defect`). R2, R5 and R6 as proposed.

| Command | Result |
|---|---|
| `python3 -B evals/test_scripts.py` | 213 run, 213 OK (the owner's `Model: haiku` on a sensitive review now gives opus, by R3) |
| `python3 -B evals/test_routing_v2.py` | 43 run, 43 OK (cap tests rewritten for the window and the off-by-default cap; new: hard stop beats a lower Model line, an overruled `Model: sonnet` is still held, `DefectLinkTests`) |
| `python3 -B evals/test_config_rules.py` | 19 run, 19 OK (`max_opus_per_window`, `opus_window_hours` replace `max_opus_per_day`) |
| `test_fire.py`, `test_route_event.py`, `test_workflow.py` | 10 OK; 30 OK; 9 OK (1 skipped) |
| 42 hand-made mutations (the 32 before, updated, plus: the window ignoring its hours, route holding without a cap, the owner lowering a hard stop, a forced sonnet escaping the cap, the cap on by default, the hold note ignoring the window, a defect note counted as a reply, a defect linked to any PR, review_history or outcomes ignoring defect notes, defect notes on any issue) | 40 caught on the first run; the 2 survivors led to 2 new tests, and then all 42 were caught |
| `flake8 --select F` on scripts and tests | 0 |

