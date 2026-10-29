#!/usr/bin/env python3
"""The executor's GitHub writes, as validated commands (REST only, no GraphQL).

    loop_gh.py claim     --repo o/r --issue N
    loop_gh.py reply     --repo o/r --issue N --file reply.md --turn T --add to-chat
    loop_gh.py park      --repo o/r --issue N --turn T --reason "why a human is needed" [--phase 1|2]
    loop_gh.py post-plan --repo o/r --issue N --file reply.md --turn T
    loop_gh.py merge     --repo o/r --issue N --pr P --owner LOGIN [--method merge] [--base main]
    loop_gh.py finish    --repo o/r --issue N --file summary.md --turn T

claim      adds code-working and removes to-code, awaiting-approval and needs-leo.
           Refuses (exit 3) if code-working is already there.
reply      classic hand-off: checks reply.md, posts it, removes code-working, adds ONE of
           to-chat, needs-leo or done. Nothing is posted if the check fails.
park       posts a short from=code question, removes to-code, code-working and
           awaiting-approval, adds needs-leo. Owner answers with CONTINUE: or REVISE:.
post-plan  autopilot Phase 1: checks a type=plan phase=1 reply, posts it, removes
           code-working, to-code and needs-leo, adds awaiting-approval.
merge      autopilot Phase 2: re-reads the issue and merges ONLY if the owner's APPROVED
           comment follows the latest plan (exit 4 otherwise), and only if the PR is open,
           not a draft, on a claude/ branch, against the base branch and mergeable
           (exit 5 otherwise). The head SHA is pinned, so nothing pushed later slips in.
finish     autopilot Phase 2: checks a type=summary phase=2 reply (up to 250 words), posts
           it, removes code-working, awaiting-approval and needs-leo, adds done, closes
           the issue as completed.

No command can add to-code. Add --dry-run to print the planned writes without sending
them (merge still reads the issue and PR, or --fixtures DIR with issue.json,
comments.json and pr.json for offline tests).
Exit codes: 0 ok, 1 reply failed validation, 2 GitHub call failed, 3 already claimed,
4 not approved, 5 PR not mergeable.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_reply import check  # noqa: E402
from loop_guard import approval_status  # noqa: E402

HANDOFF = {"to-chat", "needs-leo", "done"}


class GhError(Exception):
    pass


def gh(args, dry_run, plan, tolerate_404=False):
    plan.append("gh api " + " ".join(args))
    if dry_run:
        return ""
    proc = subprocess.run(["gh", "api"] + args, capture_output=True, text=True)
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout).strip()
        if tolerate_404 and ("404" in msg or "not found" in msg.lower() or "does not exist" in msg.lower()):
            return ""
        raise GhError(f"gh api {' '.join(args)} failed: {msg[:300]}")
    return proc.stdout


def read_json(path, fixtures, name):
    """A read is never skipped by --dry-run; --fixtures replaces the network."""
    if fixtures:
        with open(os.path.join(fixtures, name), encoding="utf-8") as f:
            return json.load(f)
    proc = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if proc.returncode != 0:
        raise GhError(f"gh api {path} failed: {(proc.stderr or proc.stdout).strip()[:300]}")
    return json.loads(proc.stdout)


def add_label(repo, issue, label, dry_run, plan):
    gh(["-X", "POST", f"repos/{repo}/issues/{issue}/labels", "-f", f"labels[]={label}"], dry_run, plan)


def remove_labels(repo, issue, labels, dry_run, plan):
    for label in labels:
        gh(["-X", "DELETE", f"repos/{repo}/issues/{issue}/labels/{label}"], dry_run, plan, tolerate_404=True)


def post_comment(repo, issue, path, dry_run, plan):
    gh(["-X", "POST", f"repos/{repo}/issues/{issue}/comments", "-F", f"body=@{path}"], dry_run, plan)


def checked_post(a, plan, add, remove, want_type):
    """Validate the reply file, then post it and swap the labels."""
    with open(a.file, encoding="utf-8") as f:
        text = f.read()
    report = check(text, a.turn, [add], ["code-working"])
    if report["ok"] and want_type and report["type"] != want_type:
        report["ok"] = False
        report["problems"].append(f"this command posts a type={want_type} reply, found type={report['type']}")
    if not report["ok"]:
        return 1, report
    post_comment(a.repo, a.issue, a.file, a.dry_run, plan)
    remove_labels(a.repo, a.issue, remove, a.dry_run, plan)
    add_label(a.repo, a.issue, add, a.dry_run, plan)
    return 0, dict(report, posted=a.issue, label=add)


def cmd_claim(a, plan):
    if not a.dry_run:
        raw = gh([f"repos/{a.repo}/issues/{a.issue}", "--jq", "[.labels[].name]"], False, plan)
        if "code-working" in json.loads(raw or "[]"):
            return 3, {"ok": False, "problem": "already claimed (code-working is set); do nothing"}
    add_label(a.repo, a.issue, "code-working", a.dry_run, plan)
    remove_labels(a.repo, a.issue, ["to-code", "awaiting-approval", "needs-leo"], a.dry_run, plan)
    return 0, {"ok": True, "claimed": a.issue}


def cmd_reply(a, plan):
    if a.add not in HANDOFF:
        return 1, {"ok": False, "problems": [f"--add must be one of {sorted(HANDOFF)}"]}
    return checked_post(a, plan, a.add, ["code-working"], None)


def cmd_post_plan(a, plan):
    return checked_post(a, plan, "awaiting-approval", ["code-working", "to-code", "needs-leo"], "plan")


def cmd_finish(a, plan):
    code, out = checked_post(a, plan, "done", ["code-working", "awaiting-approval", "needs-leo"], "summary")
    if code == 0:
        gh(["-X", "PATCH", f"repos/{a.repo}/issues/{a.issue}", "-f", "state=closed", "-f", "state_reason=completed"],
           a.dry_run, plan)
        out["closed"] = True
    return code, out


def cmd_park(a, plan):
    phase = f" phase={a.phase}" if a.phase else ""
    body = f"<!-- loop:v1 from=code type=question{phase} turn={a.turn} -->\nPaused: {a.reason.strip()}\n"
    if a.phase:
        body += "Reply `CONTINUE: <answer>` to resume, or `REVISE: <notes>` to change the plan.\n"
    report = check(body, a.turn, ["needs-leo"], ["code-working"])
    if not report["ok"]:
        return 1, report
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(body)
        path = f.name
    try:
        post_comment(a.repo, a.issue, path, a.dry_run, plan)
    finally:
        os.unlink(path)
    remove_labels(a.repo, a.issue, ["to-code", "code-working", "awaiting-approval"], a.dry_run, plan)
    add_label(a.repo, a.issue, "needs-leo", a.dry_run, plan)
    return 0, {"ok": True, "parked": a.issue, "comment": body}


def cmd_merge(a, plan):
    issue = read_json(f"repos/{a.repo}/issues/{a.issue}", a.fixtures, "issue.json")
    issue["comments"] = read_json(f"repos/{a.repo}/issues/{a.issue}/comments?per_page=100", a.fixtures, "comments.json")
    approval = approval_status(issue, a.owner)
    if not approval["approved"]:
        return 4, {"ok": False, "problem": f"not merging: {approval['reason']}"}

    pr = read_json(f"repos/{a.repo}/pulls/{a.pr}", a.fixtures, "pr.json")
    for _ in range(5):  # GitHub computes mergeability in the background
        if pr.get("mergeable") is not None or a.fixtures:
            break
        time.sleep(3)
        pr = read_json(f"repos/{a.repo}/pulls/{a.pr}", a.fixtures, "pr.json")
    head = pr.get("head") or {}
    problems = []
    if pr.get("state") != "open" or pr.get("merged"):
        problems.append("PR is not open")
    if pr.get("draft"):
        problems.append("PR is a draft")
    if not str(head.get("ref", "")).startswith("claude/"):
        problems.append("PR head is not a claude/ branch")
    if (pr.get("base") or {}).get("ref") != a.base:
        problems.append(f"PR base is not {a.base}")
    if pr.get("mergeable") is not True or pr.get("mergeable_state") != "clean":
        problems.append(f"PR is not cleanly mergeable (mergeable={pr.get('mergeable')}, "
                        f"state={pr.get('mergeable_state')})")
    if problems:
        return 5, {"ok": False, "problem": "not merging: " + "; ".join(problems)}

    raw = gh(["-X", "PUT", f"repos/{a.repo}/pulls/{a.pr}/merge", "-f", f"merge_method={a.method}",
              "-f", f"sha={head['sha']}"], a.dry_run, plan)
    result = json.loads(raw) if raw else {}
    return 0, {"ok": True, "approval": approval["reason"], "merged": result.get("merged", a.dry_run),
               "merge_sha": result.get("sha"), "head_sha": head["sha"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("claim", "reply", "park", "post-plan", "merge", "finish"):
        p = sub.add_parser(name)
        p.add_argument("--repo", required=True)
        p.add_argument("--issue", type=int, required=True)
        p.add_argument("--dry-run", action="store_true")
        if name in ("reply", "post-plan", "finish"):
            p.add_argument("--file", required=True)
            p.add_argument("--turn", type=int, required=True)
        if name == "reply":
            p.add_argument("--add", required=True)
        if name == "park":
            p.add_argument("--turn", type=int, required=True)
            p.add_argument("--reason", required=True)
            p.add_argument("--phase", type=int, choices=(1, 2), default=None)
        if name == "merge":
            p.add_argument("--pr", type=int, required=True)
            p.add_argument("--owner", required=True)
            p.add_argument("--method", choices=("merge", "squash", "rebase"), default="merge")
            p.add_argument("--base", default="main")
            p.add_argument("--fixtures", default=None)
    a = ap.parse_args()

    commands = {"claim": cmd_claim, "reply": cmd_reply, "park": cmd_park,
                "post-plan": cmd_post_plan, "merge": cmd_merge, "finish": cmd_finish}
    plan = []
    try:
        code, out = commands[a.cmd](a, plan)
    except GhError as e:
        code, out = 2, {"ok": False, "problem": str(e)}
    if a.dry_run:
        out["dry_run_calls"] = plan
    json.dump(out, sys.stdout, indent=2)
    print()
    sys.exit(code)


if __name__ == "__main__":
    main()
