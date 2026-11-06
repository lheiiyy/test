# Model routing: the right model for each step

Use the cheapest model that does the step reliably. Move up on **risk**, not on effort, and never skimp on review. The choice comes from `scripts/pick_model.py`, which reads facts (files, goal, attempt, round, the plan's declared risk) and not a feeling, so two runs choose alike. `scripts/route.py` runs it for every thinking step and adds the experts and gates; call `pick_model.py` directly only for merge, verify and report.

```
python3 scripts/pick_model.py --step <plan|revise|build|fix|review|merge|verify|report> \
    [--git-range <base>...<head> | --paths <files>] [--text <issue body file>] \
    [--tasks N] [--attempt N] [--round N] [--declared-risk high] --session <model of this task>
```

`--session` is the model this task runs on: `haiku`, `sonnet` or `opus` (a full ID such as `claude-sonnet-5-5` also works; if unsure, `sonnet`). The reply gives `tier`, `action` (`run inline` or `delegate`), the reason, and the signals it saw. Exit 2 means bad input.

## The rules

| Step | Default | Moves to opus when | Cheaper when |
|---|---|---|---|
| `merge`, `verify` | haiku | never | always: a scripted command and its exit code |
| `report` | sonnet | never | never: it states results as facts |
| `plan`, `revise` | sonnet | the goal names sensitive things (login, permissions, schema, payments, credentials), the goal is architecture-heavy (new system, rewrite), 5 or more tasks, or this is the second revision | never: sonnet is the floor |
| `review` | sonnet | a hard stop, or a score at or above `threshold` (default 3): see **Review routing v2** below | never: sonnet is the floor, even for documentation |
| `build` | sonnet | sensitive files **and** a big change | haiku when only `.md`, `.txt` or `.rst` files change |
| `fix` | sonnet | sensitive files, the third review round, or the **second attempt** at the same failure | haiku for documentation only |

Sensitive files: names containing auth, permission, role, acl, secret, token, credential, password, pin, schema, migration, `.sql`, payment, billing, payroll, security, deploy, `.env`; also `.github/`, `appsscript.json`, `.clasp*` and the skill folder itself (`.claude/skills/`, or its source in a top-level `github-loop/`), plus any `risk_paths` glob in the settings. These rules live in `scripts/rules.py`, shared with route.py and the merge gate. Documentation-only changes are never sensitive, except under `.github/` or the skill folder. A plan's `Risk: high` counts as sensitive too.

A big change counts **source files** only: tests, documentation, lockfiles and generated files do not count (the file kinds in `references/setup.md`).

## Review routing v2

A review goes to opus for a **hard stop** or a **score**, and to sonnet otherwise. `route.py --step review --git-range origin/main...<head> --history history.json` reads the diff from the same range and the history from `scripts/review_history.py`; the Model line it prints ends with the reason.

**Hard stops** (checked first; no setting can turn them off): a sensitive or `risk_paths` file; risk words in the request's goal; `Risk: high`; a test deleted, a `skip`/`only`/`xit`/`.todo` added, or an assertion removed from a test file with none added; the third review round; an authority document (`CLAUDE.md`, `AGENTS.md`, `authority_docs`) changed with no source alongside. `Why: hard stop (<reason>)`.

**Score** (each top value can be changed with `points`, 0-5; the lower step of a graded row is 1, or 0 when its top is 0):

| Signal | Points |
|---|---|
| Feature areas (`feature_roots`, else each file's folder) | 1 area = 0, 2 = +1, 3 or more = +3 |
| Source files | 4-7 = +1, 8 or more = +3 |
| Diff lines (added + removed, source and tests) | 150-400 = +1, more than 400 = +2 |
| A risk word in changed source lines | +3 |
| Public contract changed | +2 |
| An authority document changed | +2 |
| Source changed with no test change | +2 |
| A CHANGES REQUESTED verdict earlier on this issue | +1 |
| A post-merge defect in the same area within 14 days | +2 |

- Below `threshold` (default 3, settable 2-10) is sonnet; at or above it is opus. `Why: score N (<top 3 reasons>)`.
- **Risk words** count only in added or removed lines of **source** files (never tests, docs or context lines). Each line is split into words, and identifiers are split further on camelCase, snake_case, kebab-case and digits (`dueDate` gives due, date; `calc_total` gives calc, total). A word counts only when it equals a listed word: `update` never matches `date`, and `separate` never matches `rate`. The defaults are calculate, calculation, score, scoring, price, money, amount, payment, balance; `risk_words` adds a project's own (dates and rates belong in a project's settings).
- **Public contract changed:** the plan or request says `Public contract: changed`, or the diff removes or renames a top-level `function`, `export` or `module.exports` line (or a top-level `def`) in a source file.
- **Post-merge defect:** an owner issue labeled `bug` or `defect` that names a merged loop PR (`#N`), opened within 14 days of that merge; its areas come from that PR's files. When the history cannot be read, the signal scores 0 and the Why line says `defect history unknown`.
- **The owner's `Model:`** still wins, clamped to sonnet or opus for a review (`haiku` is lifted; `fable` is never picked). `Why: owner's Model line (...)`.

**A sonnet verdict** carries `Confidence: high|low` and `Unchecked: <what it could not check, or none>`. A low-confidence **approval** is not final: the Lead gets one `review-recheck` work entry (opus, limited to the Unchecked items) for that head, posted as a verdict with `recheck=yes`, and the merge waits for it. A head gets at most one recheck. A low-confidence CHANGES REQUESTED goes to the fix as before, and the next head is reviewed anyway.

**Opus cap** (off by default): set `max_opus_per_window` (0-50) to allow at most that many opus steps in the last `opus_window_hours` (default 5, settable 1-24). Triage then counts the loop replies whose Model line names opus in that rolling window, so a slot frees up at most 5 hours after an opus step. An opus step over the cap is put on hold with `loop_gh.py hold` (needs-leo, reason `Opus cap N/N reached (last 5 hours)`): it keeps its labels and runs again by itself when a slot frees up, and it is **never** run on a weaker model instead. The owner's `Model: opus` is counted but never held. A recheck counts toward the cap. `route.py --opus-left <the entry's opus_left>` applies the same rule when the real diff turns a step into opus. Without `max_opus_per_window`, nothing is counted and nothing is held.

**A hard stop beats the owner's lower Model line.** `Model: sonnet` or `Model: haiku` on a request does not lower a review that has a hard stop: that review is opus. `Model: opus` always raises.

**Bugs from a merged PR** (the loop does this, not the owner): when a request fixes something a merged loop PR broke, the Lead runs `loop_gh.py defect --pr <N>` once. It posts `Galing sa #N`, labels the issue `bug`, and from then on the post-merge defect signal can score that area.

Only the goal counts for risk words in a request (the Objective section), because the rest of the template holds boilerplate such as "schema changes" and "credentials".

## Who decides

1. **The owner** beats everything: a `Model: opus|sonnet|haiku` line in the request, or the Model field of the issue form (Auto means no override). It applies to plan, revise, build, fix and review, never to merge or verify.
2. **The script** decides the rest. The plan's `Model plan:` line is the Lead's estimate from the request; the run asks again with the real files.
3. A run may go **one tier up** from the script's answer with its reason written in the reply. It never goes down, and it never uses `fable`, the top tier, which only the owner asks for.

## Using the answer

- **`run inline`:** do the step on this task's model. If the tier is lower than the task's, still run inline: a subagent restarts cold and costs more than it saves. The task's own model sets the cost.
- **`delegate`:** the tier is above this task's model. Hand the **judgment** to a subagent (Agent tool, `model` set to the tier) and keep the scripts, the checks and the posting in this session. Give the subagent only what it needs:

  > You are doing one step of the github-loop for `<o>/<r>`, issue #N: `<step>`. Work in `<dir>` on branch `<branch>`. Read only `<files>`. Deliverable: write `<file>` as `<format from lead.md or autopilot.md>`. Do not post to GitHub, change labels, merge or push. Reply with the file path and the test result line.

  Then verify its work yourself: for a review, `git rev-parse` must equal the head Code named, and the tests must have run fresh; run `check_reply.py` or `check_plan.py`; post with the `loop_gh.py` command.
- **No Agent tool in this session:** run the step inline and use the `inline` model line, which names what was wanted. For a sensitive review, the owner can say "review the PR" in a chat on Opus.
- **Say what ran:** put exactly one line `Model: <haiku|sonnet|opus>` in a plan, phase 2 result, verdict and summary, naming the model that produced the judgment. `pick_model.py` prints the true line in `model_line`: `Model: opus (via subagent)` when a subagent did it, or `Model: sonnet (wanted opus; ran inline, no subagent)` when the step wanted more than this task has. `check_reply.py` rejects a missing or doubled line, and a "wanted" tier that does not say how the gap was handled. With `--session <this task's model>` on the posting command, it also rejects a line that names another model without `via subagent`, so a Sonnet task cannot claim an Opus review. Never claim a model that did not run.

## Recommended task setup

Put both scheduled tasks on **Sonnet**: triage costs almost nothing and Sonnet is the workhorse for builds and reviews. Opus is then used only where the rules above say so. A task whose own model is Opus pays Opus for every step, even when the script says sonnet (`run inline` never goes down), so routing saves nothing there. The skill cannot change a task's own model: ask Claude in chat to change it, and write the task's model into its prompt (`--session sonnet`) so the Model line is checked.

**Is it applied?** Check three things: the task's model in its settings, `--session` in the task prompt, and the `Model:` lines on recent issues (`scripts/outcomes.py` collects them; `scripts/improve.py` proposes a fix when steps keep wanting a stronger tier).

## Two Lead tasks (optional): how sensitive work reaches Opus

A scheduled run showed no subagent use, so a Sonnet Lead cannot reliably hand a review to Opus. Triage routes by tier instead:

| Task | Triage flags | Takes |
|---|---|---|
| Lead (Sonnet, started by events) | `--role lead --max-tier sonnet` | Work whose tier is sonnet or lower. Opus-tier work waits in `deferred`. |
| Lead Deep (Opus, scheduled every 2 hours; events do not start it) | `--role lead --min-tier opus` | Only opus-tier work: a review hard stop or a score at or above `threshold`, a `review-recheck`, sensitive files or goal words in a plan, an architecture-heavy goal, the second revision, or Leo's `Model: opus`. Over the Opus cap (when one is set), the work is held (needs-leo), not run. |

- Each work entry carries `tier` and `tier_reason`, an estimate from the request and the PR's file list (one extra call, review and fix only). The step still runs `pick_model.py` with the real diff, and that answer wins.
- **No deadlock:** after `--defer-minutes` (default 120) the normal Lead takes deferred work anyway. The entry then has a `tier_note`, and the Model line must say `wanted opus; ran inline`. If Lead Deep does not exist, leave `--max-tier` off.
- The owner's `Model:` override feeds the same estimate, so `Model: opus` sends a request to Lead Deep and `Model: sonnet` keeps it on the normal Lead.

## Known limits

- Whether a scheduled cloud run can start subagents is **UNVERIFIED**, and the one live run did not use any. Without them, the fallback above keeps the loop working on the task's model, and the Model line says so.
- The script sees file names, the goal and, for a review, the diff's changed lines; it does not see hidden complexity. That is why a run may go one tier up, why review never drops below sonnet, and why a sonnet review says what it could not check.
- Triage's tier for a review is a floor from the file list (no diff); the review step's own route.py answer, with the diff, wins.
