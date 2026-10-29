#!/usr/bin/env python3
"""Check an executor reply before it is posted to a GitHub issue.

Usage: check_reply.py reply.md --turn N --add to-chat --remove code-working
Prints a JSON report and exits 1 if anything is wrong.

Also importable: check(text, turn, add, remove, max_words) returns the same report.

Rules: the loop:v1 header is the FIRST line (so an executor comment can never be read
as an owner keyword such as APPROVED), from=code, the expected turn, a known type
(plan replies say phase=1, summary replies say phase=2), at most 150 words (250 for a
summary), never add to-code, add exactly one hand-off label, and remove code-working.
"""
import argparse
import json
import re
import sys

HEADER = re.compile(r"<!--\s*loop:v1\s+([^>]*?)-->")
URL = re.compile(r"https?://\S+")
ALLOWED_ADD = {"to-chat", "needs-leo", "done", "awaiting-approval"}
TYPES = {"result", "question", "status", "plan", "summary"}
PHASE_FOR_TYPE = {"plan": "1", "summary": "2"}


def check(text, turn, add, remove, max_words=None):
    problems = []
    rtype = None

    m = HEADER.match(text.lstrip())
    if not m:
        problems.append("the first line must be the <!-- loop:v1 ... --> header")
    else:
        fields = dict(kv.split("=", 1) for kv in m.group(1).split() if "=" in kv)
        rtype = fields.get("type")
        if fields.get("from") != "code":
            problems.append("header must say from=code")
        if fields.get("turn") != str(turn):
            problems.append(f"header turn must be {turn}, found {fields.get('turn')}")
        if rtype not in TYPES:
            problems.append("header type must be one of " + ", ".join(sorted(TYPES)))
        elif rtype in PHASE_FOR_TYPE and fields.get("phase") != PHASE_FOR_TYPE[rtype]:
            problems.append(f"a {rtype} reply must say phase={PHASE_FOR_TYPE[rtype]}")

    limit = max_words if max_words is not None else (250 if rtype == "summary" else 150)
    body = URL.sub("", HEADER.sub("", text))
    words = len(body.split())
    if words > limit:
        problems.append(f"{words} words; limit is {limit}")

    if "to-code" in add:
        problems.append("the executor must never add to-code")
    if not set(add) & ALLOWED_ADD:
        problems.append("add exactly one of " + ", ".join(sorted(ALLOWED_ADD)))
    if len(set(add) & ALLOWED_ADD) > 1:
        problems.append("add only one hand-off label")
    if "code-working" not in remove:
        problems.append("remove code-working when replying")

    return {"ok": not problems, "words": words, "type": rtype, "problems": problems}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reply")
    ap.add_argument("--turn", type=int, required=True)
    ap.add_argument("--add", action="append", default=[])
    ap.add_argument("--remove", action="append", default=[])
    ap.add_argument("--max-words", type=int, default=None, help="default 150, or 250 for a summary")
    args = ap.parse_args()

    with open(args.reply, encoding="utf-8") as f:
        text = f.read()
    report = check(text, args.turn, args.add, args.remove, args.max_words)
    json.dump(report, sys.stdout, indent=2)
    print()
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
