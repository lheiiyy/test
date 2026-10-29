#!/usr/bin/env python3
"""The executor's GitHub writes, as three validated commands (REST only, no GraphQL).

    loop_gh.py claim --repo o/r --issue N
    loop_gh.py reply --repo o/r --issue N --file reply.md --turn T --add to-chat
    loop_gh.py park  --repo o/r --issue N --turn T --reason "why a human is needed"

claim  adds code-working and removes to-code. It refuses if code-working is already there.
reply  checks reply.md with check_reply.py, posts it, removes code-working, adds ONE hand-off
       label (to-chat, needs-leo or done). Nothing is posted if the check fails.
park   posts a short from=code question comment, removes to-code and code-working, adds
       needs-leo. Use it for guard needs-leo results and for stale claims.

The executor can never add to-code: this script has no way to do it.
Add --dry-run to print the planned calls without touching GitHub.
Exit codes: 0 ok, 1 reply failed validation, 2 GitHub call failed, 3 already claimed.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_reply import check  # noqa: E402

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


def add_label(repo, issue, label, dry_run, plan):
    gh(["-X", "POST", f"repos/{repo}/issues/{issue}/labels", "-f", f"labels[]={label}"], dry_run, plan)


def remove_label(repo, issue, label, dry_run, plan):
    gh(["-X", "DELETE", f"repos/{repo}/issues/{issue}/labels/{label}"], dry_run, plan, tolerate_404=True)


def post_comment(repo, issue, path, dry_run, plan):
    gh(["-X", "POST", f"repos/{repo}/issues/{issue}/comments", "-F", f"body=@{path}"], dry_run, plan)


def cmd_claim(a, plan):
    if not a.dry_run:
        raw = gh([f"repos/{a.repo}/issues/{a.issue}", "--jq", "[.labels[].name]"], False, plan)
        if "code-working" in json.loads(raw or "[]"):
            return 3, {"ok": False, "problem": "already claimed (code-working is set); do nothing"}
    add_label(a.repo, a.issue, "code-working", a.dry_run, plan)
    remove_label(a.repo, a.issue, "to-code", a.dry_run, plan)
    return 0, {"ok": True, "claimed": a.issue}


def cmd_reply(a, plan):
    if a.add not in HANDOFF:
        return 1, {"ok": False, "problems": [f"--add must be one of {sorted(HANDOFF)}"]}
    with open(a.file, encoding="utf-8") as f:
        text = f.read()
    report = check(text, a.turn, [a.add], ["code-working"])
    if not report["ok"]:
        return 1, report
    post_comment(a.repo, a.issue, a.file, a.dry_run, plan)
    remove_label(a.repo, a.issue, "code-working", a.dry_run, plan)
    add_label(a.repo, a.issue, a.add, a.dry_run, plan)
    return 0, {"ok": True, "posted": a.issue, "words": report["words"], "label": a.add}


def cmd_park(a, plan):
    body = f"<!-- loop:v1 from=code type=question turn={a.turn} -->\nPaused: {a.reason.strip()}\n"
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
    remove_label(a.repo, a.issue, "to-code", a.dry_run, plan)
    remove_label(a.repo, a.issue, "code-working", a.dry_run, plan)
    add_label(a.repo, a.issue, "needs-leo", a.dry_run, plan)
    return 0, {"ok": True, "parked": a.issue}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("claim", "reply", "park"):
        p = sub.add_parser(name)
        p.add_argument("--repo", required=True)
        p.add_argument("--issue", type=int, required=True)
        p.add_argument("--dry-run", action="store_true")
        if name == "reply":
            p.add_argument("--file", required=True)
            p.add_argument("--turn", type=int, required=True)
            p.add_argument("--add", required=True)
        if name == "park":
            p.add_argument("--turn", type=int, required=True)
            p.add_argument("--reason", required=True)
    a = ap.parse_args()

    plan = []
    try:
        code, out = {"claim": cmd_claim, "reply": cmd_reply, "park": cmd_park}[a.cmd](a, plan)
    except GhError as e:
        code, out = 2, {"ok": False, "problem": str(e)}
    if a.dry_run:
        out["dry_run_calls"] = plan
    json.dump(out, sys.stdout, indent=2)
    print()
    sys.exit(code)


if __name__ == "__main__":
    main()
