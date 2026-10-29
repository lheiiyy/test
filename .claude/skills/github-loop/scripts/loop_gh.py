#!/usr/bin/env python3
"""The loop agents' GitHub writes, as validated commands (REST only, no GraphQL).

Lead (Cowork, Technical Lead):
    loop_gh.py post-plan      --repo o/r --issue N --file plan-reply.md --turn T
    loop_gh.py verdict        --repo o/r --issue N --pr P --file verdict.md --turn T
    loop_gh.py relay-approval --repo o/r --issue N --turn T --quote "Leo's own words"   (chat only)
Code (Claude Code, Engineer):
    loop_gh.py ready-for-review --repo o/r --issue N --pr P --file result.md --turn T
    loop_gh.py merge   --repo o/r --issue N --pr P --owner LOGIN [--method merge] [--require-checks]
    loop_gh.py verify  --repo o/r --issue N --pr P
    loop_gh.py finish  --repo o/r --issue N --file summary.md --turn T
    loop_gh.py reply   --repo o/r --issue N --file reply.md --turn T --add to-chat    (classic mode)
Either role:
    loop_gh.py claim   --repo o/r --issue N
    loop_gh.py reopen  --repo o/r --issue N
    loop_gh.py park    --repo o/r --issue N --turn T --reason "..." [--phase 1|2] [--from code|lead]

claim             adds code-working (the claim label for either role) and removes the waiting
                  labels that are present. Refuses (exit 3) if code-working is already there.
post-plan         Phase 1: posts a type=plan phase=1 reply; label awaiting-approval.
relay-approval    posts "APPROVED by Leo in chat" with his quoted words, for a chat Lead whose
                  conversation with Leo contains that approval. Never from a scheduled run.
ready-for-review  posts a type=result phase=2 reply naming pr and the PR's CURRENT head;
                  label to-review.
verdict           posts the Lead's review verdict for the PR's CURRENT head; label reviewed.
merge             merges ONLY when (1) the owner approved the latest plan (exit 4), (2) the
                  latest Lead verdict approves exactly the PR's head (exit 4), (3) no check run
                  or commit status on that head is failing or pending, and with
                  --require-checks at least one exists (exit 6), and (4) the PR is open, not a
                  draft, on a claude/ branch, against the base and cleanly mergeable (exit 5).
                  The head SHA is pinned, so nothing pushed later slips in.
verify            after a merge: the PR is merged, the merge commit is on the base branch, and
                  the check runs on the merge commit are reported (exit 7 if not merged or
                  not on the base).
finish            posts a type=summary phase=2 reply with the five report lines, adds done and
                  closes the issue as completed.
park              posts a short question; labels needs-leo. Leo answers with CONTINUE: or REVISE:.
reopen            reopens an issue that Leo closed by tapping "Close with comment" together with his
                  APPROVED, REVISE: or CONTINUE: (triage lists it under `reopen`). Refuses an issue
                  that is `done` or was closed as "not planned". Posts nothing and changes no label.

No command can add to-code. --dry-run prints the planned writes without sending them
(reads still happen; --fixtures DIR replaces them with issue.json, comments.json, pr.json,
checks.json, status.json and compare.json for offline tests).
Exit codes: 0 ok, 1 reply failed validation, 2 GitHub call failed, 3 already claimed,
4 not approved, 5 PR not mergeable, 6 checks not green, 7 merge not verified.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_reply import check  # noqa: E402
from loop_guard import approval_status, review_status  # noqa: E402

HANDOFF = {"to-chat", "needs-leo", "done"}
WAITING = ["to-code", "awaiting-approval", "needs-leo", "to-review", "reviewed"]
GOOD = {"success", "neutral", "skipped"}


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


def read_json(path, fixtures, name, default=None):
    """A read is never skipped by --dry-run; --fixtures replaces the network."""
    if fixtures:
        full = os.path.join(fixtures, name)
        if not os.path.exists(full):
            if default is not None:
                return default
            raise GhError(f"missing fixture {name}")
        with open(full, encoding="utf-8") as f:
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


def post_text(repo, issue, body, dry_run, plan):
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(body)
        path = f.name
    try:
        post_comment(repo, issue, path, dry_run, plan)
    finally:
        os.unlink(path)


def read_reply(a, add, want_type, expect_from, want_phase=None):
    with open(a.file, encoding="utf-8") as f:
        text = f.read()
    report = check(text, a.turn, [add] if add else None, ["code-working"], expect_from=expect_from)
    if report["ok"] and want_type and report["type"] != want_type:
        report["ok"] = False
        report["problems"].append(f"this command posts a type={want_type} reply, found type={report['type']}")
    if report["ok"] and want_phase and report["fields"].get("phase") != want_phase:
        report["ok"] = False
        report["problems"].append(f"this command posts a phase={want_phase} reply")
    return report


def pr_head(a):
    pr = read_json(f"repos/{a.repo}/pulls/{a.pr}", getattr(a, "fixtures", None), "pr.json")
    return pr, (pr.get("head") or {}).get("sha")


def checked_post(a, plan, add, remove, want_type, expect_from="code", want_phase=None):
    report = read_reply(a, add, want_type, expect_from, want_phase)
    if not report["ok"]:
        return 1, report
    post_comment(a.repo, a.issue, a.file, a.dry_run, plan)
    remove_labels(a.repo, a.issue, remove, a.dry_run, plan)
    add_label(a.repo, a.issue, add, a.dry_run, plan)
    return 0, dict(report, posted=a.issue, label=add)


def cmd_claim(a, plan):
    present = WAITING
    if not a.dry_run:
        raw = gh([f"repos/{a.repo}/issues/{a.issue}", "--jq", "[.labels[].name]"], False, plan)
        labels = json.loads(raw or "[]")
        if "code-working" in labels:
            return 3, {"ok": False, "problem": "already claimed (code-working is set); do nothing"}
        present = [l for l in WAITING if l in labels]
    add_label(a.repo, a.issue, "code-working", a.dry_run, plan)
    remove_labels(a.repo, a.issue, present, a.dry_run, plan)
    return 0, {"ok": True, "claimed": a.issue}


def cmd_reply(a, plan):
    if a.add not in HANDOFF:
        return 1, {"ok": False, "problems": [f"--add must be one of {sorted(HANDOFF)}"]}
    return checked_post(a, plan, a.add, ["code-working"], None)


def cmd_post_plan(a, plan):
    return checked_post(a, plan, "awaiting-approval", ["code-working", "to-code", "needs-leo"], "plan",
                        expect_from=a.sender)


def cmd_ready_for_review(a, plan):
    report = read_reply(a, "to-review", "result", "code", want_phase="2")
    if not report["ok"]:
        return 1, report
    _, head = pr_head(a)
    f = report["fields"]
    if f.get("pr") != str(a.pr) or f.get("head") != head:
        return 1, dict(report, ok=False, problems=[f"header must name pr={a.pr} head={head} (the PR's current head)"])
    post_comment(a.repo, a.issue, a.file, a.dry_run, plan)
    remove_labels(a.repo, a.issue, ["code-working", "awaiting-approval", "needs-leo", "reviewed"], a.dry_run, plan)
    add_label(a.repo, a.issue, "to-review", a.dry_run, plan)
    return 0, dict(report, posted=a.issue, label="to-review")


def cmd_verdict(a, plan):
    report = read_reply(a, "reviewed", "verdict", "lead")
    if not report["ok"]:
        return 1, report
    _, head = pr_head(a)
    f = report["fields"]
    if f.get("pr") != str(a.pr) or f.get("head") != head:
        return 1, dict(report, ok=False, problems=[f"the verdict must name pr={a.pr} head={head}; the PR moved, "
                                                    "so review the new head"])
    post_comment(a.repo, a.issue, a.file, a.dry_run, plan)
    remove_labels(a.repo, a.issue, ["code-working", "to-review"], a.dry_run, plan)
    add_label(a.repo, a.issue, "reviewed", a.dry_run, plan)
    return 0, dict(report, posted=a.issue, label="reviewed", verdict=f.get("verdict"))


def cmd_relay_approval(a, plan):
    quote = " ".join(a.quote.split())
    if not quote:
        return 1, {"ok": False, "problems": ["quote Leo's own words from the chat"]}
    body = (f"<!-- loop:v1 from=lead type=approval turn={a.turn} -->\n"
            f"APPROVED by Leo in chat on {datetime.date.today().isoformat()}: “{quote}”\n")
    report = check(body, a.turn, None, None, expect_from="lead")
    if not report["ok"]:
        return 1, report
    post_text(a.repo, a.issue, body, a.dry_run, plan)
    return 0, {"ok": True, "relayed": a.issue, "comment": body}


def cmd_finish(a, plan):
    code, out = checked_post(a, plan, "done", ["code-working", "awaiting-approval", "needs-leo", "to-review",
                                               "reviewed"], "summary")
    if code == 0:
        gh(["-X", "PATCH", f"repos/{a.repo}/issues/{a.issue}", "-f", "state=closed", "-f", "state_reason=completed"],
           a.dry_run, plan)
        out["closed"] = True
    return code, out


def cmd_reopen(a, plan):
    issue_ = read_json(f"repos/{a.repo}/issues/{a.issue}", a.fixtures, "issue.json")
    labels = {l["name"] if isinstance(l, dict) else l for l in issue_.get("labels") or []}
    if "done" in labels or issue_.get("state_reason") == "not_planned":
        return 1, {"ok": False, "problem": "this issue is done or was closed as not planned; leave it closed"}
    if issue_.get("state") == "open":
        return 0, {"ok": True, "reopened": a.issue, "already_open": True}
    gh(["-X", "PATCH", f"repos/{a.repo}/issues/{a.issue}", "-f", "state=open"], a.dry_run, plan)
    return 0, {"ok": True, "reopened": a.issue}


def cmd_park(a, plan):
    phase = f" phase={a.phase}" if a.phase else ""
    body = f"<!-- loop:v1 from={a.sender} type=question{phase} turn={a.turn} -->\nPaused: {a.reason.strip()}\n"
    if a.phase:
        body += "Reply `CONTINUE: <answer>` to resume, or `REVISE: <notes>` to change the plan.\n"
    report = check(body, a.turn, ["needs-leo"], ["code-working"], expect_from=a.sender)
    if not report["ok"]:
        return 1, report
    post_text(a.repo, a.issue, body, a.dry_run, plan)
    remove_labels(a.repo, a.issue, ["to-code", "code-working", "awaiting-approval", "to-review", "reviewed"],
                  a.dry_run, plan)
    add_label(a.repo, a.issue, "needs-leo", a.dry_run, plan)
    return 0, {"ok": True, "parked": a.issue, "comment": body}


def checks_on(a, sha):
    runs = read_json(f"repos/{a.repo}/commits/{sha}/check-runs?per_page=100", a.fixtures, "checks.json",
                     default={"check_runs": []}).get("check_runs", [])
    status = read_json(f"repos/{a.repo}/commits/{sha}/status", a.fixtures, "status.json",
                       default={"state": "pending", "total_count": 0})
    return runs, status


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
    review = review_status(issue, a.owner, head.get("sha"))
    if not review["approved"]:
        return 4, {"ok": False, "problem": f"not merging: {review['reason']}"}

    runs, status = checks_on(a, head.get("sha"))
    bad = [f"{r.get('name')}={r.get('conclusion') or r.get('status')}" for r in runs
           if r.get("status") != "completed" or r.get("conclusion") not in GOOD]
    if status.get("total_count", 0) and status.get("state") != "success":
        bad.append(f"commit status={status.get('state')}")
    if bad:
        return 6, {"ok": False, "problem": "not merging: checks not green: " + ", ".join(bad)}
    if a.require_checks and not runs and not status.get("total_count", 0):
        return 6, {"ok": False, "problem": "not merging: the plan requires CI checks and none reported on this head"}

    problems = []
    if pr.get("state") != "open" or pr.get("merged"):
        problems.append("PR is not open")
    if pr.get("draft"):
        problems.append("PR is a draft")
    if not str(head.get("ref", "")).startswith("claude/"):
        problems.append("PR head is not a claude/ branch")
    if (pr.get("base") or {}).get("ref") != a.base:
        problems.append(f"PR base is not {a.base}")
    if pr.get("mergeable") is not True or pr.get("mergeable_state") not in ("clean", "has_hooks"):
        problems.append(f"PR is not cleanly mergeable (mergeable={pr.get('mergeable')}, "
                        f"state={pr.get('mergeable_state')})")
    if problems:
        return 5, {"ok": False, "problem": "not merging: " + "; ".join(problems)}

    raw = gh(["-X", "PUT", f"repos/{a.repo}/pulls/{a.pr}/merge", "-f", f"merge_method={a.method}",
              "-f", f"sha={head['sha']}"], a.dry_run, plan)
    result = json.loads(raw) if raw else {}
    return 0, {"ok": True, "approval": approval["reason"], "review": review["reason"],
               "checks": len(runs) + status.get("total_count", 0), "merged": result.get("merged", a.dry_run),
               "merge_sha": result.get("sha"), "head_sha": head["sha"]}


def cmd_verify(a, plan):
    pr = read_json(f"repos/{a.repo}/pulls/{a.pr}", a.fixtures, "pr.json")
    sha, base = pr.get("merge_commit_sha"), (pr.get("base") or {}).get("ref", "main")
    out = {"merged": bool(pr.get("merged")), "merge_sha": sha, "base": base}
    if not out["merged"] or not sha:
        return 7, dict(out, ok=False, problem="the PR is not merged")
    cmp_ = read_json(f"repos/{a.repo}/compare/{sha}...{base}", a.fixtures, "compare.json")
    out["on_base"] = cmp_.get("status") in ("identical", "ahead")
    runs, status = checks_on(a, sha)
    out["post_merge_checks"] = [f"{r.get('name')}={r.get('conclusion') or r.get('status')}" for r in runs]
    if status.get("total_count", 0):
        out["post_merge_checks"].append(f"commit status={status.get('state')}")
    out["ok"] = out["on_base"]
    return (0 if out["ok"] else 7), out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    names = ("claim", "reply", "park", "post-plan", "ready-for-review", "verdict", "relay-approval",
             "merge", "verify", "finish", "reopen")
    for name in names:
        p = sub.add_parser(name)
        p.add_argument("--repo", required=True)
        p.add_argument("--issue", type=int, required=True)
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--fixtures", default=None)
        if name in ("reply", "post-plan", "ready-for-review", "verdict", "finish"):
            p.add_argument("--file", required=True)
            p.add_argument("--turn", type=int, required=True)
        if name in ("ready-for-review", "verdict", "merge", "verify"):
            p.add_argument("--pr", type=int, required=True)
        if name == "reply":
            p.add_argument("--add", required=True)
        if name in ("park", "post-plan"):
            p.add_argument("--from", dest="sender", choices=("code", "lead"),
                           default="lead" if name == "post-plan" else "code")
        if name == "park":
            p.add_argument("--turn", type=int, required=True)
            p.add_argument("--reason", required=True)
            p.add_argument("--phase", type=int, choices=(1, 2), default=None)
        if name == "relay-approval":
            p.add_argument("--turn", type=int, required=True)
            p.add_argument("--quote", required=True)
        if name == "merge":
            p.add_argument("--owner", required=True)
            p.add_argument("--method", choices=("merge", "squash", "rebase"), default="merge")
            p.add_argument("--base", default="main")
            p.add_argument("--require-checks", action="store_true")
    a = ap.parse_args()

    commands = {"claim": cmd_claim, "reply": cmd_reply, "park": cmd_park, "post-plan": cmd_post_plan,
                "ready-for-review": cmd_ready_for_review, "verdict": cmd_verdict,
                "relay-approval": cmd_relay_approval, "merge": cmd_merge, "verify": cmd_verify,
                "finish": cmd_finish, "reopen": cmd_reopen}
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
