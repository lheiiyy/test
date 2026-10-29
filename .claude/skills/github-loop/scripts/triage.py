#!/usr/bin/env python3
"""Read-only hourly check for the github-loop executor.

One command replaces the "list issues, fetch comments, run the guard" steps, so an
idle scheduled run costs almost no tokens: if `work` is empty, the run just says
"No new work." and stops.

    python scripts/triage.py --repo lheiiyy/test --owner lheiiyy

Prints one JSON object:
  work       issues that passed every guard (oldest first), each with next_turn and reply_header
  needs_leo  to-code issues the guard parked (turn cap, missing Goal or Acceptance criteria)
  stale      issues stuck on code-working longer than --stale-minutes (a crashed run)
  ignored    to-code issues skipped, with the reason
  summary    "No new work." or a one-line count

It also finds who applied the to-code label (from the issue events), so the
owner-only label check works in scheduled runs where no event payload exists.

Exit codes: 0 ok (including "No new work."), 2 API or input failure. A failure is never
reported as "No new work.", so a broken token cannot look like an idle queue.

Test without the network: --fixtures DIR with issues.json, <N>.comments.json, <N>.events.json.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from loop_guard import decide  # noqa: E402


class ApiError(Exception):
    pass


def fetch(path, fixtures, fixture_name):
    """Return parsed JSON for a REST path, or for a fixture file when --fixtures is set."""
    if fixtures:
        full = os.path.join(fixtures, fixture_name)
        if not os.path.exists(full):
            return []  # a missing fixture means "no comments / no events"
        with open(full, encoding="utf-8") as f:
            return json.load(f)
    proc = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if proc.returncode != 0:
        raise ApiError(f"gh api {path} failed: {(proc.stderr or proc.stdout).strip()[:300]}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise ApiError(f"gh api {path} returned non-JSON: {e}")


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def latest_label_event(events, label):
    """Return the newest `labeled` event for this label, or None."""
    found = [e for e in events if e.get("event") == "labeled" and (e.get("label") or {}).get("name") == label]
    return max(found, key=lambda e: e.get("created_at", ""), default=None)


def triage(repo, owner, max_turn, stale_minutes, now, fixtures):
    issues = fetch(f"repos/{repo}/issues?state=open&per_page=100", fixtures, "issues.json")
    result = {"repo": repo, "owner": owner, "work": [], "needs_leo": [], "stale": [], "ignored": []}

    for issue in sorted(issues, key=lambda i: i["number"]):
        if "pull_request" in issue:
            continue  # the issues endpoint also returns PRs
        number = issue["number"]
        labels = {l["name"] if isinstance(l, dict) else l for l in issue.get("labels") or []}
        if not labels & {"to-code", "code-working"}:
            continue
        comments = fetch(f"repos/{repo}/issues/{number}/comments?per_page=100", fixtures, f"{number}.comments.json")
        events = fetch(f"repos/{repo}/issues/{number}/events?per_page=100", fixtures, f"{number}.events.json")
        issue = dict(issue, comments=comments)

        if "code-working" in labels:
            claim = latest_label_event(events, "code-working")
            started = parse_time(claim["created_at"]) if claim else parse_time(issue["updated_at"])
            minutes = int((now - started).total_seconds() // 60)
            if minutes >= stale_minutes:
                turn_info = decide(issue, owner, max_turn)
                result["stale"].append({"number": number, "title": issue.get("title", ""),
                                        "minutes": minutes, "next_turn": turn_info["next_turn"]})
            else:
                result["ignored"].append({"number": number, "reason": f"claimed {minutes} min ago, still running"})
            continue

        event = latest_label_event(events, "to-code")
        labeled_by = ((event or {}).get("actor") or {}).get("login")
        decision = decide(issue, owner, max_turn, labeled_by)
        entry = {"number": number, "title": issue.get("title", ""), "labeled_by": labeled_by}
        if decision["action"] == "proceed":
            result["work"].append(dict(entry, next_turn=decision["next_turn"], reply_header=decision["reply_header"]))
        elif decision["action"] == "needs-leo":
            result["needs_leo"].append(dict(entry, next_turn=decision["next_turn"], reason=decision["reason"]))
        else:
            result["ignored"].append(dict(entry, reason=decision["reason"]))

    parts = []
    if result["work"]:
        parts.append(f"{len(result['work'])} to do")
    if result["needs_leo"]:
        parts.append(f"{len(result['needs_leo'])} need Leo")
    if result["stale"]:
        parts.append(f"{len(result['stale'])} stale")
    result["summary"] = ", ".join(parts) if parts else "No new work."
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--owner", required=True, help="login of the repo owner")
    ap.add_argument("--max-turn", type=int, default=4)
    ap.add_argument("--stale-minutes", type=int, default=90)
    ap.add_argument("--fixtures", default=None, help="directory of JSON fixtures instead of the network")
    ap.add_argument("--now", default=None, help="ISO time to treat as now (for tests)")
    args = ap.parse_args()

    now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    try:
        result = triage(args.repo, args.owner, args.max_turn, args.stale_minutes, now, args.fixtures)
    except (ApiError, KeyError, ValueError) as e:
        json.dump({"error": str(e), "summary": "TRIAGE FAILED, not an empty queue"}, sys.stdout, indent=2)
        print()
        sys.exit(2)
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
