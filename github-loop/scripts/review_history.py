#!/usr/bin/env python3
"""Read the review history that the review score needs (read-only).

    review_history.py --repo <owner>/<repo> --issue N > history.json
    route.py --step review --git-range origin/main...<head> --history history.json ...

Prints one JSON object:
  changes_requested  true when a Lead verdict after the latest plan on this issue requested changes;
                     null when the issue could not be read
  defects            post-merge defects: owner issues labeled `bug` or `defect` that name a merged
                     loop PR (`#N`, a PR from a configured branch prefix) and were opened within 14
                     days of that merge, as {pr, merged_at, opened_at, files}; null when they could
                     not be read, which the score reports as "defect history unknown"
  errors             what could not be read

Only numbers and file names leave this script: a defect issue's text is read to find `#N` and is
never printed. Bounded: the newest 100 issues per label and at most 10 referenced PRs.
Exit 0 (an unreadable part is null, never a guess), or 2 on bad input.
Test without the network: --fixtures DIR with issue.json, comments.json, bug.json, defect.json,
pr<N>.json and pr<N>.files.json.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as loop_config  # noqa: E402
from ghapi import ApiError, from_fixture, get_all, get_json  # noqa: E402
from loop_guard import login, review_history, set_owner_associations, thread  # noqa: E402
from pick_model import DEFECT_DAYS, _days  # noqa: E402

DEFECT_LABELS = ("bug", "defect")
MAX_PRS = 10
REF = re.compile(r"(?<![\w/])#(\d+)\b")


def read(path, fixtures, name, default=None, many=False):
    if fixtures:
        return from_fixture(fixtures, name, default)
    return get_all(path) if many else get_json(path)


def changes_requested(repo, issue_no, owner, fixtures):
    issue = read(f"repos/{repo}/issues/{issue_no}", fixtures, "issue.json")
    issue["comments"] = read(f"repos/{repo}/issues/{issue_no}/comments", fixtures, "comments.json", [], many=True)
    _, verdicts = review_history(thread(issue), owner)
    return any(h.get("verdict") == "changes" for _, h in verdicts)


def defects(repo, owner, prefixes, fixtures):
    found, seen, prs = [], set(), {}
    for label in DEFECT_LABELS:
        issues = read(f"repos/{repo}/issues?labels={label}&state=all&sort=created&direction=desc&per_page=100",
                      fixtures, f"{label}.json", [])
        for issue in issues:
            if "pull_request" in issue or login(issue.get("user")).lower() != owner.lower():
                continue
            text = f"{issue.get('title') or ''}\n{issue.get('body') or ''}"
            for number in dict.fromkeys(int(n) for n in REF.findall(text)):
                key = (issue.get("number"), number)
                if key in seen or (number not in prs and len(prs) >= MAX_PRS):
                    continue
                seen.add(key)
                if number not in prs:
                    try:
                        prs[number] = read(f"repos/{repo}/pulls/{number}", fixtures, f"pr{number}.json", {})
                    except ApiError as e:
                        if not re.search(r"\b404\b|Not Found", str(e)):
                            raise
                        prs[number] = {}  # `#N` names an issue, not a pull request
                pr = prs[number]
                merged_at = pr.get("merged_at")
                ref = str((pr.get("head") or {}).get("ref", ""))
                if not merged_at or not ref.startswith(prefixes):
                    continue
                opened = issue.get("created_at")
                try:
                    age = _days(merged_at, opened)
                except (TypeError, ValueError):
                    continue
                if not 0 <= age <= DEFECT_DAYS:
                    continue
                files = read(f"repos/{repo}/pulls/{number}/files", fixtures, f"pr{number}.files.json", [], many=True)
                found.append({"pr": number, "merged_at": merged_at, "opened_at": opened,
                              "files": [f.get("filename", "") for f in files]})
    return found


def history(repo, issue_no, owner, cfg, fixtures=None):
    out = {"changes_requested": None, "defects": None, "errors": []}
    try:
        out["changes_requested"] = changes_requested(repo, issue_no, owner, fixtures)
    except (ApiError, KeyError, TypeError) as e:
        out["errors"].append(f"issue {issue_no}: {str(e)[:200]}")
    try:
        out["defects"] = defects(repo, owner, loop_config.prefixes(cfg), fixtures)
    except (ApiError, KeyError, TypeError) as e:
        out["errors"].append(f"defects: {str(e)[:200]}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--issue", type=int, required=True)
    ap.add_argument("--owner", default=None)
    ap.add_argument("--config", default=None)
    ap.add_argument("--fixtures", default=None)
    a = ap.parse_args()
    try:
        cfg = loop_config.load(a.config)
        set_owner_associations(cfg["owner_associations"])
        owner = loop_config.resolve_owner(a.repo, a.owner, cfg, a.fixtures)
    except (ApiError, ValueError) as e:
        json.dump({"ok": False, "error": str(e)}, sys.stdout, indent=2)
        print()
        sys.exit(2)
    json.dump(history(a.repo, a.issue, owner, cfg, a.fixtures), sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
