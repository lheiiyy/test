#!/usr/bin/env python3
"""Pick the model tier for one github-loop step, from facts and not from a feeling.

    pick_model.py --step review --git-range origin/main...HEAD --session sonnet
    pick_model.py --step plan --text issue.md --session sonnet
    pick_model.py --step fix --paths src/auth.js tests/auth.test.js --attempt 2 --session sonnet

Prints a JSON report: tier (haiku, sonnet or opus), action ("run inline" or
"delegate"), the reasons, and the signals it saw. Exit 0, or 2 on bad input.

Rules (the table in references/models.md mirrors them):
- merge, verify: haiku (a scripted command and its exit code).
- report: sonnet (it states results as facts).
- plan, revise, review: sonnet is the floor. They go to opus on risk, on a big
  change, on an architecture-heavy goal, on the third review round, and on the
  second plan revision.
- build: sonnet (haiku for documentation only); opus only when risky AND big.
- fix: sonnet (haiku for documentation only); opus on risk, on the third review
  round, and on the second attempt at the same failure (before the run parks).
- Leo can force a tier with `Model: opus` in the request, or with the Model field of
  the issue form. It applies to plan, revise, build, fix and review.
- fable (the top tier) is never picked. It costs the most, so only Leo asks for it.

`delegate` means the tier is above the model this task runs on (--session): hand
the judgment to a subagent with that model and keep the scripts and the posting in
this session. A lower tier than the session's runs inline, because a subagent
restarts cold and costs more than it saves.
"""
import argparse
import json
import re
import subprocess
import sys

RANK = {"haiku": 1, "sonnet": 2, "opus": 3, "fable": 4}
STEPS = ["plan", "revise", "build", "fix", "review", "merge", "verify", "report"]
THINKING = {"plan", "revise", "build", "fix", "review"}  # steps Leo may force a tier for

DOCS = re.compile(r"\.(md|txt|rst)$", re.I)
RISK_PATH = re.compile(
    r"(auth(?!or)|permission|(^|[^a-z])roles?([^a-z]|$)|(^|[^a-z])acl([^a-z]|$)|secret|token|credential|passw|"
    r"(^|[^a-z])pin([^a-z]|$)|schema|migration|\.sql$|payment|billing|payroll|security|^\.github/|"
    r"(^|/)appsscript\.json$|\.clasp|deploy|(^|/)\.env)", re.I)
RISK_TEXT = re.compile(
    r"(authenticat|authoriz|permission|access control|role-based|data integrity|schema|migration|payment|"
    r"billing|payroll|credential|destructive|delete (all|data))", re.I)
ARCHITECTURE = re.compile(
    r"(new system|new project|from scratch|architecture|rewrite|redesign|rebuild|platform|re-platform)", re.I)
FORCED = re.compile(r"(?im)^[ \t]*(?:#{1,4}[ \t]*)?model\b(?![ \t]+plan)[^\n:]*?(?::[ \t]*|\n+[ \t]*)"
                    r"(auto|haiku|sonnet|opus)\b")
HEADING = re.compile(r"(?m)^#{2,3}[ \t]+(.+?)[ \t]*$")


def parse_session(value):
    """The model family of the running task: 'sonnet', 'claude-opus-5-5' or 'Opus 5.5' all work."""
    if not value:
        return "sonnet"
    low = value.lower()
    for name in ("haiku", "sonnet", "opus", "fable", "mythos"):
        if name in low:
            return "fable" if name == "mythos" else name
    raise ValueError(f"unknown model: {value!r}; use haiku, sonnet or opus")


def objective_of(text):
    """The Objective section of an autopilot request. The rest of the template (Phase 1, constraints) holds
    boilerplate words such as 'schema' and 'credentials', which must not count as risk. Without an Objective
    heading (a free-form request), the whole text is used."""
    heads = list(HEADING.finditer(text))
    for n, h in enumerate(heads):
        if h.group(1).strip().lower() == "objective":
            end = heads[n + 1].start() if n + 1 < len(heads) else len(text)
            return text[h.end():end]
    return text


def forced_tier(text):
    m = FORCED.search(text or "")
    if m and m.group(1).lower() != "auto":
        return m.group(1).lower()
    return None


def pick(step, paths=(), text="", tasks=0, attempt=1, round_=1, session=None):
    if step not in STEPS:
        raise ValueError(f"unknown step {step!r}; use one of {', '.join(STEPS)}")
    paths = [re.sub(r"^\./", "", p.replace("\\", "/")) for p in paths if p]
    docs_only = bool(paths) and all(DOCS.search(p) and not p.startswith(".github/") for p in paths)
    risk_paths = [] if docs_only else [p for p in paths if RISK_PATH.search(p)]
    goal = objective_of(text or "")
    risk_text = RISK_TEXT.search(goal)
    risky = bool(risk_paths or risk_text)
    large = len(paths) >= 8 or tasks >= 5
    heavy = bool(ARCHITECTURE.search(goal))
    why_risk = ("sensitive files: " + ", ".join(risk_paths[:3])) if risk_paths else (
        f"the goal mentions {risk_text.group(1).lower()}" if risk_text else "")
    forced = forced_tier(text) if step in THINKING else None

    if step in ("merge", "verify"):
        tier, why = "haiku", "a scripted command: run it and read its exit code"
    elif forced:
        tier, why = forced, f"Leo's request sets the model to {forced}"
    elif step == "report":
        tier, why = "sonnet", "the report states results as facts, so keep it accurate"
    elif step in ("plan", "revise"):
        tier, why = "sonnet", "planning needs real reasoning, so sonnet is the floor"
        if risky:
            tier, why = "opus", why_risk + "; plan it with the stronger model"
        elif heavy:
            tier, why = "opus", "an architecture-heavy goal"
        elif large:
            tier, why = "opus", "a big change"
        elif step == "revise" and round_ >= 2:
            tier, why = "opus", "Leo has asked for a second revision"
    elif step == "review":
        tier, why = "sonnet", "independent review: sonnet is the floor, even for documentation"
        if risky:
            tier, why = "opus", why_risk + "; review it with the stronger model"
        elif large:
            tier, why = "opus", "a big diff"
        elif round_ >= 3:
            tier, why = "opus", "the third review round: the earlier fixes did not settle it"
    elif step == "build":
        tier, why = ("haiku", "documentation only") if docs_only else ("sonnet", "ordinary implementation")
        if risky and large:
            tier, why = "opus", "a big change in sensitive code" + (": " + why_risk if why_risk else "")
    else:  # fix
        tier, why = ("haiku", "documentation only") if docs_only else ("sonnet", "an ordinary fix")
        if attempt >= 2:
            tier, why = "opus", "the second attempt at the same failure: escalate before parking"
        elif risky:
            tier, why = "opus", why_risk + "; fix it with the stronger model"
        elif round_ >= 3:
            tier, why = "opus", "the third review round: the earlier fixes did not settle it"

    running = parse_session(session)
    if RANK[tier] > RANK[running]:
        action = "delegate"
        note = (f"Hand the judgment to a subagent with model={tier}; keep the scripts and the posting in this "
                f"session. With no Agent tool, run inline and say so in the reply.")
    elif RANK[tier] < RANK[running]:
        action = "run inline"
        note = f"{tier} would be enough. Run inline, because a subagent restarts cold and costs more than it saves."
    else:
        action = "run inline"
        note = "This task's model fits."
    return {
        "step": step, "tier": tier, "action": action, "session": running, "reasons": [why], "note": note,
        "forced": bool(forced),
        "signals": {"docs_only": docs_only, "risk_paths": risk_paths,
                    "risk_text": risk_text.group(1).lower() if risk_text else None,
                    "large": large, "files": len(paths), "tasks": tasks, "attempt": attempt, "round": round_},
    }


def paths_from_git(rng):
    proc = subprocess.run(["git", "diff", "--name-only", rng], capture_output=True, text=True)
    if proc.returncode != 0:
        raise ValueError(f"git diff --name-only {rng} failed: {proc.stderr.strip()[:200]}")
    return proc.stdout.split()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--step", required=True, choices=STEPS)
    ap.add_argument("--paths", nargs="*", default=[], help="changed or planned files")
    ap.add_argument("--git-range", default=None, help="take the files from git diff --name-only <range>")
    ap.add_argument("--text", default=None, help="the issue or request text file, or - for stdin")
    ap.add_argument("--tasks", type=int, default=0, help="number of tasks in the plan")
    ap.add_argument("--attempt", type=int, default=1, help="attempt at the same failure, 1 or 2")
    ap.add_argument("--round", type=int, default=1, dest="round_", help="plan revision or review round")
    ap.add_argument("--session", default=None, help="model of the running task: haiku, sonnet, opus (default sonnet)")
    args = ap.parse_args()

    try:
        paths = list(args.paths)
        if args.git_range:
            paths += paths_from_git(args.git_range)
        text = ""
        if args.text:
            text = sys.stdin.read() if args.text == "-" else open(args.text, encoding="utf-8").read()
        report = pick(args.step, paths, text, args.tasks, args.attempt, args.round_, args.session)
    except (ValueError, OSError) as e:
        json.dump({"ok": False, "error": str(e)}, sys.stdout, indent=2)
        print()
        sys.exit(2)
    json.dump(report, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
