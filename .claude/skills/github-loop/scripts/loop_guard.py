#!/usr/bin/env python3
"""Decide whether the Code-side executor may act on a GitHub issue.

Deterministic and offline. Reads an issue JSON file (REST shape, or the older
`gh issue view --json` shape) plus its comments and prints one JSON object with
action = proceed | needs-leo | ignore.

Two modes, picked from the issue body:
- classic: a chat-written task with ## Goal and ## Acceptance criteria. Turn cap 4.
- autopilot: the request has "Phase 1" and "Phase 2" headings (## or ###). The executor
  writes a plan, waits for the owner's APPROVED comment, then builds, tests and merges.
  A proceed result carries work_type = plan | revise | build | continue and phase = 1 | 2.

Owner keywords (autopilot only): a comment by the repo owner that STARTS with
`APPROVED`, `REVISE: <notes>` or `CONTINUE: <answer>`, in capitals, posted after the
executor's latest reply. Executor replies are posted from the owner's account too, but
they always start with a loop:v1 header, so they can never be read as a keyword.
"""
import argparse
import json
import re
import sys

HEADER = re.compile(r"<!--\s*loop:v1\s+([^>]*?)-->")
KEYWORD = re.compile(r"\A\s*(APPROVED\b|REVISE:|CONTINUE:)\s*(.*)\Z", re.DOTALL)
PHASE1 = re.compile(r"^#{2,3}\s*Phase 1\b", re.MULTILINE)
PHASE2 = re.compile(r"^#{2,3}\s*Phase 2\b", re.MULTILINE)


def login(value):
    if isinstance(value, dict):
        return value.get("login", "")
    return value or ""


def label_names(labels):
    return {(l.get("name") if isinstance(l, dict) else l) for l in labels or []}


def fields_of(raw):
    return dict(kv.split("=", 1) for kv in raw.split() if "=" in kv)


def headers(text):
    return [fields_of(m.group(1)) for m in HEADER.finditer(text or "")]


def section(text, name):
    """Return the non-empty text under a '## name' heading, or ''."""
    pattern = r"^##\s*" + re.escape(name) + r"\s*$(.*?)(?=^##\s|\Z)"
    m = re.search(pattern, text or "", re.IGNORECASE | re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


def is_autopilot(body):
    return bool(PHASE1.search(body or "") and PHASE2.search(body or ""))


def is_owner(message, owner):
    if login(message.get("user")).lower() != owner.lower():
        return False
    return message.get("author_association") in (None, "", "OWNER")


def thread(issue):
    """The issue body, then its comments, each as {user, author_association, body, is_body}."""
    msgs = [{"user": issue.get("user") or issue.get("author"),
             "author_association": issue.get("author_association") or issue.get("authorAssociation"),
             "body": issue.get("body") or "", "is_body": True}]
    for c in issue.get("comments") or []:
        msgs.append({"user": c.get("user") or c.get("author"),
                     "author_association": c.get("author_association") or c.get("authorAssociation"),
                     "body": c.get("body") or "", "is_body": False})
    return msgs


def count_turns(msgs, owner):
    """Highest turn number seen. An owner `type=reset` header restarts the count."""
    turns, reset_seen = [], False
    for m in msgs:
        for h in headers(m["body"]):
            if h.get("type") == "reset" and is_owner(m, owner):
                turns, reset_seen = [], True
            elif str(h.get("turn", "")).isdigit():
                turns.append(int(h["turn"]))
    return max(turns) if turns else (0 if reset_seen else 1)  # a bare pasted issue counts as turn 1


def executor_replies(msgs, owner):
    """(index, header) for comments posted from the owner account whose first line is a from=code header."""
    found = []
    for i, m in enumerate(msgs):
        if m["is_body"] or not is_owner(m, owner):
            continue
        first = HEADER.match(m["body"].lstrip())
        if first and fields_of(first.group(1)).get("from") == "code":
            found.append((i, fields_of(first.group(1))))
    return found


def owner_keywords(msgs, owner, after):
    """Owner keyword comments with index > after, oldest first."""
    found = []
    for i in range(after + 1, len(msgs)):
        m = msgs[i]
        if m["is_body"] or not is_owner(m, owner):
            continue
        k = KEYWORD.match(m["body"])
        if k:
            found.append({"keyword": k.group(1).rstrip(":"), "text": k.group(2).strip(), "index": i})
    return found


def approval_status(issue, owner):
    """Is the latest plan approved? Used by loop_gh.py merge as an independent check."""
    msgs = thread(issue)
    plan_idx = max((i for i, h in executor_replies(msgs, owner) if h.get("type") == "plan"), default=None)
    if plan_idx is None:
        return {"approved": False, "reason": "no plan reply on the issue"}
    kws = owner_keywords(msgs, owner, plan_idx)
    if not any(k["keyword"] == "APPROVED" for k in kws):
        return {"approved": False, "reason": "no owner APPROVED after the latest plan"}
    if kws[-1]["keyword"] == "REVISE":
        return {"approved": False, "reason": "the owner asked for a revision after approving"}
    return {"approved": True, "reason": "owner APPROVED the latest plan"}


def decide_classic(issue, owner, max_turn, labeled_by=None):
    labels = label_names(issue.get("labels"))
    issue_author = login(issue.get("author") or issue.get("user"))
    msgs = thread(issue)
    current = count_turns(msgs, owner)
    result = {"mode": "classic", "current_turn": current, "next_turn": current + 1}

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

    # The latest task written by the chat side (or the pasted issue body).
    task_messages, chat_text = [], ""
    for m in msgs:
        hs = headers(m["body"])
        if hs:
            if any(h.get("from") == "chat" and h.get("type") == "task" for h in hs):
                task_messages.append(m["body"])
                chat_text += "\n" + m["body"]
        elif m["is_body"]:
            task_messages.append(m["body"])
            chat_text += "\n" + m["body"]
    latest = task_messages[-1] if task_messages else ""
    if not section(latest, "Goal"):
        return out("needs-leo", "the latest task has no Goal section; ask instead of guessing")
    if not section(chat_text, "Acceptance criteria"):
        return out("needs-leo", "no Acceptance criteria anywhere in the thread; ask instead of guessing")
    return out("proceed", "all guards passed")


def decide_autopilot(issue, owner, labeled_by=None, max_replies=10, max_revisions=3):
    labels = label_names(issue.get("labels"))
    issue_author = login(issue.get("author") or issue.get("user"))
    msgs = thread(issue)
    current = count_turns(msgs, owner)
    replies = executor_replies(msgs, owner)
    reset_at = max((i for i, m in enumerate(msgs)
                    if is_owner(m, owner) and any(h.get("type") == "reset" for h in headers(m["body"]))), default=-1)
    live = [h for i, h in replies if i > reset_at]
    plans = [h for h in live if h.get("type") == "plan"]
    last = replies[-1][1] if replies else None
    kws = owner_keywords(msgs, owner, replies[-1][0] if replies else 0)
    kw = kws[-1] if kws else None
    result = {"mode": "autopilot", "current_turn": current, "next_turn": current + 1}

    def out(action, reason, **extra):
        result.update(action=action, reason=reason, **extra)
        return result

    def work(kind, phase, notes=""):
        if len(live) >= max_replies:
            return out("needs-leo", f"reply cap reached ({len(live)} of {max_replies} executor replies); "
                       "a human should review this thread", phase=phase)
        rtype = "plan" if phase == 1 else "summary"
        return out("proceed", f"{kind} (phase {phase})", work_type=kind, phase=phase, notes=notes,
                   reply_header=f"<!-- loop:v1 from=code type={rtype} phase={phase} turn={current + 1} -->")

    def revise(notes):
        if len(plans) >= 1 + max_revisions:
            return out("needs-leo", f"revision cap reached ({len(plans) - 1} of {max_revisions} revisions)", phase=1)
        return work("revise", 1, notes)

    if issue_author.lower() != owner.lower():
        return out("ignore", "issue author is not the repo owner")
    if "done" in labels:
        return out("ignore", "issue is done")
    if "code-working" in labels:
        return out("ignore", "already claimed by a running executor")
    if "to-code" in labels:
        if labeled_by and labeled_by.lower() != owner.lower():
            return out("ignore", "label was not applied by the repo owner")
        if len(plans) >= 1 + max_revisions:
            return out("needs-leo", f"revision cap reached ({len(plans) - 1} of {max_revisions} revisions)", phase=1)
        return work("plan", 1)
    if "awaiting-approval" in labels:
        if not last or last.get("type") != "plan":
            return out("ignore", "awaiting-approval, but the latest executor reply is not a plan")
        if kw and kw["keyword"] == "APPROVED":
            return work("build", 2)
        if kw and kw["keyword"] == "REVISE":
            return revise(kw["text"])
        return out("ignore", "waiting for the owner's APPROVED or REVISE:")
    if "needs-leo" in labels:
        if kw and kw["keyword"] == "CONTINUE":
            raw = str((last or {}).get("phase", "1"))
            return work("continue", int(raw) if raw in ("1", "2") else 1, kw["text"])
        if kw and kw["keyword"] == "REVISE":
            return revise(kw["text"])
        return out("ignore", "parked; waiting for the owner's CONTINUE: or REVISE:")
    return out("ignore", "no loop label")


def decide(issue, owner, max_turn=4, labeled_by=None, max_replies=10, max_revisions=3):
    if is_autopilot(issue.get("body")):
        return decide_autopilot(issue, owner, labeled_by, max_replies, max_revisions)
    return decide_classic(issue, owner, max_turn, labeled_by)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("issue_json")
    ap.add_argument("--owner", required=True, help="login of the repo owner")
    ap.add_argument("--comments", default=None, help="JSON array of issue comments (REST shape), if not inside the issue file")
    ap.add_argument("--max-turn", type=int, default=4, help="classic mode turn cap")
    ap.add_argument("--max-replies", type=int, default=10, help="autopilot executor reply cap")
    ap.add_argument("--max-revisions", type=int, default=3, help="autopilot plan revision cap")
    ap.add_argument("--labeled-by", default=None, help="login of whoever applied the label, if known")
    args = ap.parse_args()
    with open(args.issue_json, encoding="utf-8") as f:
        issue = json.load(f)
    if args.comments:
        with open(args.comments, encoding="utf-8") as f:
            issue["comments"] = json.load(f)
    result = decide(issue, args.owner, args.max_turn, args.labeled_by, args.max_replies, args.max_revisions)
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
