# One-time setup (all steps work from a tablet browser, except the optional token step)

Do these in order. After each step, tell Leo what to expect and wait for "done" before the next. Steps 1-7 are enough for the main route.

## Main route: Claude Code scheduled task with a GitHub trigger

Uses the Pro subscription, no API key, no YAML, no terminal.

1. **Install the Claude GitHub App** on the repo: github.com/apps/claude. Repo admin is needed.
2. **Create the five labels** in the repo (Issues → Labels → New label): `to-code`, `code-working`, `to-chat`, `needs-leo`, `done`.
3. **Add a short `CLAUDE.md`** at the repo root with stack rules (for example "Apps Script V8, no clasp", "single-file HTML, no build step"). Claude reads it on every run, so keep it under 30 lines.
4. **Commit this skill** to the repo as `.claude/skills/github-loop/` (SKILL.md, scripts/, references/) using GitHub's Add file → Upload files.
5. **Protect `main`** (Settings → Branches → Add rule) so the executor can only land work through `claude/` branches and PRs that Leo merges.
6. **Create the scheduled task** at claude.ai/code/routines. Trigger: GitHub event → Issues → labeled, filter label = `to-code`, author = the repo owner. Prompt: "Follow .claude/skills/github-loop/SKILL.md as the executor for the issue in the event."
7. **Run one test issue** (see the live smoke test in the final hand-off message).

## Alternative route: scheduled task without the GitHub App (what Leo's other repos use)

The GitHub-event trigger can only be created in the claude.ai UI, and it needs the Claude GitHub App. A cron scheduled task needs neither, and can be made from chat with the scheduled-task tools:
- **Hourly check:** a scheduled task that runs `scripts/triage.py` and ends with "No new work." when nothing is waiting. The script does the listing, the guard, the label-actor check and stale-claim detection, so an idle run is one command. Leo's TLMI-AI tasks run hourly with the same shape and succeed, so the "5 runs a day on Pro" limit from the launch post does not appear to be enforced. Suggested prompt, short on purpose:
  > Clone `<owner>/<repo>`. Run `python .claude/skills/github-loop/scripts/triage.py --repo <owner>/<repo> --owner <owner>` from the repo root. If the summary is "No new work.", reply with exactly that and stop. If triage fails, say so and stop. Otherwise follow `.claude/skills/github-loop/SKILL.md` (executor procedure, steps 2 to 7) for the first `work` entry. Never merge, never push to `main`, never add `to-code`. Final message: one line in Taglish.
- **Poke-only:** a scheduled task with no schedule at all, started by `fire_trigger` right after the planner creates the issue. It costs nothing while idle, but a label added by hand in the GitHub app does not wake it.
- Use REST (`gh api`) everywhere; GraphQL is blocked in cloud sessions.

## Optional: return path from chat

- Say "check the loop" in any chat, or
- add one daily scheduled chat task: "List open issues labeled to-chat in <repo>, summarise each in two lines, and stop."
- Only if Leo wants chat to create issues itself: add GitHub's remote MCP server (https://api.githubcopilot.com/mcp/) as a custom connector, set only the issue and comment write tools to "Always allow", and test for a week. Reliability bugs are open on this, so the paste-and-label fallback stays valid.

## Optional fallback: GitHub Action (needs a one-year token made in a terminal)

Only needed if scheduled-task run limits get in the way. A free browser Codespace can stand in for the terminal: install Claude Code there, run `claude setup-token`, copy the token at once, and save it as the repo secret `CLAUDE_CODE_OAUTH_TOKEN`. Renew yearly. This flow is documented but has not been tested on a tablet.

Save as `.github/workflows/claude-loop.yml`:

```yaml
name: claude-loop
on:
  issues:
    types: [labeled]
concurrency:
  group: claude-${{ github.event.issue.number }}
  cancel-in-progress: false
jobs:
  claude:
    if: github.event.label.name == 'to-code' && github.event.sender.login == github.repository_owner
    runs-on: ubuntu-latest
    timeout-minutes: 20
    permissions:
      contents: write
      pull-requests: write
      issues: write
      id-token: write
      actions: read
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 1
      - uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          prompt: "Follow .claude/skills/github-loop/SKILL.md as the executor for issue #${{ github.event.issue.number }}."
          claude_args: |
            --max-turns 8
```

Leave `allowed_bots` empty and never pass `allowed_non_write_users`. This YAML is a design based on the docs and has not been run end to end.

## Known limits to repeat to Leo

- Chat cannot be woken by GitHub. The loop is automatic only up to Claude Code's reply.
- The Pro daily limit for scheduled runs is unconfirmed (launch post says 5 per day, current docs list hourly caps). Plan for 5.
- Scheduled tasks are a research preview, so behavior may change.
