---
name: github-loop
description: Coordinate Leo (Product Owner), Claude Cowork (Technical Lead) and Claude Code (Engineer) through GitHub Issues and pull requests, with no copy-paste relay. Autopilot mode runs plan with readiness check, one approval, build, independent review, fix, scripted merge, verify, deploy when authorized, and report. Use whenever Leo says "send to Code", "check the loop", "set up the loop", "autopilot", "plan then build" or "review the PR", or replies APPROVED, REVISE or CONTINUE on an issue. Also use it when an issue labeled to-code, awaiting-approval, to-review, reviewed or to-chat is in front of you, when a scheduled task fires for the loop, or when drafting an issue for Claude Code, even if "loop" is never said.
---

# github-loop

GitHub is the shared source of truth. Issues carry requests and hand-offs, pull requests carry code, and labels say whose turn it is. Every agent posts from Leo's account, so the first line of each agent comment is a header that names the writer.

## Team and authority

| Who | Owns | Acts through |
|---|---|---|
| **Leo**, Product Owner | Goals, requirements, the one plan approval, scope changes, material risks, production releases (release policy) | The request (issue form), then `APPROVED`, `REVISE: <notes>` or `CONTINUE: <answer>` comments |
| **Lead**, Claude Cowork (Technical Lead) | Inspection, readiness audit, the plan, independent review, verification, escalation | A chat with Leo, or the hourly Lead scheduled task (`--role lead`). Steps: `references/lead.md` |
| **Code**, Claude Code (Engineer) | Branches, code, tests, PRs, fixes, the scripted merge, post-merge checks, authorized deploys, the report | The hourly Code scheduled task (`--role code`). Steps: `references/autopilot.md` |
| **GitHub** | The record: issues, PRs, commits, checks, verdicts | The `gh api` REST calls in `scripts/` |

- Approving the plan authorizes the routine work in its scope, including the merge.
- It never overrides platform permissions, repository rules or security controls.
- Self-review is not review: the Lead reviews from a different session than the one that built.
- In this loop, plan approval replaces the "Leo approves merge" gate in the Ship row of web-app-project-planning. Production deploys still follow the plan's release policy.

## Lifecycle (autopilot mode)

INSPECT → PLAN + READINESS (Lead) → APPROVE ONCE (Leo) → IMPLEMENT + TEST (Code) → REVIEW (Lead) → FIX (Code) → MERGE through the scripted gate (Code) → VERIFY (Code) → DEPLOY WHEN AUTHORIZED (Code) → REPORT (Code; the issue closes).

An issue is in autopilot mode when its body has Phase 1 and Phase 2 headings (`references/task-template.md`, or the Autopilot issue form). Any other issue is in **classic mode**: chat writes a task with Goal and Acceptance criteria, Code replies, and the turn cap is 4 (see the end of this file).

**What Leo does per feature:** files the request, and approves the plan (`APPROVED` on the issue, or in a chat with the Lead). If a platform rule refuses the merge, he also taps Merge once and replies `CONTINUE: merged`. Releases follow the release policy.

## Labels: whose turn it is

| Label | Next actor |
|---|---|
| `to-code` | Lead plans (autopilot); Code works (classic). The only label that starts work, and Leo or the issue form adds it. |
| `awaiting-approval` | Leo: `APPROVED` or `REVISE: <notes>` |
| `code-working` | A run of either role holds the claim |
| `to-review` | Lead reviews the exact head that Code named |
| `reviewed` | Code merges (verdict approved) or fixes (changes requested) |
| `needs-leo` | Leo: `CONTINUE: <answer>` or `REVISE: <notes>`. Classic mode stops here. |
| `to-chat` | Classic only: the chat planner |
| `done` | Finished and closed |

## Message headers

The first line of every agent comment:

```
<!-- loop:v1 from=code|lead|chat type=TYPE [phase=1|2] [pr=N head=SHA] [verdict=approved|changes] turn=N -->
```

| Type | From | Rule |
|---|---|---|
| `plan` | lead | phase=1 |
| `result` | code | phase=2 adds `pr` and the exact `head` |
| `verdict` | lead | Names `pr`, `head` and `verdict`. Ends with `Reviewed head <sha>`, then `VERDICT: APPROVED` or `VERDICT: CHANGES REQUESTED`. |
| `summary` | code | phase=2. Carries five report lines: Implemented and tested / Reviewed / Merged / Deployed / Blocked or unverified. |
| `question` | either | Used by `park` |
| `approval` | lead | Relays Leo's approval from a chat, quoting him. Never posted from a scheduled run. |
| `task`, `result`, `status` | chat, code | Classic mode |

## Every run, both roles

Run the scripts from the skill folder (`.claude/skills/github-loop/` in a repo) after `export PYTHONDONTWRITEBYTECODE=1`. Use REST (`gh api`) only, because GraphQL and `gh pr create` fail in cloud sessions.

1. **Triage:** `python scripts/triage.py --repo <o>/<r> --owner <owner> --role <code|lead>`.
   - `No new work.` → say exactly that and stop.
   - Exit code 2 or `TRIAGE FAILED` → report the error and stop. A failure is never "No new work."
2. **Park (Code role only).** For each `needs_leo` and `stale` entry, run `python scripts/loop_gh.py park --repo <o>/<r> --issue <N> --turn <next_turn> --reason "<reason>"`. Add `--phase <phase>` only for autopilot entries (`mode: autopilot`). For a stale entry, the reason is "the previous run stopped after claiming; reply CONTINUE: to retry (re-apply to-code in classic mode)".
3. **One issue per run.** Take the first `work` entry. Lead work follows `references/lead.md`, Code work follows `references/autopilot.md`, and classic work follows "Classic mode" below.

## The merge gate (`loop_gh.py merge`)

The script merges only when all of these hold:
- The owner approved the latest plan.
- The latest Lead verdict approves the PR's exact head.
- No check run or commit status on that head is failing or pending. When the plan requires CI, at least one check must exist.
- The PR is open, not a draft, on a `claude/` branch, against `main`, and cleanly mergeable.

The head SHA is pinned. Anything else returns an exit code, and the run parks with that reason. Never work around a refusal, whether it comes from the script, GitHub or the platform.

## Guards (why each exists)

- **Only `to-code` starts work, and agents never add it.** Otherwise the loop could trigger itself.
- **Keywords count only when the owner writes them**, at the very start of a comment, in capitals, and after the latest agent reply. Agent comments start with a header, so they never read as keywords.
- **A relayed approval** comes only from a chat Lead, quoting Leo's own words.
- **Caps.** Autopilot: 20 agent replies, 3 plan revisions, 4 change requests. Classic: 4 turns. Leo can lift a classic cap with an owner `<!-- loop:v1 from=human type=reset turn=0 -->` comment.
- **Stale claims are surfaced, not hidden:** after 90 minutes, or 180 for an approved build.
- **The repo is public.** Only the owner's issues and comments count, and nothing confidential is ever committed.
- **One issue per run, one reply per run.**

## Token rules

These are the caveman rules, written inline because scheduled runs load no plugins.
- Triage first. Read only the files the plan or the issue names, and never re-read the whole codebase.
- From round 2 on, the review reads only `git diff <since>..<head>` and the open findings.
- Hand-offs carry facts, paths, commands and results, with no filler. Keep code and errors verbatim.
- Record each decision once, in the plan file or on the issue, and reuse it.
- Batch the checks. Do not retry the same failing approach without new evidence.
- Never drop a security check or a test to save tokens.

## Skills used when installed, with fallbacks

| Need | Skill | Fallback |
|---|---|---|
| Project-level planning | web-app-project-planning | The plan sections in `references/lead.md` |
| Build plan, TDD, debugging | superpowers writing-plans, test-driven-development, systematic-debugging | Failing test first; root cause before any fix |
| Review | superpowers requesting-code-review, receiving-code-review | The review checklist in `references/lead.md` |
| Proof of done | superpowers verification-before-completion | Run the command and read its output |
| Token use | caveman | The token rules above |

Scheduled tasks start with no plugins (`enabled_plugins` is empty), so the fallbacks are the default there. Never claim that a skill was used unless it was loaded.

## Classic mode (chat ↔ Code)

- **Planner (chat):** write the issue with the header `from=chat type=task turn=1` and the sections `## Goal`, `## Context` (paths, no pasted code), `## Acceptance criteria` and `## Constraints`. Create it with `to-code` if a GitHub write works; otherwise give Leo the text and tell him to add `to-code`. "Check the loop" means summarising the `to-chat` and `awaiting-approval` issues in two lines each.
- **Code:** run `claim`, do the work on a `claude/` branch, open a PR, then send `reply` with `--add to-chat`, `needs-leo` or `done`, in 150 words or fewer.

## Setup and failures

Setup steps are in `references/setup.md`: labels, issue form, the two scheduled tasks, CI, release policy and the readiness check. If a step cannot finish, park with the step and the evidence. A run that "succeeded" only means the session ended, so check the labels and replies, not the run status.
