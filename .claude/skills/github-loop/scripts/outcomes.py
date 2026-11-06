#!/usr/bin/env python3
"""Collect loop outcomes from the GitHub record, as fixed fields only (read-only).

    outcomes.py --repo <owner>/<repo> [--owner LOGIN] [--limit 50] [--out outcomes.json]

Each autopilot issue by the owner becomes one record built from the loop headers, labels and
counts. Nothing an agent claims is trusted, and no comment text is ever stored, so a secret in a
comment cannot leak into the outcomes. Comments by other accounts are never read; they are only
counted as rejected evidence.

Record fields: number, state, outcome (done | parked | open | closed), plans, revisions, verdicts,
review_rounds, parks, park_reasons (fixed categories), replies, merged, relayed_approval,
model_gaps (Model lines that say a stronger tier was wanted), models (tier per reply type),
risk (the plan's Risk line), rejected_comments, and for review routing v2: review_score (from the
latest verdict's `Why: score N`), why (fixed reason codes), hard_stop (a fixed code), confidence
(high | low, from a sonnet verdict), rechecked, cap_parked (a hold for the Opus cap), areas (the
feature areas of the latest PR's files) and defect_after (a bug or defect issue by the owner named
that PR, in its text or in the loop's "Galing sa #N" note, within 14 days of its summary). `evidence` says which fields are verified
(counted from headers and labels) and which are uncertain (read from free text, such as a park
reason). improve.py turns repeated patterns into proposals; neither script changes anything.
Exit 0, or 2 on an API or input failure.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as loop_config  # noqa: E402
from ghapi import CALLS, ApiError, from_fixture, get_all, get_json  # noqa: E402
from loop_guard import (AGENTS, agent_replies, first_header, is_autopilot, is_owner, is_recheck,  # noqa: E402
                        label_names, login, owner_keywords, set_owner_associations, thread)
from pick_model import DEFECT_DAYS, HARD_STOP_CODES, REASON_CODES, _days  # noqa: E402
from rules import declared_risk, feature_areas, source_files  # noqa: E402

PARK_CATEGORIES = [
    ("stale", r"previous run stopped"),
    ("stalled", r"\bNo (code|lead) run picked up"),
    ("merge_tap", r"Merge needs one tap"),
    ("release", r"Ready to release"),
    ("out_of_scope", r"outside the plan's scope|outside the approved scope|Files in scope"),
    ("high_risk", r"high-risk"),
    ("not_approved", r"not merging: (no owner APPROVED|the owner asked)"),
    ("checks", r"checks not green|requires CI"),
    ("not_mergeable", r"not cleanly mergeable|PR is not open|draft|forks are never|not a \S+ branch|changed files"),
    ("repo_mismatch", r"repo mismatch"),
    ("cap", r"cap reached"),
    ("fix_failed", r"same error|fix attempts|survives"),
    ("scope", r"outside the (approved )?plan|scope"),
    ("dependency", r"dependency|external service|subscription|cost"),
]
MODEL = re.compile(r"(?im)^Model:[ \t]*(haiku|sonnet|opus|fable)\b([^\n]*)$")
FIELDS = {"number": int, "state": str, "outcome": str, "plans": int, "revisions": int, "verdicts": int,
          "review_rounds": int, "parks": int, "park_reasons": list, "replies": int, "merged": bool,
          "relayed_approval": bool, "model_gaps": int, "models": dict, "risk": (str, type(None)),
          "rejected_comments": int, "evidence": dict, "review_score": (int, type(None)), "why": list,
          "hard_stop": (str, type(None)), "confidence": (str, type(None)), "rechecked": bool, "cap_parked": bool,
          "areas": list, "defect_after": bool}
ENUMS = {"state": {"open", "closed"}, "outcome": {"done", "parked", "open", "closed"},
         "risk": {"low", "normal", "high", None}, "confidence": {"high", "low", None},
         "hard_stop": {code for code, _ in HARD_STOP_CODES} | {None}}
WHY_CODES = {code for code, _ in REASON_CODES}
WHY_LINE = re.compile(r"(?im)^Model:[^\n]*?\bWhy:[ \t]*(.+)$")
SCORE = re.compile(r"^score (\d+) \(")
CONFIDENCE = re.compile(r"(?im)^[ \t>*-]*\**Confidence\**[ \t]*:[ \t]*\**[ \t]*(high|low)\b")
AREA = re.compile(r"^[\w.\-/]{1,120}$")
CATEGORY_NAMES = {name for name, _ in PARK_CATEGORIES} | {"other"}
TIER_NAMES = {"haiku", "sonnet", "opus", "fable"}


def park_category(text):
    for name, rx in PARK_CATEGORIES:
        if re.search(rx, text or "", re.I):
            return name
    return "other"


def validate(record):
    """Reject anything that is not one of the fixed fields with a fixed-shape value."""
    if set(record) != set(FIELDS):
        raise ValueError(f"unexpected fields: {sorted(set(record) ^ set(FIELDS))}")
    for key, kind in FIELDS.items():
        if not isinstance(record[key], kind) or (kind is int and isinstance(record[key], bool)):
            raise ValueError(f"{key} has the wrong type")
    for key, allowed in ENUMS.items():
        if record[key] not in allowed:
            raise ValueError(f"{key} is not one of the fixed values")
    if not set(record["park_reasons"]) <= CATEGORY_NAMES:
        raise ValueError("park_reasons holds a value outside the fixed categories")
    if not all(k in {"plan", "result", "verdict", "summary"} and v in TIER_NAMES for k, v in record["models"].items()):
        raise ValueError("models holds a value outside the fixed tiers")
    if not set(record["why"]) <= WHY_CODES:
        raise ValueError("why holds a value outside the fixed reason codes")
    if not all(isinstance(a, str) and AREA.match(a) for a in record["areas"]):
        raise ValueError("areas holds a value that is not a folder path")
    return record


def why_fields(body):
    """(review_score, why codes, hard_stop code) from a verdict's `Model: ... Why: ...` line. Only fixed codes
    and a number come out; the reason text itself is never stored."""
    m = WHY_LINE.search(body or "")
    if not m:
        return None, [], None
    why = m.group(1).strip()
    if why.lower().startswith("hard stop"):
        inner = why[why.find("(") + 1:]
        code = next((c for c, rx in HARD_STOP_CODES if re.search(rx, inner)), None)
        return None, [], code
    score = SCORE.match(why)
    codes = [c for c, rx in REASON_CODES if re.search(rx, why)]
    return (int(score.group(1)) if score else None), codes, None


def record_for(issue, owner, files=None, defects=(), cfg=None):
    """One fixed-shape record. `files` are the latest PR's file names (for areas); `defects` are
    (pr number, opened_at) pairs from the owner's bug or defect issues."""
    msgs = thread(issue)
    rejected = sum(1 for m in msgs[1:] if not is_owner(m, owner))
    replies = agent_replies(msgs, owner)
    kinds = [h.get("type") for _, h in replies]
    verdicts = [h for _, h in replies if h.get("type") == "verdict"]
    parks = [(i, h) for i, h in replies if h.get("type") == "question"]
    models, gaps, risk, merged = {}, 0, None, False
    for i, h in replies:
        body = msgs[i]["body"]
        m = MODEL.search(body)
        if m and h.get("type") in ("plan", "result", "verdict", "summary"):
            models[h["type"]] = m.group(1).lower()
            gaps += 1 if re.search(r"\bwanted\b", m.group(2), re.I) else 0
        if h.get("type") == "plan":
            risk = declared_risk(body) or risk
        if h.get("type") == "summary":
            line = re.search(r"(?im)^[ \t>*-]*\**Merged\**[ \t]*:[ \t]*\**[ \t]*(.*)$", body)
            merged = bool(line and not re.match(r"(no|not|none)\b", line.group(1).strip(), re.I))
    labels = label_names(issue.get("labels"))
    state = issue.get("state") or "open"
    outcome = ("done" if "done" in labels else "parked" if "needs-leo" in labels else
               "open" if state == "open" else "closed")
    relayed = any(k.get("relayed") for k in owner_keywords(msgs, owner, 0))
    verdict_replies = [(i, h) for i, h in replies if h.get("type") == "verdict"]
    score, why, hard, confidence = None, [], None, None
    if verdict_replies:
        body = msgs[verdict_replies[-1][0]]["body"]
        score, why, hard = why_fields(body)
        c = CONFIDENCE.search(body)
        confidence = c.group(1).lower() if c else None
    holds = [m for m in msgs[1:] if is_owner(m, owner) and (first_header(m["body"]) or {}).get("from") in AGENTS
             and (first_header(m["body"]) or {}).get("type") == "hold"]
    results = [h for _, h in replies if h.get("type") == "result" and h.get("phase") == "2"]
    pr = results[-1].get("pr") if results else None
    summaries = [i for i, h in replies if h.get("type") == "summary"]
    comments = issue.get("comments") or []
    at = summaries[-1] - 1 if summaries else -1  # msgs[0] is the issue body, so msgs[i] is comments[i - 1]
    merged_at = comments[at].get("created_at") if 0 <= at < len(comments) else None
    defect_after = False
    if pr and merged_at:
        for number, opened in defects or ():
            try:
                defect_after = defect_after or (str(number) == str(pr) and 0 <= _days(merged_at, opened) <= DEFECT_DAYS)
            except (TypeError, ValueError):
                continue
    areas = [a for a in feature_areas(source_files(files or [], cfg), cfg) if AREA.match(a)]
    return validate({
        "number": int(issue["number"]), "state": "closed" if state == "closed" else "open", "outcome": outcome,
        "plans": kinds.count("plan"), "revisions": max(kinds.count("plan") - 1, 0), "verdicts": len(verdicts),
        "review_rounds": sum(1 for h in verdicts if h.get("verdict") == "changes"), "parks": len(parks),
        "park_reasons": [park_category(msgs[i]["body"]) for i, _ in parks], "replies": len(replies),
        "merged": merged, "relayed_approval": relayed, "model_gaps": gaps, "models": models, "risk": risk,
        "rejected_comments": rejected,
        "review_score": score, "why": why, "hard_stop": hard, "confidence": confidence,
        "rechecked": any(is_recheck(h) for h in verdicts), "cap_parked": bool(holds), "areas": areas,
        "defect_after": defect_after,
        "evidence": {"verified": ["plans", "revisions", "verdicts", "review_rounds", "parks", "replies", "outcome",
                                  "relayed_approval", "model_gaps", "models", "risk", "rechecked", "cap_parked",
                                  "areas"],
                     "uncertain": ["park_reasons", "merged", "review_score", "why", "hard_stop", "confidence",
                                   "defect_after"], "rejected": rejected},
    })


def defect_refs(repo, owner, fixtures=None):
    """(pr number, opened_at) for every `#N` in the owner's bug or defect issues (numbers only leave here)."""
    refs = []
    for label in ("bug", "defect"):
        issues = (from_fixture(fixtures, f"{label}.json", []) if fixtures else
                  get_json(f"repos/{repo}/issues?labels={label}&state=all&sort=created&direction=desc&per_page=100"))
        for issue in issues:
            if "pull_request" in issue or login(issue.get("user")).lower() != owner.lower():
                continue
            text = f"{issue.get('title') or ''}\n{issue.get('body') or ''}"
            refs += [(int(n), issue.get("created_at")) for n in re.findall(r"(?<![\w/])#(\d+)\b", text)]
    return refs


def latest_pr(issue, owner):
    results = [h for _, h in agent_replies(thread(issue), owner) if h.get("type") == "result" and h.get("phase") == "2"]
    pr = results[-1].get("pr") if results else None
    return int(pr) if pr and str(pr).isdigit() else None


def defect_notes(issue, owner):
    """(pr number, opened_at) for the loop's `type=defect pr=N` notes ("Galing sa #N") on a bug issue."""
    if not label_names(issue.get("labels")) & {"bug", "defect"}:
        return []
    refs = []
    for c in issue.get("comments") or []:
        h = first_header(c.get("body") or "") if is_owner(c, owner) else None
        if h and h.get("from") in AGENTS and h.get("type") == "defect" and str(h.get("pr", "")).isdigit():
            refs.append((int(h["pr"]), issue.get("created_at")))
    return refs


def collect(repo, owner, fixtures=None, limit=50, cfg=None):
    if fixtures:
        issues = from_fixture(fixtures, "issues.json", [])
    else:
        issues = get_json(f"repos/{repo}/issues?state=all&sort=updated&direction=desc&per_page=100")
    defects = defect_refs(repo, owner, fixtures)
    loaded = []
    for issue in issues[:limit]:
        if "pull_request" in issue or login(issue.get("user")).lower() != owner.lower():
            continue
        if not is_autopilot(issue.get("body")):
            continue
        n = issue["number"]
        comments = (from_fixture(fixtures, f"{n}.comments.json", []) if fixtures else
                    get_all(f"repos/{repo}/issues/{n}/comments"))
        loaded.append(dict(issue, comments=comments))
        defects += defect_notes(loaded[-1], owner)
    records = []
    for issue in loaded:
        pr = latest_pr(issue, owner)
        files = []
        if pr:
            files = [f.get("filename", "") for f in (from_fixture(fixtures, f"pr{pr}.files.json", []) if fixtures else
                                                     get_all(f"repos/{repo}/pulls/{pr}/files"))]
        records.append(record_for(issue, owner, files, defects, cfg))
    return {"repo": repo, "owner": owner, "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "issues": records, "api_calls": len(CALLS)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--owner", default=None)
    ap.add_argument("--config", default=None)
    ap.add_argument("--limit", type=int, default=50, help="the most recently updated issues to look at")
    ap.add_argument("--fixtures", default=None)
    ap.add_argument("--out", default=None, help="write the JSON here instead of stdout")
    a = ap.parse_args()
    try:
        cfg = loop_config.load(a.config)
        set_owner_associations(cfg["owner_associations"])
        owner = loop_config.resolve_owner(a.repo, a.owner, cfg, a.fixtures)
        result = collect(a.repo, owner, a.fixtures, a.limit, cfg)
    except (ApiError, ValueError, KeyError) as e:
        json.dump({"ok": False, "error": str(e)}, sys.stdout, indent=2)
        print()
        sys.exit(2)
    text = json.dumps(result, indent=2)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        print(text)


if __name__ == "__main__":
    main()
