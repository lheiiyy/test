#!/usr/bin/env python3
"""Check an executor reply before it is posted to a GitHub issue.

Usage: check_reply.py reply.md --turn N --add to-chat --remove code-working
Prints a JSON report and exits 1 if anything is wrong.

Also importable: check(text, turn, add, remove, max_words) returns the same report.
"""
import argparse
import json
import re
import sys

HEADER = re.compile(r"<!--\s*loop:v1\s+([^>]*?)-->")
URL = re.compile(r"https?://\S+")
ALLOWED_ADD = {"to-chat", "needs-leo", "done"}


def check(text, turn, add, remove, max_words=150):
    problems = []

    m = HEADER.search(text)
    if not m:
        problems.append("missing <!-- loop:v1 ... --> header")
    else:
        fields = dict(kv.split("=", 1) for kv in m.group(1).split() if "=" in kv)
        if fields.get("from") != "code":
            problems.append("header must say from=code")
        if fields.get("turn") != str(turn):
            problems.append(f"header turn must be {turn}, found {fields.get('turn')}")
        if fields.get("type") not in {"result", "question", "status"}:
            problems.append("header type must be result, question or status")

    body = URL.sub("", HEADER.sub("", text))
    words = len(body.split())
    if words > max_words:
        problems.append(f"{words} words; limit is {max_words}")

    if "to-code" in add:
        problems.append("the executor must never add to-code")
    if not set(add) & ALLOWED_ADD:
        problems.append("add exactly one of to-chat, needs-leo, done")
    if len(set(add) & ALLOWED_ADD) > 1:
        problems.append("add only one hand-off label")
    if "code-working" not in remove:
        problems.append("remove code-working when replying")

    return {"ok": not problems, "words": words, "problems": problems}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reply")
    ap.add_argument("--turn", type=int, required=True)
    ap.add_argument("--add", action="append", default=[])
    ap.add_argument("--remove", action="append", default=[])
    ap.add_argument("--max-words", type=int, default=150)
    args = ap.parse_args()

    with open(args.reply, encoding="utf-8") as f:
        text = f.read()
    report = check(text, args.turn, args.add, args.remove, args.max_words)
    json.dump(report, sys.stdout, indent=2)
    print()
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
