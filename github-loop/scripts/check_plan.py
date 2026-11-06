#!/usr/bin/env python3
"""Check an autopilot Phase 1 plan file before it is posted.

    check_plan.py <project>/docs/plan-<feature>.md --git-base origin/main
    check_plan.py docs/plan-x.md --changed docs/plan-x.md other/file.js     (tests)

Settings (.github/github-loop.json, or --config):
- `plan_sections`: "lite" means four sections, Goal, Tasks, Tests and Merge plan; a list names the
  sections. Topic checks run only for the six known heavy names. Whatever the setting, these stay:
  the Merge plan with its Risk:, CI required: and Files in scope: lines, a model tier, and
  AWAITING APPROVAL. Without the setting, the six heavy sections below are required, as before.
- `plan_dir`: the plan file must be under this folder (give the plan path from the repository root).
- `commit_ref_pattern`: the plan must show the commit reference format (a line matching it), because
  the merge gate checks every commit message against it.

Checks (the default, heavy plan):
- the six sections exist and are not empty: Business plan, Architecture,
  Task breakdown, Test plan, Merge plan, Readiness (## or ### headings, numbering optional);
- the task breakdown carries a model plan: it names a tier (haiku, sonnet or opus);
- the business plan covers problem, users, value, scope, out of scope, success
  metrics, risks and effort; the architecture covers components, data flow, schema,
  integration points, migration and decisions; the task breakdown has pass/fail
  checks and the responsible agent; the merge plan names the branch, the method and
  the release policy (deploy or no deploy); the readiness section uses the statuses
  READY, NEEDS SETUP, BLOCKED, NOT REQUIRED or UNVERIFIED;
- the merge plan declares `Risk: low|normal|high`, `CI required: yes|no` and
  `Files in scope: <folders/ and files>` on their own lines (the plan reply repeats them, and the
  merge gate reads them: high risk, or a changed file outside the scope, means the owner merges);
  with --git-base or --changed, the scope must cover the plan file itself;
- the last non-empty line is exactly AWAITING APPROVAL;
- with --git-base or --changed: the plan is the only changed file, because
  Phase 1 makes no code changes.

Prints a JSON report; exit 1 on any problem.
"""
import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as loop_config  # noqa: E402
from rules import declared_scope, glob_match, in_scope, scope_problems  # noqa: E402

SECTIONS = ["Business plan", "Architecture", "Task breakdown", "Test plan", "Merge plan", "Readiness"]
LITE = ["Goal", "Tasks", "Tests", "Merge plan"]
TOPICS = {
    "Business plan": ["problem", "user", "value", "scope", "out of scope|out-of-scope",
                      "success metric", "risk", "effort"],
    "Architecture": ["component", "data flow", "schema", "integration", "migration", "decision"],
    "Task breakdown": ["pass|fail|check", "code|lead"],
    "Test plan": ["test"],
    "Merge plan": ["branch", "method", "deploy|release"],
    "Readiness": ["ready|needs setup|blocked|not required|unverified"],
}
TIERS = re.compile(r"\b(haiku|sonnet|opus)\b", re.IGNORECASE)
RISK_LINE = re.compile(r"(?im)^[ \t>*-]*risk[ \t]*:[ \t]*\**[ \t]*(low|normal|high)\b")
CI_LINE = re.compile(r"(?im)^[ \t>*-]*CI required[ \t]*:[ \t]*\**[ \t]*(yes|no)\b")
HEADING = re.compile(r"^(#{2,3})\s+(.+?)\s*$", re.MULTILINE)


def required_sections(cfg=None):
    """The section names a plan needs: the six heavy ones, the four lite ones, or the configured list (the
    Merge plan is always added, because the merge gate reads it)."""
    wanted = (cfg or {}).get("plan_sections")
    if wanted == loop_config.LITE_SECTIONS:
        return list(LITE)
    if isinstance(wanted, list) and wanted:
        names = [str(n).strip() for n in wanted if str(n).strip()]
        return names + ([] if any(n.lower() == "merge plan" for n in names) else ["Merge plan"])
    return list(SECTIONS)


def sections(text, names=SECTIONS):
    """Map each required section name to its body text (None when missing)."""
    found = {}
    heads = list(HEADING.finditer(text))
    for n, h in enumerate(heads):
        title = re.sub(r"^\d+[.)]\s*", "", h.group(2)).lower()
        for name in names:
            if name.lower() in title and name not in found:
                level = len(h.group(1))
                end = len(text)
                for later in heads[n + 1:]:
                    if len(later.group(1)) <= level:
                        end = later.start()
                        break
                found[name] = text[h.end():end].strip()
    return {name: found.get(name) for name in names}


def changed_files_from_git(base):
    def git(*args):
        proc = subprocess.run(["git"] + list(args), capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()[:200]}")
        return proc.stdout
    top = git("rev-parse", "--show-toplevel").strip()
    # Compare with the point where the branch left the base, so new commits on the base never count as changes
    # of this branch (the working tree is compared, so uncommitted edits count too).
    fork_point = git("merge-base", base, "HEAD").strip()
    changed = git("diff", "--name-only", fork_point).split()
    untracked = git("ls-files", "--others", "--exclude-standard", "--full-name", top).split()
    names = set(changed) | set(untracked)
    return top, sorted(names)


def check(text, plan_rel=None, changed=None, cfg=None):
    problems = []
    names = required_sections(cfg)
    body = sections(text, names)
    for name in names:
        if body[name] is None:
            problems.append(f"missing section: {name}")
        elif not body[name]:
            problems.append(f"empty section: {name}")
        else:
            low = body[name].lower()
            for topic in TOPICS.get(name, []):  # topic checks only for the six known heavy names
                if not any(word in low for word in topic.split("|")):
                    problems.append(f"{name} does not cover: {topic.split('|')[0]}")
            if name == "Merge plan":
                if not RISK_LINE.search(body[name]):
                    problems.append("Merge plan needs a line `Risk: low|normal|high` (high: the owner merges)")
                if not CI_LINE.search(body[name]):
                    problems.append("Merge plan needs a line `CI required: yes|no`")
                scope = declared_scope(body[name])
                problems += [f"Merge plan: {p}" for p in scope_problems(scope)]
                if changed is not None and scope and not in_scope(plan_rel, scope):
                    problems.append(f"Merge plan: `Files in scope:` must include the plan file {plan_rel}")
    task_section = next((n for n in ("Task breakdown", "Tasks") if n in names), None)
    if task_section and body.get(task_section) and not TIERS.search(body[task_section]):
        problems.append(f"{task_section} has no model plan: name a tier (haiku, sonnet or opus) per step, "
                        "from scripts/pick_model.py")
    elif not task_section and not TIERS.search(text):
        problems.append("the plan has no model plan: name a tier (haiku, sonnet or opus) per step, from "
                        "scripts/pick_model.py")
    plan_dir = (cfg or {}).get("plan_dir")
    if plan_dir and plan_rel and not glob_match(plan_rel, plan_dir.rstrip("/") + "/**"):
        problems.append(f"the plan file {plan_rel} must be under {plan_dir}/ (the plan_dir setting)")
    ref = (cfg or {}).get("commit_ref_pattern")
    if ref and not re.search(ref, text, re.MULTILINE):
        problems.append(f"the plan must show the commit reference format: a line matching `{ref}` (the merge gate "
                        "checks every commit message against it)")
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines or lines[-1] != "AWAITING APPROVAL":
        problems.append('the last line must be exactly "AWAITING APPROVAL"')
    if changed is not None:
        others = [f for f in changed if os.path.normpath(f) != os.path.normpath(plan_rel)]
        if others:
            problems.append("Phase 1 must change only the plan file; also changed: " + ", ".join(others))
        if os.path.normpath(plan_rel) not in [os.path.normpath(f) for f in changed]:
            problems.append("the plan file is not among the changed files")
    return {"ok": not problems, "problems": problems}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan")
    ap.add_argument("--git-base", default=None, help="compare the working tree with this ref, for example origin/main")
    ap.add_argument("--changed", nargs="*", default=None, help="changed files, instead of asking git")
    ap.add_argument("--config", default=None, help="settings file (default .github/github-loop.json)")
    args = ap.parse_args()
    try:
        cfg = loop_config.load(args.config)
    except ValueError as e:
        json.dump({"ok": False, "problems": [str(e)]}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    with open(args.plan, encoding="utf-8") as f:
        text = f.read()
    plan_rel, changed = os.path.normpath(args.plan), args.changed
    if args.git_base:
        try:
            top, changed = changed_files_from_git(args.git_base)
        except RuntimeError as e:
            json.dump({"ok": False, "problems": [str(e)]}, sys.stdout, indent=2)
            print()
            sys.exit(1)
        plan_rel = os.path.relpath(os.path.abspath(args.plan), top)
    report = check(text, plan_rel, changed, cfg)
    report["changed"] = changed
    json.dump(report, sys.stdout, indent=2)
    print()
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
