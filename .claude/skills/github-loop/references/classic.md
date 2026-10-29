# Classic mode (chat ↔ Code)

An issue without Phase 1 and Phase 2 headings is classic mode: one task, one build, no plan approval.

- **Planner (chat):** write the issue with the header `<!-- loop:v1 from=chat type=task turn=1 -->` and the sections `## Goal`, `## Context` (paths, no pasted code), `## Acceptance criteria` and `## Constraints`. Create it with `to-code` if a GitHub write works; otherwise give the owner the text and ask them to add `to-code`.
- **Code:** run `python scripts/loop_gh.py claim --repo <o>/<r> --issue <N>`, do the work on a `claude/` branch, open a PR, then run `python scripts/loop_gh.py reply --repo <o>/<r> --issue <N> --file reply.md --turn <next_turn> --add <to-chat|needs-leo|done>` with 150 words or fewer.
- **Turn cap:** 4. The owner lifts it with an owner comment `<!-- loop:v1 from=human type=reset turn=0 -->`.
- **Check the loop (chat):** summarise the `to-chat` and `awaiting-approval` issues in two lines each.
- Classic mode has no scripted merge: the owner merges the PR.
