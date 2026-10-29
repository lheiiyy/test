---
name: github-loop
description: Hand coding tasks between Claude chat (planner) and Claude Code (executor) through GitHub Issues, with no manual copy-paste relay. Use this whenever Leo says "send to Code", "hand this to Claude Code", "check the loop", "set up the loop for repo X", or when an issue labeled to-code or to-chat is in front of you, or when a scheduled task fires on a GitHub issue event. Also use it when drafting an issue that Claude Code should pick up, even if the word "loop" is never said.
---

# github-loop

Two Claudes cannot talk to each other directly, but both can read and write GitHub Issues. This skill makes an issue the shared message thread, and labels the signal for whose turn it is. Claude Code can wake itself on a GitHub event. Claude chat cannot, so the return trip happens when Leo opens a chat and says "check the loop" (or a daily scheduled chat task does it). Be honest about that in every setup conversation: the automation ends at Claude Code's reply.

## Decide your role first

- **Repo checkout present, or woken by a GitHub event** → you are the **executor** (Code side). Follow "Executor procedure".
- **Running in claude.ai chat** → you are the **planner**. Follow "Planner procedure".
- **Asked to set up the loop** → read `references/setup.md` and walk Leo through it one step at a time. He works from a tablet and a browser, so every step must be doable in the GitHub web UI and claude.ai.

## Labels (one issue = one task)

| Label | Set by | Meaning |
|---|---|---|
| `to-code` | planner or Leo | Ready for the executor. This label is the only trigger. |
| `code-working` | executor | Claimed, so a second run does not start. |
| `to-chat` | executor | Result or question waiting for the planner. |
| `needs-leo` | either | A human must decide. Automation stops here. |
| `done` | either | Finished. Close the issue. |

## Message format

Every message the two sides post starts with a header line, so turns can be counted without guessing:

```
<!-- loop:v1 from=chat|code type=task|status|result|question turn=N -->
```

A task message then has these sections: `## Goal`, `## Context` (file paths and links, never pasted code), `## Acceptance criteria`, `## Constraints` (for example "single-file HTML", "Apps Script V8", "no new dependencies"). Clear acceptance criteria are what let the executor finish without asking, which is the whole point of unattended runs.

## Executor procedure

1. Save the issue and run the guard. The guard is deterministic, so it costs almost nothing and does not depend on your judgment:
   `gh api repos/<owner>/<repo>/issues/<N> > issue.json`
   `gh api "repos/<owner>/<repo>/issues/<N>/comments?per_page=100" > comments.json`
   `python scripts/loop_guard.py issue.json --comments comments.json --owner <repo owner login> [--labeled-by <actor>]`
2. Obey the result. `ignore` → do nothing and say nothing on the issue. `needs-leo` → post the guard's reason as a short comment, add `needs-leo`, remove `to-code`, stop. `proceed` → continue.
3. Claim the issue: add `code-working`, remove `to-code`.
4. Do the work. Read only the files the issue names. Work on a `claude/` branch and open a PR. Never push to `main`, never edit `.github/workflows` unless the task says so.
5. If the task turns out to be ambiguous or blocked, stop and ask in one comment (batch all questions) with `needs-leo`. A wrong guess costs more tokens than a question.
6. Write the reply to `reply.md`: the header (`from=code`, `turn` = the guard's `next_turn`), then at most 150 words: what changed, the PR or branch link, how it was checked, open questions. Run `python scripts/check_reply.py reply.md --turn <next_turn> --add to-chat --remove code-working` and fix anything it reports.
7. Post the comment, then apply the labels: remove `code-working`, add `to-chat` (or `needs-leo`).

## GitHub calls (REST only)

Cloud sessions block GraphQL, so `gh issue view`, `gh issue edit` and `gh pr create` fail there. Use `gh api` instead:
- Comment: `gh api -X POST repos/<o>/<r>/issues/<N>/comments -F body=@reply.md`
- Add a label: `gh api -X POST repos/<o>/<r>/issues/<N>/labels -f 'labels[]=to-chat'`
- Remove a label: `gh api -X DELETE repos/<o>/<r>/issues/<N>/labels/code-working` (a 404 means it was not there)
- Open a PR, ready for review: `gh api -X POST repos/<o>/<r>/pulls -f title=... -f head=claude/... -f base=main -F body=@pr.md`

## Planner procedure

- **Hand off a task:** draft the issue with the header (`from=chat type=task turn=1`) and all four sections. If a write-capable GitHub connector works, create it with the `to-code` label. Otherwise give Leo the text to paste into GitHub's New issue page, and tell him the one extra step: add the `to-code` label. Do not pretend the handoff happened if the write did not succeed.
- **Check the loop:** list open issues labeled `to-chat`, summarise each in two lines, then either post a follow-up task (turn = last turn + 1, and re-apply `to-code`) or ask Leo what he wants. Stop when the thread is at the turn cap.

## Loop guards (why each exists)

- **Only `to-code` triggers a run.** Triggering on "any comment" lets two Claudes answer each other forever.
- **Turn cap of 4** (`loop_guard.py --max-turn`). Chat writes to GitHub as Leo's own account, so GitHub's built-in bot check cannot tell the two sides apart. The counter is the real brake.
- **Leo can lift the cap** by commenting `<!-- loop:v1 from=human type=reset turn=0 -->` on the issue and re-applying `to-code`. Only the repo owner's reset counts, and the count restarts from there. Tell Leo this whenever you park a thread at the cap.
- **The executor never applies `to-code`.** Otherwise it could re-trigger itself.
- **Only the repo owner's issues and labels count.** On a public repo anyone can open an issue, and a run costs Leo's Pro quota.
- **One run per label event, one reply per run.**

## Token rules (Leo is on a limited Pro plan)

Cloud runs share the same 5-hour and weekly budget as chat. Keep issue bodies to file paths, not code. Read only named files. Batch small tasks into one issue. Keep replies to the 150-word format. Plan for at most 5 automated runs a day on Pro until the real cap is confirmed.

## When something fails

If a step cannot finish, say which one in a comment, add `needs-leo`, and stop. For auth or connector failures name the exact setup step to redo (see `references/setup.md`). A run that "succeeded" only means the session ended, so always check the labels and the reply, not the run status.
