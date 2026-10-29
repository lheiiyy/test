# github-loop changelog

Each adopted change is its own PR with one line here. After its PR is merged, tag the merge commit `github-loop-<date>` (for example `github-loop-2026-10-29`), so the runbook can roll back to it.

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
