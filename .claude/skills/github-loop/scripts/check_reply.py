#!/usr/bin/env python3
"""Check an executor reply before it is posted to a GitHub issue.

Usage: check_reply.py reply.md --turn N --add to-chat --remove code-working
Prints a JSON report and exits 1 if anything is wrong.
"""
import argparse
import json
import re
import sys

HEADER = re.compile(r"<!--\s*loop:v1\s+([^>]*?)-->")
URL = re.compile(r"https?://\S+")
ALLOWED_ADD = {"to-chat", "needs-leo", "done"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reply")
    ap.add_argument("--turn", type=int, required=True)
    ap.add_argument("--add", action="append", default=[])
    ap.add_argument("--remove", action="append", default=[])
    ap.add_argument("--max-words", type=int, default=150)
    args = ap.parse_args()

    text = open(args.reply, encoding="utf-8").read()
    problems = []

    m = HEADER.search(text)
    if not m:
        problems.append("missing <!-- loop:v1 ... --> header")
    else:
        fields = dict(kv.split("=", 1) for kv in m.group(1).split() if "=" in kv)
        if fields.get("from") != "code":
            problems.append("header must say from=code")
        if fields.get("turn") != str(args.turn):
            problems.append(f"header turn must be {args.turn}, found {fields.get('turn')}")
        if fields.get("type") not in {"result", "question", "status"}:
            problems.append("header type must be result, question or status")

    body = URL.sub("", HEADER.sub("", text))
    words = len(body.split())
    if words > args.max_words:
        problems.append(f"{words} words; limit is {args.max_words}")

    if "to-code" in args.add:
        problems.append("the executor must never add to-code")
    if not set(args.add) & ALLOWED_ADD:
        problems.append("add exactly one of to-chat, needs-leo, done")
    if len(set(args.add) & ALLOWED_ADD) > 1:
        problems.append("add only one hand-off label")
    if "code-working" not in args.remove:
        problems.append("remove code-working when replying")

    json.dump({"ok": not problems, "words": words, "problems": problems}, sys.stdout, indent=2)
    print()
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
