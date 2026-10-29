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
| Approval tied to the latest plan and authorized scope | Partly | Latest plan and REVISE rules are enforced. A file-scope check at merge is not built: D4 b keeps approval with no scope limit; the Lead's review checklist covers "only files the plan lists". Decision below |
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

- A full live loop with the new rules (plan → approval → build → review → merge) was not run; the scheduled tasks still use the old prompts until the owner updates them.
- Two runs claiming the same issue in the same second (no atomic claim exists).
- Whether a scheduled cloud run can start subagents (unchanged from before: UNVERIFIED).
- Branch protection on `main` (the token cannot read it) and GitHub Pages.
- Pushing workflow files (no workflow was added).

## Remaining risks

- **Shared identity:** every agent posts as the owner, so an unheaded comment starting with APPROVED would count. The header rule and the prompts are the barrier.
- **Relayed approval and in-chat MERGE:** a script cannot tell a chat from a scheduled run; the quote rules make misuse visible (the quote is in the summary or the merge commit) but do not prevent it.
- **Review independence:** a verdict is checked for head and PR, not for which session wrote it.

## Decisions still required from the owner

1. **Scope check at merge:** keep D4 b as is (no file-scope check), or add a `Scope:` line to plans and park a PR that changes files outside it (unless a `CONTINUE:` widened it).
2. **Scheduled tasks:** the Code task runs on Opus, the Lead task on Sonnet, and neither prompt passes `--session`. Move Code to Sonnet and add `--session` (setup.md has the updated prompts)?
3. **Account copy of the skill:** the installed copy still has the first version's scripts. Upload the packaged zip (or the merged repo folder) to replace it.
