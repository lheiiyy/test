#!/usr/bin/env python3
"""Read-only hourly check for the github-loop agents.

One command replaces the "list issues, fetch comments, run the guard" steps, so an
idle scheduled run costs almost no tokens: if `work` is empty, the run just says
"No new work." and stops.

    python scripts/triage.py --repo lheiiyy/test --owner lheiiyy --role code
    python scripts/triage.py --repo lheiiyy/test --owner lheiiyy --role lead

--role code  the Engineer: build, fix, merge, continue (phase 2), classic tasks. It also
             parks needs_leo and stale entries.
--role lead  the Technical Lead (Cowork): plan, revise, review, continue (phase 1).
--role all   both (one session doing every role; avoid it when a separate Lead task exists,
             because a review should come from a different session than the build).

Prints one JSON object:
  work       issues for this role that passed every guard (oldest first), each with
             next_turn and reply_header. Autopilot entries also carry work_type, phase,
             role, notes, and for review, fix and merge the pr and head.
  needs_leo  issues the guard parked (caps; missing Goal or Acceptance criteria)
  stale      issues stuck on code-working longer than --stale-minutes, or
             --build-stale-minutes for an approved autopilot build (a crashed run)
  ignored    issues skipped, with the reason (for example "waiting for the owner's APPROVED")

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
from loop_guard import approval_status, decide, is_autopilot  # noqa: E402

LOOP_LABELS = {"to-code", "code-working", "awaiting-approval", "needs-leo", "to-review", "reviewed"}


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


def triage(repo, owner, max_turn, stale_minutes, now, fixtures, build_stale_minutes=180,
           max_replies=20, max_revisions=3, role="code", max_review_rounds=4):
    issues = fetch(f"repos/{repo}/issues?state=open&per_page=100", fixtures, "issues.json")
    result = {"repo": repo, "owner": owner, "role": role, "work": [], "needs_leo": [], "stale": [], "ignored": []}
    parks = role in ("code", "all")

    for issue in sorted(issues, key=lambda i: i["number"]):
        if "pull_request" in issue:
            continue  # the issues endpoint also returns PRs
        number = issue["number"]
        labels = {l["name"] if isinstance(l, dict) else l for l in issue.get("labels") or []}
        autopilot = is_autopilot(issue.get("body"))
        watched = {"to-code", "code-working"} | (LOOP_LABELS if autopilot else set())
        if not labels & watched or "done" in labels:
            continue
        comments = fetch(f"repos/{repo}/issues/{number}/comments?per_page=100", fixtures, f"{number}.comments.json")
        issue = dict(issue, comments=comments)
        needs_events = bool(labels & {"to-code", "code-working"})
        events = fetch(f"repos/{repo}/issues/{number}/events?per_page=100", fixtures,
                       f"{number}.events.json") if needs_events else []

        if "code-working" in labels:
            building = autopilot and approval_status(issue, owner)["approved"]
            limit = build_stale_minutes if building else stale_minutes
            claim = latest_label_event(events, "code-working")
            started = parse_time(claim["created_at"]) if claim else parse_time(issue["updated_at"])
            minutes = int((now - started).total_seconds() // 60)
            if minutes >= limit and parks:
                turn_info = decide(issue, owner, max_turn)
                result["stale"].append({"number": number, "title": issue.get("title", ""), "minutes": minutes,
                                        "next_turn": turn_info["next_turn"], "phase": 2 if building else 1})
            else:
                result["ignored"].append({"number": number, "reason": f"claimed {minutes} min ago, still running"})
            continue

        event = latest_label_event(events, "to-code") if "to-code" in labels else None
        labeled_by = ((event or {}).get("actor") or {}).get("login")
        decision = decide(issue, owner, max_turn, labeled_by, max_replies, max_revisions, max_review_rounds)
        entry = {"number": number, "title": issue.get("title", ""), "labeled_by": labeled_by, "mode": decision["mode"]}
        if decision["action"] == "proceed":
            if role != "all" and decision.get("role", "code") != role:
                result["ignored"].append(dict(entry, reason=f"{decision.get('work_type', 'task')} is "
                                                            f"{decision.get('role')} work"))
                continue
            item = dict(entry, next_turn=decision["next_turn"], reply_header=decision["reply_header"],
                        role=decision.get("role", "code"))
            if autopilot:
                for key in ("work_type", "phase", "notes", "pr", "head", "review_round", "since"):
                    if key in decision:
                        item[key] = decision[key]
            result["work"].append(item)
        elif decision["action"] == "needs-leo":
            target = result["needs_leo"] if parks else result["ignored"]
            target.append(dict(entry, next_turn=decision["next_turn"], reason=decision["reason"],
                               phase=decision.get("phase", 1)))
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
    ap.add_argument("--role", choices=("code", "lead", "all"), default="code")
    ap.add_argument("--max-turn", type=int, default=4, help="classic mode turn cap")
    ap.add_argument("--stale-minutes", type=int, default=90)
    ap.add_argument("--build-stale-minutes", type=int, default=180, help="stale limit for approved autopilot builds")
    ap.add_argument("--max-replies", type=int, default=20, help="autopilot agent reply cap")
    ap.add_argument("--max-revisions", type=int, default=3, help="autopilot plan revision cap")
    ap.add_argument("--max-review-rounds", type=int, default=4, help="autopilot change-request cap")
    ap.add_argument("--fixtures", default=None, help="directory of JSON fixtures instead of the network")
    ap.add_argument("--now", default=None, help="ISO time to treat as now (for tests)")
    args = ap.parse_args()

    now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    try:
        result = triage(args.repo, args.owner, args.max_turn, args.stale_minutes, now, args.fixtures,
                        args.build_stale_minutes, args.max_replies, args.max_revisions, args.role,
                        args.max_review_rounds)
    except (ApiError, KeyError, ValueError) as e:
        json.dump({"error": str(e), "summary": "TRIAGE FAILED, not an empty queue"}, sys.stdout, indent=2)
        print()
        sys.exit(2)
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
