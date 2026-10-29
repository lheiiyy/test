# One-time setup

Do these in order, and confirm each step before the next. Everything works from a tablet browser except where noted.

## 1. Repository

1. **Commit this skill** as `.claude/skills/github-loop/` through a PR. Scheduled runs read it from the default branch.
2. **Create the labels.** Run `python scripts/readiness.py --repo <o>/<r> --owner <owner> --create-labels`, or create them by hand:

   | Label | Color |
   |---|---|
   | `to-code` | `0E8A16` |
   | `code-working` | `FBCA04` |
   | `awaiting-approval` | `5319E7` |
   | `to-review` | `1D76DB` |
   | `reviewed` | `0052CC` |
   | `needs-leo` | `D93F0B` |
   | `done` | `6E7781` |
   | `to-chat` | classic mode only |
3. **Add the issue form** `.github/ISSUE_TEMPLATE/autopilot.yml`, copied from `lheiiyy/test`. It files the request with `to-code` already applied.
4. **Keep one short `CLAUDE.md` per project:** the stack rules and the folders the loop may touch.
5. **Protect `main` the loop-compatible way:** require pull requests and status checks, but do **not** require approvals. Every agent posts as the owner, and GitHub never lets a PR author approve their own PR, so a required-approval rule stops every merge. If Leo wants to approve each merge himself, he taps Merge, which brings automation to about 80%.

## 2. Two scheduled tasks: Code and Lead

Both are hourly cloud tasks. Recommended settings: permission mode "auto", only the Claude Code Remote connector (least privilege), and a Sonnet model to save the shared Pro budget.

**Code task** (for example at minute 03):
> You are Code, the Engineer of the github-loop for `<o>/<r>` (owner `<owner>`, who reads Taglish). Clone the repo into a fresh empty directory. Run `export PYTHONDONTWRITEBYTECODE=1`, then `python3 .claude/skills/github-loop/scripts/triage.py --repo <o>/<r> --owner <owner> --role code`. If the summary is "No new work.", end with exactly that. If triage fails, say so and stop. Otherwise follow `.claude/skills/github-loop/SKILL.md` (Every run, from step 2), and `references/autopilot.md` for autopilot work. Use REST (`gh api`) only. Merge only with `scripts/loop_gh.py merge`; if a permission rule refuses it, park and ask Leo for one tap, and never work around a refusal. Never push to main, force-push, add `to-code`, commit secrets, or delete files outside the approved plan. Act only on the owner's issues and comments. One issue per run. Final message: one line in Taglish, or exactly "No new work."

**Lead task** (for example at minute 33, so a review follows a build by about 30 minutes):
> You are the Lead (Claude Cowork as Technical Lead) of the github-loop for `<o>/<r>` (owner `<owner>`). Clone the repo into a fresh empty directory. Run `export PYTHONDONTWRITEBYTECODE=1`, then `python3 .claude/skills/github-loop/scripts/triage.py --repo <o>/<r> --owner <owner> --role lead`. If the summary is "No new work.", end with exactly that. If triage fails, say so and stop. Otherwise follow `.claude/skills/github-loop/references/lead.md` for the first `work` entry: plan with a readiness check, or review independently. Never write application code, never merge, never relay an approval (that happens only in a chat with Leo), never add `to-code`. Use REST only. Act only on the owner's issues and comments. Final message: one line in Taglish, or exactly "No new work."

Facts to keep in mind:
- **GitHub access is per repository.** The scheduled session reached `lheiiyy/test`. Test any new repo with one run before relying on it.
- **Starting another task early is refused from chat on this account** ("Run Routine Now"), so hand-offs wait for the next hourly run.

## 3. CI (recommended)

Add `.github/workflows/tests.yml` so a check gates every merge. Then require the `test` check on `main`, and write "CI required: yes" in each plan's merge plan; Code then merges with `--require-checks`. Whether the session token may push workflow files is UNVERIFIED. If the push is refused, Leo uploads the file with GitHub's Add file button.

```yaml
name: tests
on:
  pull_request:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 -B .claude/skills/github-loop/evals/test_scripts.py
      # add the project's own test command here, for example: node --test odometer-trips/tests/
```

## 4. Release policy

Each plan states one of these:

| Policy | What happens after the merge |
|---|---|
| `no deploy` | Nothing |
| `staging automatic` | Code deploys through the authorized workflow and verifies the deployment |
| `production after Leo's CONTINUE: release` | Code parks; Leo's reply releases |

- **GitHub Pages:** Leo enables it once in Settings → Pages. The session proxy blocks the Pages API.
- **Apps Script:** deploys stay manual. clasp is not available in cloud runs, and credentials are never committed.

## 5. Readiness before the first request

Run `python scripts/readiness.py --repo <o>/<r> --owner <owner> --markdown` and fix the NEEDS SETUP rows. The Lead repeats it in every plan.

## Leo's one-time checklist

- [ ] Approve the skill PR.
- [ ] Do not turn on "required approvals" for `main`. If protection exists, require status checks only.
- [ ] Try the Autopilot issue form once (browser and phone).
- [ ] When a plan deploys: enable GitHub Pages, or keep Apps Script deploys manual.

## Other routes (kept for reference)

- **GitHub App with an event trigger,** instead of hourly polling. It is created in the claude.ai UI after installing github.com/apps/claude, with the trigger "Issues → labeled".
- **GitHub Action fallback** with `anthropics/claude-code-action@v1` and a `CLAUDE_CODE_OAUTH_TOKEN` secret, made with `claude setup-token` in a terminal or Codespace. Run it on `issues: labeled`, only when `github.event.sender.login == github.repository_owner`. This is untested on a tablet.
- **Return path in chat:** say "check the loop".

## Known limits

- **Chat cannot be woken by GitHub.** When Leo is away, the Lead runs as a scheduled task.
- **Hourly cadence:** a plan within about 1 hour of the request, a build within 1 hour of approval, a review about 30 minutes later, and the merge about 30 minutes after that.
- **Shared budget:** all scheduled tasks and chat share the Pro budget.
- **Research preview:** scheduled tasks may change.
