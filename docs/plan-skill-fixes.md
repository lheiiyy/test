# Plan: github-loop skill fixes for TDMS (S1-S4, G1-G7)

Status: PLAN ONLY, waiting for the owner's OK. Nothing is built on this branch.
Repo: `lheiiyy/test`. `lheiiyy/TDMS` is not touched.
Target design: "Review model routing v2 = checklist score", as agreed. This plan does not reopen it.

Risk: high (every PR changes the loop's own scripts, which are its safety controls; the owner merges)
CI required: no (the skill evals run in the session; there is no skill CI job, and `.github/` stays as it is)
Files in scope: docs/plan-skill-fixes.md

## 0. What I found first (read this before the per-PR detail)

1. **Where the source is.** The only copy of the skill in this repo is `.claude/skills/github-loop/`
   (SKILL.md, `scripts/`, `references/`). It has **no `evals/` folder and no CHANGELOG.md**: both were
   deleted in commit `8866f95` ("Clear repository for Trip Monitoring project"). Commit `4223cbe` put the
   skill back for Trip Monitoring without them. The two copies differ only by a 2-line change in
   `references/events.md`. The other copy on this machine is a synced cache (`/root/.claude/skills/synced/...`).
   It is off limits.
   So no folder in this repo matches "SKILL.md + scripts/ + references/ + evals/" right now. The one that
   comes closest is the installed copy, and your rules say not to edit that. This is open question 1.
   The rest of the plan uses `<src>/` for the skill folder.
2. **G3 answer.** The merge gate reads the config: `loop_gh.py` line 402 checks
   `head.ref.startswith(a.branch_prefix)`, and line 534 loads it from the config. But:
   - `readiness.py` line 136 hardcodes `"claude/"` when it lists open PRs that are "not from the loop".
   - `branch_prefix` is a single string, so TDMS cannot allow both `feat/` and `docs/`.
3. **Merge phrase today.** The gate already has a manual path, `--owner-merge-quote`, which must start with
   `MERGE`. It is only used for high-risk or out-of-scope merges, and only in chat. Nothing checks for a
   phrase written on GitHub.
4. **Branch protection today.** `readiness.py` treats every failed protection read as "UNVERIFIED (403)". On a
   free plan with a private repo, GitHub answers 403 with an "upgrade" message. That is not an unknown: it
   means there is no protection at all.
5. **Review floor gap.** `pick_model.py` lets the owner's `Model: haiku` force a review down to haiku.
   Design v2 says review never goes below Sonnet, so this has to be clamped. It is a behavior change (section 3).
6. **Config callers.** `config.load()` is called by `loop_gh.py`, `triage.py`, `outcomes.py`, `readiness.py`
   and `improve.py`. One unknown key makes all five stop at start (S1 is confirmed).

## 1. Per-PR plan

Every PR: branch `claude/skill-fix-a|b|c`, small commits, a draft PR, then `Risk: high`, then the owner
reviews and merges. Each PR has its own plan OK before any build. Each PR adds one line to
`<src>/CHANGELOG.md` (restored in PR-A, see Q1). Test command for the skill:
`python3 -B <src>/evals/test_scripts.py` (the restored suite), plus the new test files below. I run the
Trip Monitoring tests too (`npm test` in `trip-monitoring/`) to show nothing else broke.

### PR-A Foundation (S1, S2, source-only counting, TDMS example profile)

**Files to change**
- `<src>/scripts/config.py`: replace `DEFAULTS` with a small `SCHEMA` table: key → (type, default, check).
  - Documented keys are accepted. Each is checked by type and range, and a bad value raises
    `ValueError("<key>: <why>")`.
  - An unknown key still raises (typo guard). The message names the closest documented key
    (`difflib.get_close_matches`): "unknown key `risk_path`; did you mean `risk_paths`?".
  - New keys, all optional: `feature_roots`, `risk_paths`, `risk_words`, `authority_docs`, `test_globs`,
    `doc_globs`, `points`, `threshold`, `max_opus_per_day`, `plan_dir`, `plan_sections`,
    `commit_ref_pattern`, `merge_phrase`, `deploy`.
  - `branch_prefix` accepts a string or a list of strings.
  - Guardrail checks in the validator:
    - `threshold` is an integer from 2 to 10.
    - Each `points` value is an integer from 0 to 5. Only the 9 known point names are allowed, and none
      can be negative.
    - `max_opus_per_day` is an integer from 0 to 50 (0 means every Opus item parks; it never means "drop
      to Sonnet").
    - `commit_ref_pattern` must compile as a regex.
    - `merge_phrase` must contain `#{n}`.
    - `deploy` is `"auto"` or `"off"`.
  - There are no keys for the review floor, the hard stops or "downgrade over cap", so no config can turn
    them off.
- `<src>/scripts/rules.py`:
  - `sensitive_paths(paths, cfg=None)` adds the config's `risk_paths` globs to the built-in `RISK_PATH`
    regex. Config can only add patterns, never remove built-in ones.
  - New `authority_hits(paths, cfg)`: built-in `CLAUDE.md`, `AGENTS.md`, plus `authority_docs` globs.
  - New `classify(paths, cfg)` sorts each path into `source | test | doc | lockfile | generated`, using
    `test_globs` and `doc_globs` plus built-in lockfile and generated patterns (`*.lock`,
    `package-lock.json`, `*.min.js`, `dist/`, `build/`).
  - New `feature_areas(source_paths, cfg)`:
    - When a path sits under one of the `feature_roots`, its area is the next path segment.
    - Otherwise its area is the file's parent folder. Root files share one area.
  - Docs-only stays never sensitive. The two existing exceptions stay as they are: `.github/` and the
    skill folder.
  - An authority doc alone is not "sensitive" for the merge gate. It is a routing hard stop in PR-B.
- `<src>/scripts/pick_model.py`: `large` counts **source files only** (from `classify`). This is the S3 part
  that belongs in PR-A. Scoring itself comes in PR-B.
- `<src>/scripts/route.py`, `<src>/scripts/loop_gh.py`: pass `cfg` to `sensitive_paths`/`risk_tier`, so all
  three readers keep sharing one rule set. Plain argument passing, no new logic.
- New `<src>/references/profiles/tdms.example.json`. It holds **example values only**, for you to review:
  - `risk_paths`: `src/**/env*`, `src/**/session*`, `src/**/repository*`, `src/**/scoring*`,
    `src/**/platform*`, `src/**/props*`, `config/settings.json`.
  - `authority_docs`: `docs/permissions*.md`, `docs/data-model*.md`, `docs/decisions*.md`,
    `docs/business-rules*.md`.
  - `branch_prefix`: `["feat/", "docs/"]`, `merge_phrase`: `"OK i-merge #{n}"`, `deploy`: `"off"`.
  - No IDs, tokens or real data.
- `<src>/references/setup.md`: a table of every key with its type, default and range.

**New tests and evals** (`<src>/evals/test_config_rules.py`)
- Every documented key loads. An unknown key raises with the "did you mean" text. A bad type or range
  raises.
- `threshold: 1` raises. `points.no_tests: -1` raises. An unknown point name raises.
- The example profile loads clean.
- TDMS misses from S2 are now sensitive: the Props adapter path, `config/settings.json`, and
  env/session/repository/scoring/platform files.
- Docs-only `docs/x.md` is not sensitive. `CLAUDE.md` is an authority hit, not sensitive.
- `classify`: tests, docs, `package-lock.json` and `dist/x.js` are not source.
- `feature_areas` with and without `feature_roots`.
- Regression: 10 files = 5 source + 4 tests + 1 doc, so `large` is false (today it is true).

**Acceptance checks**
- The restored suite passes unchanged, except tests that encode the old `large` rule. Those are listed in
  the PR, the same way VALIDATION.md did it last time.
- A repo with today's `.github/github-loop.json` (7 keys) loads to the same values as before.
- `readiness.py` and `triage.py` run against fixtures with the TDMS example profile, with no exception.

**Risk**: high (skill scripts). Main danger: a config pattern that matches too much, or too little. The
mitigation is that config can only add patterns, never remove one.

### PR-B Routing v2 (scoring, hard stops, cascade, cap, Why line, learning hooks)

**Files to change**
- `<src>/scripts/pick_model.py`: new `score(paths, diff, cfg, history)` returns `(points, reasons)`. The
  review step uses the rules below:
  - Points (defaults; each one can be changed in `points`, from 0 to 5):

    | Signal | Points |
    |---|---|
    | Feature areas | 1 = 0, 2 = +1, 3+ = +3 |
    | Source files | 4-7 = +1, 8+ = +3 |
    | Diff lines (added + removed, source and tests) | 150-400 = +1, >400 = +2 |
    | `risk_words` hit in changed source lines or names (default words: calculat, score, rate, total, amount, money, price, date, due) | +3 |
    | Public contract changed (Q2) | +2 |
    | `authority_docs` changed | +2 |
    | Source changed with no test change | +2 |
    | A `CHANGES REQUESTED` verdict earlier on this issue | +1 |
    | A post-merge defect in the same area within 14 days (Q3) | +2 |

  - Hard stops to Opus. Each is checked before the score and cannot be configured away:
    - a `risk_paths` or sensitive path, or a sensitive goal word (`RISK_TEXT`);
    - `Risk: high`;
    - a test deleted, `skip`/`only`/`xit`/`.todo` added, or an assertion line removed with none added in
      the same test file ("weakened");
    - the third review round;
    - an authority doc changed with no source alongside.
  - Score 0 to `threshold - 1` (default 0-2) goes to Sonnet. Score at `threshold` or more (default 3+) goes
    to Opus.
  - Owner `Model:` wins. For review it is clamped to Sonnet or Opus: `haiku` is lifted to Sonnet and
    `fable` is never picked.
  - The `model_line` becomes `Model: <tier> ... Why: score N (<top 3 reasons>)`, or
    `Why: hard stop (<reason>)`.
- `<src>/scripts/check_reply.py`:
  - A review verdict's Model line must carry `Why:`.
  - A Sonnet review must carry `Confidence: high|low` and an `Unchecked:` line (`none` is allowed).
- `<src>/scripts/triage.py` and `<src>/scripts/route.py`:
  - Cascade: a Sonnet verdict with `Confidence: low` creates one `review-recheck` work item, tier Opus,
    limited to the `Unchecked:` text. It happens at most once per head SHA.
  - Cap: `max_opus_per_day` (default 3) is counted from today's (UTC) loop replies whose Model line says
    `opus`. An Opus item over the cap is parked with label `needs-leo` and the reason `Opus cap N/N reached`.
    It is never downgraded. An owner `Model: opus` override is still counted, but it is not parked.
- `<src>/scripts/outcomes.py`: new fixed fields: `review_score` (int or null), `why` (fixed reason codes
  only, no free text), `hard_stop` (code or null), `confidence` (`high|low|null`), `rechecked` (bool),
  `cap_parked` (bool), and `areas` (area names from the file list). `FIELDS` and `ENUMS` are updated, so
  validation stays strict.
- `<src>/scripts/improve.py`: new patterns, each needing at least 3 issues:
  - Opus reviews with no findings ("threshold may be low");
  - Sonnet reviews followed by a post-merge defect ("threshold may be high");
  - frequent `Confidence: low`;
  - frequent cap parks.
  New `--open-issue` posts one proposal issue (label `improve-proposal`, deduped by title). It never edits
  a file.
- `<src>/references/models.md`: replace the review row and the Lead Deep table text with the v2 rules, the
  score table, the cascade and the cap.
- `<src>/SKILL.md`: one line pointing at the v2 rules (the Model line now has `Why:`).

**New tests and evals** (`<src>/evals/test_routing_v2.py`)
- Each row of the score table in section 2 is one test, with the expected tier and Why text.
- Each hard stop is tested on its own.
- Threshold change through config. `points` set to 0 for one signal.
- Clamp: `Model: haiku` on a review gives Sonnet.
- Cascade: a low-confidence verdict creates one recheck. A second low verdict on the same SHA creates
  none.
- Cap: the fourth Opus item parks with `needs-leo` and does not become Sonnet.
- `check_reply` rejects a Sonnet verdict without `Confidence:`.
- `outcomes.validate` rejects a free-text `why`.
- `improve --open-issue` dry run plans exactly one POST and no file writes.
- Eval set (`<src>/evals/routing_cases.json`): the 4 recent TDMS PR shapes, described by file **pattern**
  only (no repo content). The expected result is that none goes to Opus on file count alone, and the
  Props-adapter one hits a hard stop.

**Acceptance checks**
- All suites pass.
- `route.py --step review` on fixtures prints a `Why:` line for every case.
- With no new keys, a docs-only PR still reviews on Sonnet and a sensitive PR still reviews on Opus.

**Risk**: high.
- It changes who reviews, and adds a reply-format rule that existing Lead tasks must follow.
- Mitigation: `check_reply` names the missing line exactly, and models.md shows the new verdict shape.

### PR-C Process fit (S4, G1, G2, G3, G4, G5, G7)

**Files to change**
- `<src>/scripts/check_plan.py`:
  - `plan_sections` takes either a list of section names or `"lite"`. `"lite"` means: Goal, Tasks, Tests,
    Merge plan.
  - Topic checks run only for the six known heavy names.
  - These checks always stay, whatever the profile: the Merge plan with its `Risk:`, `CI required:` and
    `Files in scope:` lines, a model tier, and `AWAITING APPROVAL`.
  - `plan_dir`: when it is set, the plan path must be under it.
  - G1: when `commit_ref_pattern` is set, the plan must contain a match (the task ID and rule IDs).
- `<src>/scripts/loop_gh.py` merge gate:
  - G3: `branch_prefix` can be a list.
  - G1: when `commit_ref_pattern` is set, every PR commit message must match (read from
    `pulls/N/commits`). Otherwise exit 5, naming the commits that fail.
  - G4: when `merge_phrase` is set, the gate needs an **owner** comment, exactly `OK i-merge #<PR number>`,
    posted after the latest head commit. It may be on the PR or on the issue. Without it, exit 8, "waiting
    for the owner's merge phrase". When `merge_phrase` is set, every merge waits for this phrase.
  - `deploy: "off"`: the release step is skipped. The report line says `deployed: no (deploy: off, manual
    step for the owner)`, and `check_reply.py` accepts that line.
- `<src>/scripts/readiness.py`:
  - G3: the open-PR row uses the config prefix (or prefixes) instead of `"claude/"`.
  - G2: when the protection read returns 403 with GitHub's upgrade message, or 404, the row says plainly:
    "No branch protection (private repo on a free plan). `loop_gh.py merge` is the only gate. Do not
    merge from the GitHub page." A separate "Merge gate" row shows the owner's merge phrase, when one is
    set.
  - With `deploy: "off"`, the Pages row is NOT REQUIRED.
- `<src>/references/autopilot.md`, `<src>/references/task-template.md`: the lite plan shape, plan_dir, and
  the commit ref line.
- New `<src>/references/smoke-test.md`, which holds:
  1. The 3 steps from `references/events.md`: workflow dry run; one real fire per role; one tiny docs-only
     issue with `Risk: high` and no deploy. `events.md` then links to this file instead of repeating them.
  2. A negative test: a stranger's comment, and a lowercase "approved" from the owner, both fire nothing.
     Check the Actions log and the scheduled-task list.
  3. A model check: 3 test issues (easy; 3 features; sensitive). Compare each Model and Why line with the
     section 2 table.
  4. A cost log: usage (tokens or the plan's usage meter) before and after each run, in a small table
     (run, role, model, before, after, delta). This is G5. The skill cannot read token use, so the owner
     records it.
  5. G7 notes:
     - TDMS install and secrets come later;
     - the API trigger is a research preview and its header can change;
     - a finished check is not an event (reply `CONTINUE:` or wait for the backup run).
  6. Pass criteria: each step's expected result, all checked; zero fires from step 2; 3 of 3 Model lines
     match the table; every cost row filled.

**New tests and evals** (`<src>/evals/test_process_fit.py`)
- A lite plan passes; a lite plan without a Merge plan fails; the heavy default stays the same.
- A plan outside `plan_dir` fails.
- A commit ref is missing in the plan, or in one commit, and the check fails with that commit named.
- A branch on the `feat/` or `docs/` list passes the gate; `fix/` fails.
- Merge phrase: missing, then exit 8. Written by a stranger, ignored. Posted before the latest push,
  ignored. Wrong PR number, ignored. Correct, the merge goes ahead.
- `deploy: off` makes the report line pass.
- Readiness with a fixture for a free-plan 403 gives the plain wording. The open-PR row uses the
  configured prefixes.

**Acceptance checks**
- All suites pass.
- `readiness.py --markdown` on fixtures shows the G2 wording.
- `check_plan.py` passes on a TDMS-style lite plan fixture.
- smoke-test.md covers all 6 parts above.

**Risk**: high. The merge gate gets two new checks. Both can only add stops; neither can remove one.

## 2. Score table (proposed defaults, threshold 3)

Assumptions for line counts are shown. "Areas" counts source files only. Today's result is from the
current `pick_model.py`.

| Shape | Points | Score | v2 review | Today |
|---|---|---|---|---|
| Docs-only small (README, 30 lines) | none (no source) | 0 | Sonnet. Why: score 0 (documentation only) | Sonnet |
| 1 area, 3 source + tests, about 200 lines | lines +1 | 1 | Sonnet. Why: score 1 (diff 150-400) | Sonnet |
| 9 source in 1 area + tests, about 450 lines | files 8+ +3, lines >400 +2 | 5 | Opus. Why: score 5 (9 source files, diff >400) | Opus |
| 3 areas, 3 source + tests, about 120 lines | areas 3+ +3 | 3 | Opus. Why: score 3 (3 feature areas) | Sonnet |
| 1 risk_path file + 1 other | hard stop | n/a | Opus. Why: hard stop (risk path `src/.../props-adapter.js`) | Opus |
| Authority doc alone (`docs/decisions.md`) | authority +2, plus a hard stop (no code alongside) | 2 | Opus. Why: hard stop (authority doc changed with no code) | Sonnet |
| Code with no tests: 1 area, 2 source, about 100 lines | no tests +2 | 2 | Sonnet. Why: score 2 (no test change) | Sonnet |
| (variant) same, 4 source files | files +1, no tests +2 | 3 | Opus. Why: score 3 (no test change, 4 source files) | Sonnet |
| (S3 check) 5 source + 4 tests + 1 doc, 1 area, about 250 lines | lines +1 | 1 | Sonnet. Why: score 1 (diff 150-400) | **Opus** (10 files) |

What changes overall: Opus no longer comes from test, doc or lockfile counts. It does come from breadth
(areas), missing tests and authority docs, which today's rules do not see.

## 3. Backward compatibility

A repo with no new keys keeps running. The defaults reproduce today's config values, and no new key is
required. Here is every behavior change that existing users will see even with no new keys:

1. **PR-A**: `large` counts source files only. Big diffs made of tests, docs or lockfiles stop going to Opus
   (for plan, build and review).
2. **PR-A**: `CLAUDE.md`/`AGENTS.md` are recognized as authority docs. This has no merge-gate effect.
3. **PR-A**: unknown-key errors now suggest the correct key. A bad value for a documented key now fails
   with a clear message. Before, it was accepted silently. Only a broken config sees this.
4. **PR-B**: review routing becomes the score. Some reviews move up: 3+ areas, a risk word in the code,
   code without tests plus 4 or more files, a deleted or skipped test, an authority doc alone. Some move
   down: many test or doc files.
5. **PR-B**: the owner's `Model: haiku` on a review is lifted to Sonnet.
6. **PR-B**: every review Model line must carry `Why:`. Sonnet verdicts must carry `Confidence:` and
   `Unchecked:`. Lead prompts that copy the old verdict shape are rejected by `check_reply.py` until they
   add the lines. The error says exactly what is missing.
7. **PR-B**: a default cap of 3 Opus items per day. The 4th is parked with `needs-leo`, where before it ran.
8. **PR-B**: a low-confidence Sonnet review adds one Opus recheck (more Opus use, and it counts toward the
   cap).
9. **PR-C**: readiness wording changes: the plain "no branch protection" line, and the open-PR row uses
   the config prefix. The values are the same for the default `claude/`.
10. Unchanged without the keys: plan sections (still the six), plan location, commit messages, merge phrase
    (none), deploy (auto), and the `claude/` branch prefix.

## 4. Open questions (with my recommendation)

1. **Where is "the source"?** The only skill copy here is the installed one, `.claude/skills/github-loop/`,
   and `evals/` and CHANGELOG.md are gone (commit `8866f95`).
   *Recommend:* PR-A restores the full source from `8866f95^` into a new top-level `github-loop/` folder
   (SKILL.md, scripts, references, evals, CHANGELOG). All three PRs edit only that folder. The installed
   copy stays as it is, and you refresh it yourself after PR-C. In `rules.py`, the skill-path rule then
   also matches `github-loop/`, so the source stays high-risk.
   This adds a folder outside `trip-monitoring/`, which CLAUDE.md treats as a `needs-leo` item, so your OK
   on this plan should say yes or no to it.
   The alternative is to edit `.claude/skills/github-loop/` in place, but that is the copy your rules say
   not to touch.
2. **How do we detect "public contract changed"?** There is no config key for it.
   *Recommend:* count it when the plan or PR has a `Public contract: changed` line, **or** the diff removes
   or renames a top-level `function`/`export`/`module.exports` line in a source file. Simple, and wrong
   only in the safe direction.
3. **What counts as a "post-merge defect in the same area"?**
   *Recommend:* an issue by the owner with the label `bug` (or `defect`) that names a merged loop PR (`#N`),
   opened within 14 days of that merge. Its areas come from that PR's files. When the history cannot be
   read, the signal gives 0 and the Why line says "defect history unknown". It never blocks.

## 5. `.github/` and templates

- No PR touches `.github/` (not `github-loop.json`, not the workflows, not the issue forms). TDMS values
  ship only as `references/profiles/tdms.example.json`.
- No file under `references/templates/` changes. The verdict and plan shapes live in `models.md`,
  `autopilot.md` and `task-template.md`.
- Every PR is still **Risk: high**, because it changes the loop's own safety scripts. You review and merge
  each one; the loop does not.

AWAITING APPROVAL
