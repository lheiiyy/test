# github-loop changelog

Each adopted change is its own PR with one line here. After its PR is merged, tag the merge commit `github-loop-<date>` (for example `github-loop-2026-10-29`), so the runbook can roll back to it.

## 2026-10-30 (last): classic mode removed

- Removed: the classic chat-to-Code flow (an issue without Phase 1 and Phase 2 headings, one build, no plan approval, no scripted merge, a turn cap of 4). It sat outside the plan-approval and merge-gate rules and no live task used it. Gone with it: its reference file, the `reply` command of `loop_gh.py`, the `to-chat` label, the `--max-turn` option of `triage.py` and `loop_guard.py`, and the `status` reply type and `from=chat` header.
- Changed: a `to-code` label on an issue without the two headings used to start a classic build. Now triage lists it under `needs_leo` and Code parks it once with a note on how to file the request (the Autopilot issue form); the parked issue is then left alone. That entry has no `phase`, so its `park` takes no `--phase`.
- `loop_guard.decide()` and `triage.triage()` no longer take a `max_turn` argument.
- No change to the merge gate, the approval rules or the risk rules. The two live scheduled tasks pass only `--repo`, `--owner` and `--role` to triage, so they need no edit.

## 2026-10-30 (later): install check, web-app support, setup rewrite

- `scripts/selfcheck.py`: a static check that every script, reference and `loop_gh.py` command the docs name exists in this copy. SKILL.md tells a session to run it first, so an account copy saved from SKILL.md alone (or an old `scripts/` folder under a new SKILL.md) is caught before a run, not during one.
- Web apps: `references/web-apps.md` (the path from chat planning to loop slices, what runs where, how to make a plan loop-ready), the `appsscript` expert note (mock transport, repository layer, manual deploy steps) in the registry, and design and proof rules in `experts/frontend.md` (design tokens, and screenshots at 1280, 768 and 375 px that the reviewer must open). `lead.md` and `autopilot.md` follow: the screenshots folder is part of `Files in scope:`, and an Apps Script deploy is a manual step with listed steps.
- The starter `CLAUDE.md` gains a Design section and the Apps Script test rule.
- `references/templates/tests.yml` is the CI template, and `.github/workflows/tests.yml` runs the loop's tests on every pull request.
- `setup.md` is rewritten as one ordered path with a "You should see" check after each step, a zip install step and a CI step. Removed: the GitHub App trigger route and the `claude-code-action` fallback (both untested; the event-trigger work replaces them), and the `to-chat` label row (no tool creates that label).
- No change to the merge gate, the approval rules or the risk rules. Classic mode is removed in a separate PR.

## 2026-10-30: portable setup for other projects

- `scripts/init_repo.py`: one command sets up a new repository. It writes `.github/github-loop.json`, the Autopilot issue form and a starter `CLAUDE.md` (never over an existing file without `--force`), installs the skill with `--install-skill`, creates the labels with `--create-labels`, and prints the Code, Lead and Lead Deep task prompts with `--prompts`. `--dry-run` writes nothing.
- `references/templates/`: the issue form, the Code and Lead task prompts and the starter `CLAUDE.md`, with `{{placeholders}}`. They are the one source for the scheduled-task prompts (taken from the prompts that ran live in `lheiiyy/test`, with the owner, repo, language and model filled in). The setup guide points to them instead of keeping a second copy.
- `loop_gh.py`: `--file` and `--plan-file` also work when the command runs from the skill folder (a relative path that is missing is tried from the repo root), and a missing plan file is a clear problem, not a traceback.
- `lead.md`: in a chat, look for existing material (folders, docs, PRs, issues) before planning anything new, and plan the next slice on a project that already exists.
- Docs: no owner, repo or project names left in SKILL.md, setup.md or the script docstrings; setup.md starts with a one-command quick start.

## 2026-10-29 (later): D4 changed to a

- Plans and plan replies carry `Files in scope: <folders/ and files>`; `*` and similar are refused, and the scope must cover the plan file. A `CONTINUE:` still keeps the approval, but `merge` exits 9 when a changed file is outside the scope (or the plan declares none), so the owner decides: `REVISE:`, a Merge tap, or `MERGE ...` in a chat session (which covers exit 8 and 9 together).
- outcomes.py has an `out_of_scope` park category, and improve.py advises on it.

## 2026-10-29: rework from the handoff

- Approval rules (owner decisions D4 b, D5 a, D6 b): a `REVISE:` after the latest plan cancels every approval until a revised plan is posted; `CONTINUE:` keeps it; loose `APPROVED ...` wording still counts.
- Relayed approval (D10 b): only the owner's own words starting with `APPROVED`; the final summary repeats the quote.
- Merge gate: never a fork PR; the verdict and the latest Code result must name this PR; the plan's `CI required: yes` requires checks; the whole file list must be read; high-risk changes (D3 a, D8 list in `scripts/rules.py`) exit 8 and are merged by the owner, by a Merge tap or the owner's `MERGE ...` words in a chat session (recorded in the merge commit message).
- `finish` needs a merged PR or `No PR: yes` (D7 a); every posting command is safe to repeat (no duplicate comments).
- Reliability: every list is read to its last page; 429 and 5xx are retried; a missing `gh` is a failure, never an idle queue.
- Plans and plan replies carry `Risk:` and `CI required:` lines; `post-plan` runs `check_plan.py` on the plan file; links count as words.
- Model line: `--session` makes it name the model the task really runs on.
- Portability: `.github/github-loop.json` (owner, name, language, base, branch prefix, associations); the owner defaults to the repo's owner; `scripts/package.py` builds an installable zip.
- Routing: `scripts/route.py` with `references/experts/registry.json` and nine short expert notes; routing only adds gates.
- Outcomes: `scripts/outcomes.py` (fixed fields from the GitHub record) and `scripts/improve.py` (recommend-only, off switch).
- Docs: SKILL.md slimmed; classic mode and a recovery runbook moved to their own references.
