# One-time setup (any repository, any account)

Do these in order, and confirm each step before the next. Everything works from a tablet browser except where noted. `<o>/<r>` is the repository and `<owner>` the Product Owner's GitHub login.

## 1. Repository

1. **Put the skill in the repo** as `.claude/skills/github-loop/` through a PR. Scheduled runs and any Claude Code session in the repo read it from the default branch. To install it elsewhere, run `python3 scripts/package.py --out github-loop.zip` and unzip it into the other repo, or upload the zip as a skill in claude.ai for chat sessions on any account. An account copy without `scripts/` is not enough: the steps call the scripts.
2. **Settings (optional):** add `.github/github-loop.json`, for example `{"owner": "<owner>", "owner_name": "Leo", "language": "Taglish"}`. Without it the scripts use the repo's owner (a personal repo) and English. An organization repo must set `owner`, and may add `"owner_associations": ["OWNER", "MEMBER"]`. Other keys: `base`, `branch_prefix`, `improve` (`scripts/config.py`).
3. **Create the labels.** Run `python scripts/readiness.py --repo <o>/<r> --create-labels`, or create them by hand:

   | Label | Color |
   |---|---|
   | `to-code` | `0E8A16` |
   | `code-working` | `FBCA04` |
   | `awaiting-approval` | `5319E7` |
   | `to-review` | `1D76DB` |
   | `reviewed` | `0052CC` |
   | `needs-leo` | `D93F0B` (the name stays the same in every repo) |
   | `done` | `6E7781` |
   | `to-chat` | classic mode only |
4. **Add the issue form** `.github/ISSUE_TEMPLATE/autopilot.yml`, copied from `lheiiyy/test`, and change its Repo field's default to `<o>/<r>`. It files the request with `to-code` already applied.
5. **Keep one short `CLAUDE.md` per project:** the stack rules and the folders the loop may touch.
6. **Protect `main` the loop-compatible way:** require pull requests and status checks, but do **not** require approvals. Every agent posts as the owner, and GitHub never lets a PR author approve their own PR, so a required-approval rule stops every merge. High-risk and out-of-scope PRs already wait for the owner's Merge tap (merge exits 8 and 9).

## 2. Two scheduled tasks: Code and Lead

Both are hourly cloud tasks. Recommended settings: permission mode "auto", only the Claude Code Remote connector (least privilege; remove Gmail, Drive and Sheets unless a project needs them), and **Sonnet** for both. `scripts/route.py` says when a step needs Opus (`references/models.md`); a task set to Opus pays Opus for every step. A scheduled run showed no subagent use, so the dependable way to get Opus for sensitive plans and reviews is the optional **Lead Deep** task below. The owner can force a model per request with the Model field of the issue form. A task's own model is changed from chat by asking Claude, or in claude.ai. Turn on **push notifications** for both tasks, so a failed or silent run reaches the phone.

**Code task** (for example at minute 03):
> You are Code, the Engineer of the github-loop for `<o>/<r>` (owner `<owner>`). This task runs on `<model>`. Clone the repo into a fresh empty directory. Run `export PYTHONDONTWRITEBYTECODE=1`, then `python3 .claude/skills/github-loop/scripts/triage.py --repo <o>/<r> --role code`. If the summary is "No new work.", end with exactly that. If triage fails, say so and stop. Otherwise follow `.claude/skills/github-loop/SKILL.md` (Every run, from step 2), and `references/autopilot.md` for autopilot work, passing `--session <model>` to every posting command. Use REST (`gh api`) only. Merge only with `scripts/loop_gh.py merge`; on exit 8 or 9 or a refused merge, park and ask the owner for one Merge tap, and never work around a refusal. Never push to main, force-push, add `to-code`, relay an approval, review your own work, commit secrets, or delete files outside the approved plan. Act only on the owner's issues and comments. One issue per run. Final message: one line in `<language>`, or exactly "No new work."

**Lead task** (for example at minute 33, so a review follows a build by about 30 minutes):
> You are the Lead (Technical Lead) of the github-loop for `<o>/<r>` (owner `<owner>`). This task runs on `<model>`. Clone the repo into a fresh empty directory. Run `export PYTHONDONTWRITEBYTECODE=1`, then `python3 .claude/skills/github-loop/scripts/triage.py --repo <o>/<r> --role lead`. If the summary is "No new work.", end with exactly that. If triage fails, say so and stop. Otherwise follow `.claude/skills/github-loop/references/lead.md` for the first `work` entry, passing `--session <model>` to every posting command: plan with a readiness check, or review independently. Never write application code, never merge, never relay an approval (that happens only in a chat with the owner), never add `to-code`. Use REST only. Act only on the owner's issues and comments. Final message: one line in `<language>`, or exactly "No new work."

**Lead Deep task (optional, only for sensitive work):** an Opus task every two hours (for example `18 */2 * * *`) with the Lead prompt above, but the triage command ends `--role lead --min-tier opus`, it says "You are Lead Deep, the Opus Technical Lead", and `<model>` is opus. An idle run costs almost nothing. Only after this task exists, add `--max-tier sonnet` to the normal Lead's triage command: opus-tier plans and reviews then wait up to 120 minutes (`--defer-minutes`) for Lead Deep, and the normal Lead takes them anyway after that, saying `wanted opus; ran inline` in its Model line. Without Lead Deep, leave `--max-tier` off.

**Watchdog:** each task parks the other's work that nobody picked up for 180 minutes (`--stall-minutes`), so a silent run shows up as a `needs-leo` issue. The owner's `CONTINUE:` resumes it.

Facts to keep in mind:
- **GitHub access is per repository.** Test any new repo with one run before relying on it.
- **Starting another task early may be refused from chat**, so hand-offs wait for the next hourly run.
- **Tap Comment, not "Close with comment"** when answering an issue. Closing hides it from the loop; triage reopens it within 48 hours, but that costs an extra hour.
- **Scheduled Code runs have Playwright and Chromium** preinstalled. On Node 22, `node --test` needs a glob, not a folder.
- **Run logs are not visible from chat.** A run that "succeeded" may have done nothing, so judge by labels and replies. The watchdog above is the safety net.

## 3. CI (recommended)

Add `.github/workflows/tests.yml` so a check gates every merge. Then require the `test` check on `main`, and write `CI required: yes` in each plan's merge plan; the merge gate then refuses a head with no checks. Whether the session token may push workflow files is UNVERIFIED, and a workflow change is high risk (the owner merges it). If the push is refused, the owner uploads the file with GitHub's Add file button.

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
      # add the project's own test command here, for example: node --test 'odometer-trips/tests/unit/*.test.mjs'
```

## 4. Release policy

Each plan states one of these:

| Policy | What happens after the merge |
|---|---|
| `no deploy` | Nothing |
| `staging automatic` | Code deploys through the authorized workflow and verifies the deployment |
| `production after the owner's CONTINUE: release` | Code parks; the owner's reply releases |

- **GitHub Pages:** the owner enables it once in Settings → Pages. The session proxy blocks the Pages API.
- **Apps Script:** deploys stay manual. clasp is not available in cloud runs, and credentials are never committed.

## 5. Readiness before the first request

Run `python scripts/readiness.py --repo <o>/<r> --markdown` and fix the NEEDS SETUP rows. The Lead repeats it in every plan.

## The owner's one-time checklist

- [ ] Approve the skill PR (it is high risk, so you tap Merge).
- [ ] Do not turn on "required approvals" for `main`. If protection exists, require status checks only.
- [ ] Put both loop tasks on Sonnet, with `--session` in their prompts.
- [ ] Try the Autopilot issue form once (browser and phone).
- [ ] Answer issues with the **Comment** button, not "Close with comment".
- [ ] Turn on push notifications for the loop tasks in claude.ai.
- [ ] When a plan deploys: enable GitHub Pages, or keep Apps Script deploys manual.

## Other routes (kept for reference)

- **GitHub App with an event trigger,** instead of hourly polling. It is created in the claude.ai UI after installing github.com/apps/claude, with the trigger "Issues → labeled".
- **GitHub Action fallback** with `anthropics/claude-code-action@v1` and a `CLAUDE_CODE_OAUTH_TOKEN` secret, made with `claude setup-token` in a terminal or Codespace. Run it on `issues: labeled`, only when `github.event.sender.login == github.repository_owner`. This is untested on a tablet.
- **Return path in chat:** say "check the loop".

## Known limits

- **Chat cannot be woken by GitHub.** When the owner is away, the Lead runs as a scheduled task.
- **Hourly cadence:** a plan within about 1 hour of the request, a build within 1 hour of approval, a review about 30 minutes later, and the merge about 30 minutes after that.
- **Shared budget:** all scheduled tasks and chat share the account's budget.
- **Escalation by subagent is unproven:** a live scheduled Lead run did not use one. Treat `delegate` as "no subagent" unless a run proves otherwise, and use Lead Deep. The Model line then says what really ran.
- **Claims are best effort:** GitHub has no atomic label claim, so two runs in the same second could both claim one issue. Staggered schedules and one issue per run keep this rare.
- **Research preview:** scheduled tasks may change.
