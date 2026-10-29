#!/usr/bin/env python3
"""Decide whether the Code-side executor may act on a GitHub issue.

Deterministic and offline: it reads an issue JSON file (the shape produced by
`gh issue view --json number,labels,author,body,comments`) and prints one JSON
object with action = proceed | needs-leo | ignore.
"""
import argparse
import json
import re
import sys

HEADER = re.compile(r"<!--\s*loop:v1\s+([^>]*?)-->")


def login(value):
    if isinstance(value, dict):
        return value.get("login", "")
    return value or ""


def label_names(labels):
    return {(l.get("name") if isinstance(l, dict) else l) for l in labels or []}


def headers(text):
    found = []
    for m in HEADER.finditer(text or ""):
        fields = dict(kv.split("=", 1) for kv in m.group(1).split() if "=" in kv)
        found.append(fields)
    return found


def section(text, name):
    """Return the non-empty text under a '## name' heading, or ''."""
    pattern = r"^##\s*" + re.escape(name) + r"\s*$(.*?)(?=^##\s|\Z)"
    m = re.search(pattern, text or "", re.IGNORECASE | re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


def decide(issue, owner, max_turn, labeled_by=None):
    labels = label_names(issue.get("labels"))
    # Accept both the `gh issue view --json` shape (author) and the REST shape (user).
    issue_author = login(issue.get("author") or issue.get("user"))
    messages = [{"author": issue_author, "body": issue.get("body") or "", "is_body": True}]
    for c in issue.get("comments") or []:
        messages.append({"author": login(c.get("author") or c.get("user")), "body": c.get("body") or "", "is_body": False})

    # Count turns in order. A "type=reset" header posted by the repo owner restarts the
    # count, so Leo can let a capped thread continue by commenting
    # <!-- loop:v1 from=human type=reset turn=0 -->
    turns = []
    reset_seen = False
    for m in messages:
        for h in headers(m["body"]):
            if h.get("type") == "reset" and login(m["author"]).lower() == owner.lower():
                turns, reset_seen = [], True
            elif str(h.get("turn", "")).isdigit():
                turns.append(int(h["turn"]))
    current = max(turns) if turns else (0 if reset_seen else 1)  # a bare pasted issue counts as turn 1
    result = {"current_turn": current, "next_turn": current + 1}

    def out(action, reason):
        result.update(action=action, reason=reason)
        if action == "proceed":
            result["reply_header"] = f"<!-- loop:v1 from=code type=result turn={current + 1} -->"
        return result

    if labels & {"needs-leo", "done"}:
        return out("ignore", "issue is parked (needs-leo or done)")
    if "to-code" not in labels:
        return out("ignore", "no to-code label")
    if "code-working" in labels:
        return out("ignore", "already claimed by a running executor")
    if issue_author.lower() != owner.lower():
        return out("ignore", "issue author is not the repo owner")
    if labeled_by and labeled_by.lower() != owner.lower():
        return out("ignore", "label was not applied by the repo owner")
    if current >= max_turn:
        return out("needs-leo", f"turn cap reached ({current} of {max_turn}); a human should review this thread")

    # Find the latest task message written by the chat side.
    task_messages = []
    chat_text = ""
    for m in messages:
        hs = headers(m["body"])
        if hs:
            if any(h.get("from") == "chat" and h.get("type") == "task" for h in hs):
                task_messages.append(m["body"])
                chat_text += "\n" + m["body"]
        elif m["is_body"]:
            task_messages.append(m["body"])  # pasted issue without a header
            chat_text += "\n" + m["body"]
    latest = task_messages[-1] if task_messages else ""
    if not section(latest, "Goal"):
        return out("needs-leo", "the latest task has no Goal section; ask instead of guessing")
    if not section(chat_text, "Acceptance criteria"):
        return out("needs-leo", "no Acceptance criteria anywhere in the thread; ask instead of guessing")
    return out("proceed", "all guards passed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("issue_json")
    ap.add_argument("--owner", required=True, help="login of the repo owner")
    ap.add_argument("--comments", default=None, help="JSON array of issue comments (REST shape), if not inside the issue file")
    ap.add_argument("--max-turn", type=int, default=4)
    ap.add_argument("--labeled-by", default=None, help="login of whoever applied the label, if known")
    args = ap.parse_args()
    with open(args.issue_json, encoding="utf-8") as f:
        issue = json.load(f)
    if args.comments:
        with open(args.comments, encoding="utf-8") as f:
            issue["comments"] = json.load(f)
    json.dump(decide(issue, args.owner, args.max_turn, args.labeled_by), sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
