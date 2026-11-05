# Plan: github-loop skill fixes for TDMS (S1-S4, G1-G7)

Status: PLAN ONLY, revision 2 (after the audit verdict FIX). Waiting for "OK A0". Nothing is built on
this branch.
Repo: `lheiiyy/test`. `lheiiyy/TDMS` is not touched.
Target design: "Review model routing v2 = checklist score", as agreed. This plan does not reopen it.

Risk: high (every PR changes the loop's own scripts, which are its safety controls; the owner merges)
CI required: no (the skill evals run in the session; there is no skill CI job, and `.github/` stays as it is)
Files in scope: docs/plan-skill-fixes.md

## 0. Findings and decisions

1. **Source location (decided, Q1 = option 1).** The only copy of the skill in this repo is
   `.claude/skills/github-loop/`, and its `evals/` and `CHANGELOG.md` were deleted in commit `8866f95`.
   - Leo's decision: a new top-level `github-loop/` folder holds the source, and it is restored first (PR-A0).
     That decision is the needs-leo OK for the new folder.
   - All later PRs edit only `github-loop/`. `.claude/skills/github-loop/` stays as it is; Leo refreshes
     it after PR-C. The synced cache under `/root/.claude/skills/synced/` is never touched.
   - Below, `<src>/` means `github-loop/`.
2. **G3.** The merge gate reads the config: `loop_gh.py` line 402 checks
   `head.ref.startswith(a.branch_prefix)`. Two gaps:
   - `readiness.py` line 136 hardcodes `"claude/"`.
   - `branch_prefix` is a single string, so TDMS cannot use both `feat/` and `docs/`.
3. **Exit 8 today.** `loop_gh.py` (docstring lines 40-42 and 67-69, line 417) defines exit 8 as "high
   risk: the owner merges". `--owner-merge-quote "MERGE ..."` clears it, and so do `autopilot.md`,
   `lead.md` and `runbook.md`.
   - If "waiting for the merge phrase" reused exit 8, a chat `MERGE` quote would also skip the phrase,
     and the runbook would print the wrong advice.
   - So the merge phrase gets a **new exit code 10**, with its own message (PR-C).
4. **Branch protection.** `readiness.py` reports every failed protection read as "UNVERIFIED (403)". On a
   private repo on a free plan, that 403 actually means there is no protection at all.
5. **Review floor gap.** `pick_model.py` lets the owner's `Model: haiku` force a review down to haiku.
   v2 clamps this to Sonnet.
6. **Config callers.** `loop_gh.py`, `triage.py`, `outcomes.py`, `readiness.py` and `improve.py` all call
   `config.load()`. One unknown key stops all five at start (S1 confirmed).

## 1. Per-PR plan

There are 4 PRs, in this order: **A0 → A → B → C**. Each one gets:
- its own plan OK from Leo;
- branch `claude/skill-fix-a0|a|b|c`, small commits, a draft PR, `Risk: high`;
- Leo's review and merge.

Each PR from A onward adds one line to `<src>/CHANGELOG.md`.
- Skill tests: `python3 -B <src>/evals/test_scripts.py`, plus the new test files listed below.
- I also run `npm test` in `trip-monitoring/`, to show nothing else broke. I do not edit that folder.

### PR-A0 Restore the source (no logic change)

**Files**
- New `github-loop/`: a byte-for-byte copy of today's `.claude/skills/github-loop/`, meaning `SKILL.md`,
  `scripts/` and `references/`.
- New `github-loop/evals/`, restored from `8866f95^`: `test_scripts.py`, `test_fire.py`,
  `test_route_event.py`, `test_workflow.py`, `VALIDATION.md`.
- New `github-loop/CHANGELOG.md`, restored from `8866f95^`, plus one line: "2026-11: source restored to
  top-level github-loop/".

**Acceptance**
- `diff -r .claude/skills/github-loop github-loop` shows only `evals/` and `CHANGELOG.md`.
- No script changes.
- The restored suites run against the current scripts. The baseline result (run, OK, failures with
  names) goes in the PR body as it is. Known risk: `references/events.md` changed by 2 lines after
  `8866f95^`, so a test that reads it may fail. Any failure is recorded, not fixed, in A0.
- `npm test` in `trip-monitoring/` passes.

**Risk**: high (it adds a copy of the safety scripts outside `.claude/skills/`; the copy is not active
until it is installed). Until PR-A lands, the new folder is not yet matched by the skill-path rule. A0
declares `Risk: high` itself, so the gate still sends it to Leo.

### PR-A Foundation (S1, S2, one glob matcher, source-only counting, TDMS example profile)

**Files to change** (config, rules and pick_model only, plus the example profile and the setup docs)
- `<src>/scripts/config.py`: `DEFAULTS` becomes a `SCHEMA` table: key → (type, default, check).
  - Documented keys are checked by type and range; a bad value raises `ValueError("<key>: <why>")`.
  - An unknown key still raises (typo guard), and names the closest key ("did you mean `risk_paths`?").
  - New optional keys: `feature_roots`, `risk_paths`, `risk_words`, `authority_docs`, `test_globs`,
    `doc_globs`, `points`, `threshold`, `max_opus_per_day`, `plan_dir`, `plan_sections`,
    `commit_ref_pattern`, `merge_phrase`, `deploy`.
  - `branch_prefix` accepts a string or a list.
  - Guardrail checks:

    | Key | Allowed values |
    |---|---|
    | `threshold` | integer, 2-10 |
    | `points` | integer 0-5 each; only the 9 known point names; no negatives |
    | `max_opus_per_day` | integer 0-50 (0 parks every Opus item and never drops it to Sonnet) |
    | `risk_words` | lowercase single tokens |
    | `commit_ref_pattern` | must compile as a regex |
    | `merge_phrase` | must contain `#{n}` |
    | `deploy` | `auto` or `off` |

    There are no keys for the review floor, the hard stops or downgrade-over-cap.
- `<src>/scripts/rules.py`:
  - **One glob matcher**, `glob_match(path, pattern)`, used for `risk_paths`, `authority_docs`,
    `test_globs`, `doc_globs` and `feature_roots`:
    - case-insensitive;
    - paths use `/`, and a leading `./` is removed;
    - `*`, `?` and `[...]` match inside one segment only and never cross `/`;
    - a `**` segment matches zero or more whole segments;
    - a pattern ending in `/**`, or in `/`, matches everything under that folder;
    - any other pattern must match the whole path.
    - `Files in scope:` keeps its current matcher (`in_scope`), so approved plans read the same.
  - `sensitive_paths(paths, cfg=None)`: the built-in `RISK_PATH` regex OR any `risk_paths` glob. Config
    only adds.
  - `authority_hits(paths, cfg)`: built-in `CLAUDE.md` and `AGENTS.md` (any folder) plus the
    `authority_docs` globs.
  - `classify(paths, cfg)` sorts each path into `source | test | doc | lockfile | generated`. It uses
    `test_globs` and `doc_globs`, plus built-in lockfile and generated patterns (`**/*.lock`,
    `**/package-lock.json`, `**/*.min.js`, `dist/**`, `build/**`).
  - `feature_areas(source_paths, cfg)`: the area of a file is the longest `feature_roots` folder pattern
    that matches the start of its path, for example `src/*` gives `src/repository`. Without
    `feature_roots`, the area is the file's parent folder.
  - The skill-path rule also matches `github-loop/` at the top level, so the source stays high-risk.
  - Docs-only stays never sensitive. The two current exceptions remain: `.github/` and the skill folder.
    An authority doc alone is not sensitive for the merge gate; in PR-B it becomes a routing hard stop.
- `<src>/scripts/pick_model.py`: `large` counts **source files only**. Scoring comes in PR-B.
- `<src>/scripts/route.py`, `<src>/scripts/loop_gh.py`: pass `cfg` into `sensitive_paths` and
  `risk_tier`. Argument passing only.
- New `<src>/references/profiles/tdms.example.json`, with **example values** for Leo to review:

  | Key | Example value |
  |---|---|
  | `risk_paths` | `src/repository/**`, `src/platform/**`, `src/**/env*`, `src/**/session*`, `src/**/scoring*`, `config/settings.json` |
  | `authority_docs` | `docs/PERMISSIONS.md`, `docs/DATA-MODEL.md`, `docs/DECISIONS.md`, `docs/BUSINESS-RULES.md` |
  | `risk_words` | the default list plus `date`, `rate`, `due`, `overdue`, `sla`, `total` |
  | `feature_roots` | `src/*` |
  | `branch_prefix` | `["feat/", "docs/"]` |
  | `merge_phrase` | `"OK i-merge #{n}"` |
  | `deploy` | `"off"` |

  There are no IDs, tokens or real data. The Props adapter is assumed to live under `src/platform/`.
- `<src>/references/setup.md`: a table of every key, with its type, default, range and the glob rules.

**New tests** (`<src>/evals/test_config_rules.py`)
- Config:
  - every documented key loads;
  - an unknown key raises with "did you mean";
  - a bad type or range raises (`threshold: 1`, `points.no_tests: -1`, an unknown point name);
  - the example profile loads clean;
  - today's 7-key `.github/github-loop.json` loads to the same values as before.
- **Glob list test** with the TDMS example profile. A path counts as a match if it is matched by
  `risk_paths` or `authority_docs`.
  - Must match: `src/core/env.js`, `src/env.js`, `src/api/session.js`, `src/repository/sheets.js`,
    `src/rules/scoring.js`, `src/platform/lock.js`, `src/platform/cache.js`, `config/settings.json`,
    `docs/PERMISSIONS.md`, `docs/DATA-MODEL.md`, `docs/DECISIONS.md`, `docs/BUSINESS-RULES.md`.
  - Must NOT match: `src/ui/index.html`, `src/rules/dates.js`, `README.md`, `docs/ROADMAP.md`.
  - The same must-not paths also give no built-in sensitive hit.
- Matcher unit cases:
  - `*` does not cross `/`;
  - `**` matches zero segments (`src/**/env*` matches `src/env.js`);
  - case is ignored (`docs/permissions.md` matches);
  - a trailing `/**` and a trailing `/` behave the same.
- `CLAUDE.md` is an authority hit, not sensitive. Docs-only `docs/x.md` is not sensitive.
- `classify`: tests, docs, `package-lock.json` and `dist/x.js` are not source.
- `feature_areas`, with and without `feature_roots`.
- `github-loop/scripts/x.py` is sensitive (the skill-path rule).
- Regression: 10 files made of 5 source, 4 tests and 1 doc give `large = false` (today it is true).

**Acceptance**
- The A0 baseline does not get worse. The only tests changed on purpose are the ones that encode the old
  `large` rule; they are listed in the PR.
- `readiness.py` and `triage.py` run on fixtures with the TDMS example profile, with no exception.

**Risk**: high. The main danger is a pattern that matches too much or too little; the glob list test pins
it down. Config can only add patterns.

### PR-B Routing v2 (scoring, hard stops, cascade, cap, Why line, learning hooks)

**Files to change**
- `<src>/scripts/pick_model.py`: new `score(paths, diff, cfg, history)` returns `(points, reasons)`, used
  for the review step.

  | Signal | Points (each can be changed in `points`, 0-5) |
  |---|---|
  | Feature areas | 1 = 0, 2 = +1, 3+ = +3 |
  | Source files | 4-7 = +1, 8+ = +3 |
  | Diff lines (added + removed, source and tests) | 150-400 = +1, >400 = +2 |
  | `risk_words` hit | +3 |
  | Public contract changed | +2 |
  | `authority_docs` changed | +2 |
  | Source changed with no test change | +2 |
  | A `CHANGES REQUESTED` verdict earlier on this issue | +1 |
  | A post-merge defect in the same area within 14 days | +2 |

  - **How `risk_words` matches:**
    - only added or removed lines in **source** files count, never tests, docs or context lines;
    - each line is split into words, and identifiers are split further on camelCase, snake_case,
      kebab-case and digits (`dueDate` gives `due`, `date`; `calc_total` gives `calc`, `total`);
    - a word must equal a listed token, ignoring case (whole-token, not substring).
  - **Generic default `risk_words`:** calculate, calculation, score, scoring, price, money, amount,
    payment, balance. Date and rate words live only in the TDMS profile.
  - **Public contract changed (Q2, accepted):** the plan or PR has a `Public contract: changed` line,
    or the diff removes or renames a top-level `function`, `export` or `module.exports` line in a source
    file.
  - **Post-merge defect (Q3, accepted):**
    - it is an owner issue labeled `bug` or `defect` that names a merged loop PR (`#N`), opened within
      14 days of that merge;
    - the defect's areas come from that PR's files;
    - when the history cannot be read, the signal scores 0 and the Why line says "defect history
      unknown".
  - **Hard stops to Opus** (checked before the score, and no config can turn them off):
    - a `risk_paths` or sensitive path, or a sensitive goal word;
    - `Risk: high`;
    - a test is deleted, a `skip`/`only`/`xit`/`.todo` is added, or an assertion line is removed with
      none added in the same test file;
    - the third review round;
    - an authority doc changed with no source alongside.
  - Score 0 to `threshold - 1` (default 0-2) goes to Sonnet; `threshold` or more (default 3+) goes to
    Opus.
  - The owner's `Model:` wins, clamped to Sonnet or Opus for review (`haiku` is lifted; `fable` is never
    picked).
  - `model_line` ends with `Why: score N (<top 3 reasons>)` or `Why: hard stop (<reason>)`.
- `<src>/scripts/check_reply.py`:
  - a review Model line must carry `Why:`;
  - a Sonnet review must carry `Confidence: high|low` and `Unchecked:` (`none` is allowed).
- `<src>/scripts/triage.py`, `<src>/scripts/route.py`:
  - **Cascade:** `Confidence: low` on a Sonnet review creates one `review-recheck` item, tier Opus,
    limited to the `Unchecked:` text, at most once per head SHA.
  - **Cap:** `max_opus_per_day` (default 3) counts today's loop replies whose Model line says opus. The
    **day boundary is UTC midnight (08:00 Manila)**; there is no config key for it.
  - An Opus item over the cap is parked with `needs-leo` and the reason `Opus cap N/N reached (UTC
    day)`. It is never downgraded.
  - An owner `Model: opus` override is counted, but never parked.
- `<src>/scripts/outcomes.py`: new fixed fields:

  | Field | Value |
  |---|---|
  | `review_score` | int or null |
  | `why` | fixed reason codes only |
  | `hard_stop` | code or null |
  | `confidence` | `high`, `low` or null |
  | `rechecked` | bool |
  | `cap_parked` | bool |
  | `areas` | list |

  `FIELDS` and `ENUMS` are updated, so validation stays strict.
- `<src>/scripts/improve.py`: new patterns, each needing at least 3 issues:
  - Opus reviews that found nothing;
  - Sonnet reviews followed by a defect;
  - frequent low confidence;
  - frequent cap parks.

  New `--open-issue` posts one proposal issue (label `improve-proposal`, deduplicated by title). It never
  edits a file.
- `<src>/references/models.md`:
  - the v2 rules, the score table, the token matching, the cascade, and the cap with **"the day is the
    UTC day (resets 08:00 Manila)"**;
  - the review row and the Lead Deep text are replaced.
- `<src>/SKILL.md`: one line saying the Model line now ends with `Why:`.

**New tests and evals** (`<src>/evals/test_routing_v2.py`, `<src>/evals/routing_cases.json`)
- Scoring:
  - every row of the section 2 table and of the TDMS-shapes table below;
  - each hard stop on its own;
  - a threshold change through config;
  - a point set to 0.
- Tokens:
  - **zero hits** for `update`, `validate`, `generate`, `migrate`, `separate`, `operate`, `candidate`,
    with the TDMS profile words loaded;
  - hits for `dueDate`, `calc_total`, `isOverdue`, `computePrice`;
  - a hit in a test file or a context line does not count.
- Model override: `Model: haiku` on a review gives Sonnet.
- Cascade: one recheck per SHA.
- Cap:
  - the 4th Opus item parks with `needs-leo` and stays Opus;
  - a cap counted at 23:59 UTC is cleared at 00:00 UTC.
- `check_reply` rejects a Sonnet verdict without `Confidence:`.
- `outcomes.validate` rejects a free-text `why`.
- `improve --open-issue` dry run: one POST, no file writes.

**TDMS shapes** (the 4 recent PR shapes, rebuilt as synthetic file patterns and diff lines, with no TDMS
content). Settings: TDMS example profile, `feature_roots: ["src/*"]`, threshold 3. "Today" is the
current `pick_model.py`.

| Shape | Files | Sample source lines | Points | v2 review | Today |
|---|---|---|---|---|---|
| T1 trip form validation | `src/ui/trip-form.js`, `src/ui/trip-form.html`, `src/services/trips.js`, 3 tests, 2 docs; about 260 lines | `+function validateTrip(trip) {`, `+updateStatus(id, "SUBMITTED")` | 2 areas +1, lines +1; tokens validate, update: 0 hits | **Sonnet**. Why: score 2 (2 feature areas, diff 150-400) | Opus (8 files). With substring matching, `validate` and `update` would hit `date` (+3) |
| T2 overdue reminder | `src/services/reminders.js`, `src/rules/dates.js`, 4 tests, 2 docs; about 190 lines | `+const overdue = isOverdue(trip.dueDate, now)` | risk words overdue, due, date +3, 2 areas +1, lines +1 | **Opus**. Why: score 5 (date logic: overdue, due, date; 2 areas; diff 150-400) | Opus (8 files) |
| T3 Props adapter | `src/platform/props.js`, `src/services/settings.js`, 4 tests, 2 docs | `+PropertiesService.getScriptProperties()` | hard stop | **Opus**. Why: hard stop (risk path src/platform/props.js) | Opus (8 files), with `risk_paths` empty |
| T4 status labels on list screen | `src/ui/trip-list.js`, `src/ui/trip-list.html`, `src/services/trips.js`, 4 tests, 1 doc; about 180 lines | `+// migrate old status names`, `+const label = separateWords(generateLabel(status))` | 2 areas +1, lines +1; tokens migrate, separate, generate: 0 hits | **Sonnet**. Why: score 2 (2 feature areas, diff 150-400) | Opus (9 files). With substring matching, the three words would hit `rate` (+3) |

Opus comes only from real signals (date logic in T2, the Props-adapter hard stop in T3), never from file
counts or substrings.

**Acceptance**
- All suites pass.
- `route.py --step review` on fixtures prints a `Why:` line for every case.
- With no new keys, a docs-only PR still reviews on Sonnet and a sensitive PR on Opus.

**Risk**: high. It changes who reviews, and adds reply lines that Lead tasks must write. `check_reply.py`
names the missing line exactly.

### PR-C Process fit (S4, G1, G2, G3, G4, G5, G7)

**Files to change**
- `<src>/scripts/check_plan.py`:
  - `plan_sections` takes a list or `"lite"`. `"lite"` means Goal, Tasks, Tests, Merge plan.
  - Topic checks run only for the six known heavy names.
  - These always stay: the Merge plan with its `Risk:`, `CI required:` and `Files in scope:` lines, a
    model tier, and `AWAITING APPROVAL`.
  - `plan_dir`: when set, the plan path must be under it.
  - G1: when `commit_ref_pattern` is set, the plan must match it.
- `<src>/scripts/loop_gh.py` merge gate:
  - G3: `branch_prefix` may be a list.
  - G1: when `commit_ref_pattern` is set, every PR commit message must match it (from
    `pulls/N/commits`). Otherwise exit 5, naming the commits that fail.
  - G4, `merge_phrase`: when set, the gate needs an **owner** comment that is exactly `OK i-merge #<PR
    number>`, on the PR or on the issue, newer than the head commit.
    - Without it, the gate exits with a **new code 10** and the message "waiting for the owner's merge
      phrase: comment `OK i-merge #N` on the PR".
    - This message is different from the exit-8 high-risk message.
    - `--owner-merge-quote` does not clear exit 10.
    - The docstring exit table, `autopilot.md`, `lead.md` and `runbook.md` get one exit-10 row each.
  - `deploy: "off"`: the release step is skipped. The report line becomes `deployed: no (deploy: off,
    manual step for the owner)`, and `check_reply.py` accepts it.
- `<src>/scripts/readiness.py`:
  - G3: the open-PR row uses the configured prefixes.
  - G2: when the protection read gives a 403 with the "upgrade" message, or a 404, the row says plainly:
    "No branch protection (private repo on a free plan). `loop_gh.py merge` is the only gate. Do not
    merge from the GitHub page."
  - A "Merge gate" row shows the merge phrase when one is set.
  - With `deploy: "off"`, the Pages row says NOT REQUIRED.
- `<src>/references/autopilot.md`, `<src>/references/task-template.md`: the lite plan, `plan_dir`, and
  the commit ref line.
- New `<src>/references/smoke-test.md`, in 6 parts:
  1. The 3 steps from `events.md`: a workflow dry run; one real fire per role; one tiny docs-only issue
     with `Risk: high` and no deploy. `events.md` then links here.
  2. Negative test: a stranger's comment, and a lowercase "approved" from the owner, both fire nothing.
  3. Model check: 3 test issues (easy, 3 features, sensitive). Compare their Model and Why lines with
     section 2.
  4. Cost log (G5): usage before and after each run, as a table of run, role, model, before, after,
     delta.
  5. G7 notes:
     - the TDMS install and secrets come later;
     - the API trigger is a research preview;
     - a finished check is not an event (reply `CONTINUE:` or wait for the backup run).
  6. Pass criteria: every step's expected result is ticked; part 2 fires nothing; 3 of 3 Model lines
     match the table; every cost row is filled.

**New tests** (`<src>/evals/test_process_fit.py`)
- Plans:
  - a lite plan passes;
  - a lite plan without a Merge plan fails;
  - the heavy default is unchanged;
  - a plan outside `plan_dir` fails.
- A missing commit ref fails and names the commit.
- `feat/` and `docs/` branches pass; `fix/` fails.
- **Merge phrase:**
  - missing → exit 10, with the exit-10 message;
  - a high-risk PR with no phrase → exit 10 first. Once the phrase is there, the high-risk owner-merge
    rule still applies as today (exit 8, with its own message);
  - from a stranger, or older than the head, or with the wrong PR number → ignored;
  - correct → passes;
  - `--owner-merge-quote` alone does not clear exit 10.
- `deploy: off`: the report line passes.
- Readiness:
  - a free-plan 403 gives the plain wording;
  - the open-PR row uses the configured prefixes.

**Acceptance**
- All suites pass.
- `readiness.py --markdown` shows the G2 wording.
- A TDMS-style lite plan fixture passes.
- smoke-test.md has all 6 parts.

**Risk**: high. The gate gets two new stops, and neither one removes an existing stop.

## 2. Score table (generic defaults, no profile, threshold 3)

Feature areas count source files only. No row has a `risk_words` hit: with the generic defaults (for
example calculate, price, payment), these shapes contain none. "Today" is the current `pick_model.py`.

| Shape | Points | Score | v2 review | Today |
|---|---|---|---|---|
| Docs-only small (README, 30 lines) | none (no source) | 0 | Sonnet. Why: score 0 (documentation only) | Sonnet |
| 1 area, 3 source + tests, about 200 lines | lines +1 | 1 | Sonnet. Why: score 1 (diff 150-400) | Sonnet |
| 9 source in 1 area + tests, about 450 lines | files 8+ +3, lines >400 +2 | 5 | Opus. Why: score 5 (9 source files, diff >400) | Opus |
| 3 areas, 3 source + tests, about 120 lines | areas 3+ +3 | 3 | Opus. Why: score 3 (3 feature areas) | Sonnet |
| 1 risk_path file + 1 other | hard stop | n/a | Opus. Why: hard stop (risk path `<file>`) | Opus, only if the built-in regex matches the name |
| Authority doc alone (`CLAUDE.md`, or a configured one) | authority +2, plus a hard stop (no code alongside) | 2 | Opus. Why: hard stop (authority doc changed with no code) | Sonnet |
| Code with no tests: 1 area, 2 source, about 100 lines | no tests +2 | 2 | Sonnet. Why: score 2 (no test change) | Sonnet |
| (variant) same, with 4 source files | files +1, no tests +2 | 3 | Opus. Why: score 3 (no test change, 4 source files) | Sonnet |
| (S3 check) 5 source + 4 tests + 1 doc, 1 area, about 250 lines | lines +1 | 1 | Sonnet. Why: score 1 (diff 150-400) | **Opus** (10 files) |

Notes on this table:
- Without `risk_paths`, the risk-path row only works for names the built-in regex knows; that is why
  TDMS needs its profile.
- Without `authority_docs`, only `CLAUDE.md` and `AGENTS.md` count as authority docs.
- The 4 real TDMS shapes, with their profile, are in the PR-B table.

## 3. Backward compatibility

A repo with no new keys keeps running. The defaults reproduce today's config values, and no new key is
required. These behavior changes reach existing users even with no new keys:

1. **A0**: none. It adds a folder that is not active.
2. **PR-A**:
   - `large` counts source files only, so big diffs of tests, docs or lockfiles stop going to Opus (plan,
     build and review);
   - `CLAUDE.md` and `AGENTS.md` are authority docs (no effect on the merge gate);
   - the top-level `github-loop/` counts as the skill path (high risk);
   - a bad value for a documented key now fails with a clear message, where before it was silently
     accepted;
   - unknown-key errors suggest the right key;
   - `Files in scope:` matching is unchanged.
3. **PR-B**: review routing becomes the score.
   - Some reviews move **up**: 3+ areas, a whole-token generic risk word in the source lines (for
     example `calculate`, `price`), no tests with 4+ source files, a deleted or skipped test, an
     authority doc alone.
   - Some move **down**: many test or doc files.
   - Date and rate words do **not** score without a profile.
4. **PR-B**: the owner's `Model: haiku` on a review is lifted to Sonnet.
5. **PR-B**: review Model lines need `Why:`, and Sonnet verdicts need `Confidence:` and `Unchecked:`.
   `check_reply.py` rejects old-shape verdicts and names exactly what is missing.
6. **PR-B**: a default cap of 3 Opus items per UTC day. The 4th parks with `needs-leo`, where before it
   ran.
7. **PR-B**: a low-confidence Sonnet review adds one Opus recheck, which counts toward the cap.
8. **PR-C**:
   - readiness shows the plain "no branch protection" wording;
   - the open-PR row reads the config prefix (same output for `claude/`);
   - exit code 10 exists, but it is only produced when `merge_phrase` is set.
9. **Unchanged without the new keys:** plan sections (the six), plan location, commit messages, the
   merge phrase (none), deploy (auto), the `claude/` prefix, and the meaning of exit 8.

## 4. Open questions

All three are decided by Leo:
- **Q1:** top-level `github-loop/`, restored first in PR-A0. This is the needs-leo OK for that folder.
- **Q2:** public contract, detected as written in PR-B (accepted).
- **Q3:** post-merge defect, detected as written in PR-B (accepted).

No open questions remain. The next step waits for "OK A0".

## 5. `.github/` and templates

- No PR touches `.github/` or `references/templates/`. TDMS values ship only as
  `references/profiles/tdms.example.json`.
- No PR edits `.claude/skills/` or `trip-monitoring/`.
- Every PR is still **Risk: high**, because it changes or copies the loop's own safety scripts. Leo
  reviews and merges each one; the loop does not.

AWAITING APPROVAL
