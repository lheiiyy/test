#!/usr/bin/env python3
"""Pick the model tier for one github-loop step, from facts and not from a feeling.

    pick_model.py --step review --git-range origin/main...HEAD --session sonnet
    pick_model.py --step plan --text issue.md --session sonnet
    pick_model.py --step fix --paths src/auth.js tests/auth.test.js --attempt 2 --session sonnet

Prints a JSON report: tier (haiku, sonnet or opus), action ("run inline" or
"delegate"), the reasons, and the signals it saw. Exit 0, or 2 on bad input.

Rules (the table in references/models.md mirrors them):
- merge, verify: haiku (a scripted command and its exit code).
- report: sonnet (it states results as facts).
- plan, revise: sonnet is the floor. They go to opus on risk, on a big change, on an
  architecture-heavy goal, and on the second plan revision.
- review (routing v2): hard stops go to opus first (a sensitive or `risk_paths` file, risk
  words in the goal, `Risk: high`, a weakened test, the third round, an authority document
  changed with no code). Otherwise score() adds points (feature areas, source files, diff
  lines, whole-word risk words in changed source lines, a public contract change, an
  authority document, no test change, an earlier CHANGES REQUESTED, a post-merge defect in the
  same area); below `threshold` (default 3) is sonnet, at or above it is opus. The Model line
  ends with `Why: score N (...)` or `Why: hard stop (...)`.
- A big change means 8 or more source files, or 5 or more plan tasks. Tests, documentation,
  lockfiles and generated files do not count (rules.classify, with the settings' test_globs and
  doc_globs).
- build: sonnet (haiku for documentation only); opus only when risky AND big.
- fix: sonnet (haiku for documentation only); opus on risk, on the third review
  round, and on the second attempt at the same failure (before the run parks).
- The owner can force a tier with `Model: opus` in the request, or with the Model field of
  the issue form. It applies to plan, revise, build, fix and review. For a review it can only
  choose sonnet or opus (`haiku` is lifted to sonnet), and it can never lower a review hard stop:
  that review is opus whatever the Model line says.
- fable (the top tier) is never picked. It costs the most, so only the owner asks for it.

`delegate` means the tier is above the model this task runs on (--session): hand
the judgment to a subagent with that model and keep the scripts and the posting in
this session. A lower tier than the session's runs inline, because a subagent
restarts cold and costs more than it saves.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as loop_config  # noqa: E402
from rules import (ARCHITECTURE, DOCS, RISK_PATH, RISK_TEXT, authority_hits, classify,  # noqa: E402,F401
                   feature_areas, is_docs_only, norm, sensitive_paths, source_files)

RANK = {"haiku": 1, "sonnet": 2, "opus": 3, "fable": 4}
STEPS = ["plan", "revise", "build", "fix", "review", "merge", "verify", "report"]
THINKING = {"plan", "revise", "build", "fix", "review"}  # steps the owner may force a tier for

FORCED = re.compile(r"(?im)^[ \t]*(?:#{1,4}[ \t]*)?model\b(?![ \t]+plan)[^\n:]*?(?::[ \t]*|\n+[ \t]*)"
                    r"(auto|haiku|sonnet|opus)\b")
HEADING = re.compile(r"(?m)^#{2,3}[ \t]+(.+?)[ \t]*$")

# Review routing v2. The generic risk words; a repository adds its own with the `risk_words` setting.
DEFAULT_RISK_WORDS = ("calculate", "calculation", "score", "scoring", "price", "money", "amount", "payment",
                      "balance")
SKIP_ADDED = re.compile(r"(\.(skip|only|todo)\s*\(|\bx(it|describe|test)\s*\(|@pytest\.mark\.skip|"
                        r"@unittest\.skip|\bskipTest\s*\(|\btest\.todo\b)")
ASSERTION = re.compile(r"\b(assert\w*|expect|should)\b|\bt\.(is|ok|deepEqual|equal|true|false|throws)\b")
CONTRACT_LINE = re.compile(r"(?im)^[ \t>*-]*\**public contract\**[ \t]*:[ \t]*\**[ \t]*changed\b")
TOP_DECL = re.compile(r"^(?:export\s+(?:default\s+)?(?:async\s+)?(?:function\*?|class|const|let|var)\s+"
                      r"([A-Za-z_$][\w$]*)|(?:async\s+)?function\*?\s+([A-Za-z_$][\w$]*)|(?:async\s+)?def\s+"
                      r"([A-Za-z_]\w*)|(module\.exports(?:\.[A-Za-z_$][\w$]*)?\s*=|export\s*\{))")
WORD = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+")
DEFECT_DAYS = 14
# Fixed reason codes: outcomes.py stores these codes, never the reason text.
REASON_CODES = (
    ("areas", r"feature areas"), ("files", r"source files"), ("lines", r"\bdiff (150-400|>400)"),
    ("risk_words", r"risk words:"), ("contract", r"public contract changed"),
    ("authority", r"authority doc changed(?! with no code)"), ("no_tests", r"no test change"),
    ("changes_requested", r"changes requested earlier"), ("defect", r"post-merge defect"),
    ("defect_unknown", r"defect history unknown"), ("docs_only", r"documentation only"),
    ("no_signals", r"no risk signals"), ("owner", r"owner's Model line"))
HARD_STOP_CODES = (
    ("risk_path", r"risk path "), ("risk_goal", r"the goal mentions "), ("risk_declared", r"Risk: high"),
    ("test_weakened", r"(test deleted|test skipped|assertion removed): "), ("round3", r"third review round"),
    ("authority_only", r"authority doc changed with no code"))


def parse_session(value):
    """The model family of the running task: 'sonnet', 'claude-opus-5-5' or 'Opus 5.5' all work."""
    if not value:
        return "sonnet"
    low = value.lower()
    for name in ("haiku", "sonnet", "opus", "fable", "mythos"):
        if name in low:
            return "fable" if name == "mythos" else name
    raise ValueError(f"unknown model: {value!r}; use haiku, sonnet or opus")


def objective_of(text):
    """The Objective section of an autopilot request. The rest of the template (Phase 1, constraints) holds
    boilerplate words such as 'schema' and 'credentials', which must not count as risk. Without an Objective
    heading (a free-form request), the whole text is used."""
    heads = list(HEADING.finditer(text))
    for n, h in enumerate(heads):
        if h.group(1).strip().lower() == "objective":
            end = heads[n + 1].start() if n + 1 < len(heads) else len(text)
            return text[h.end():end]
    return text


def forced_tier(text):
    m = FORCED.search(text or "")
    if m and m.group(1).lower() != "auto":
        return m.group(1).lower()
    return None


def parse_diff(text):
    """{path: {"added": [...], "removed": [...], "deleted": bool}} from a unified diff (`git diff` output)."""
    files, cur = {}, None
    for line in (text or "").splitlines():
        if line.startswith("diff --git "):
            parts = line.split(" b/", 1)
            cur = norm([parts[1] if len(parts) == 2 else line.split()[-1]])[0]
            files[cur] = {"added": [], "removed": [], "deleted": False}
        elif cur is None:
            continue
        elif line.startswith("deleted file mode") or line == "+++ /dev/null":
            files[cur]["deleted"] = True
        elif line.startswith(("+++", "---", "index ", "new file mode", "similarity", "rename ", "@@", "Binary")):
            continue
        elif line.startswith("+"):
            files[cur]["added"].append(line[1:])
        elif line.startswith("-"):
            files[cur]["removed"].append(line[1:])
    return files


def words_of(line):
    """Whole words of a line: identifiers split on camelCase, snake_case, kebab-case and digits, lower-cased.
    `dueDate` gives due, date; `calc_total` gives calc, total; `validate` stays validate."""
    out = []
    for ident in re.findall(r"[A-Za-z0-9]+", line):
        out += [w.lower() for w in WORD.findall(ident)]
    return out


def risk_word_hits(files, sources, cfg):
    """Listed words found in added or removed lines of source files, in order of first appearance."""
    listed = set(DEFAULT_RISK_WORDS) | set((cfg or {}).get("risk_words") or [])
    hits = []
    for path in sources:
        d = files.get(path) or {}
        for line in d.get("added", []) + d.get("removed", []):
            for w in words_of(line):
                if w in listed and w not in hits:
                    hits.append(w)
    return hits


def decl_key(line):
    """The top-level declaration a line makes (a name, or the whole line for module.exports and export {...})."""
    if not line or line[:1].isspace():
        return None
    m = TOP_DECL.match(line)
    if not m:
        return None
    return m.group(1) or m.group(2) or m.group(3) or line.strip()


def contract_changes(files, sources):
    """Top-level functions, exports or module.exports lines that a source file removes or renames."""
    found = []
    for path in sources:
        d = files.get(path) or {}
        kept = {decl_key(l) for l in d.get("added", [])} - {None}
        for line in d.get("removed", []):
            key = decl_key(line)
            if key and key not in kept:
                found.append(f"{path}: {key}")
    return found


def test_weakening(files, kinds):
    """The first test file that is deleted, gains a skip/only/xit/.todo, or loses assertions with none added."""
    for path, d in files.items():
        if kinds.get(path) != "test":
            continue
        if d["deleted"]:
            return f"test deleted: {path}"
        if any(SKIP_ADDED.search(l) for l in d["added"]):
            return f"test skipped: {path}"
        if any(ASSERTION.search(l) for l in d["removed"]) and not any(ASSERTION.search(l) for l in d["added"]):
            return f"assertion removed: {path}"
    return None


def _days(a, b):
    def t(v):
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    return (t(b) - t(a)).total_seconds() / 86400


def defect_areas(history, areas, cfg):
    """Feature areas this change shares with a post-merge defect (an issue opened within 14 days of its PR's
    merge). None when the defect history could not be read."""
    defects = (history or {}).get("defects")
    if defects is None:
        return None
    hit = []
    for d in defects:
        try:
            age = _days(d["merged_at"], d["opened_at"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= age <= DEFECT_DAYS:
            for area in feature_areas(source_files(d.get("files") or [], cfg), cfg):
                if area in areas and area not in hit:
                    hit.append(area)
    return hit


def _kinds(paths, files, cfg):
    return classify(list(paths) + [p for p in files if p not in paths], cfg)


def score(paths, diff=None, cfg=None, history=None, text=""):
    """(points, reasons) for a review; reasons is a list of (code, text, points) in the order of the table in
    references/models.md. `diff` is unified diff text (None: not read). `history` is
    {"changes_requested": bool, "defects": [{"pr", "merged_at", "opened_at", "files"}]}; a missing or null
    "defects" means the defect history is unknown, which scores 0 and says so."""
    cfg = cfg or {}
    pts = dict(loop_config.DEFAULT_POINTS, **(cfg.get("points") or {}))
    paths = norm(paths)
    files = parse_diff(diff) if diff else {}
    kinds = _kinds(paths, files, cfg)
    sources = [p for p, k in kinds.items() if k == "source"]
    tests = [p for p, k in kinds.items() if k == "test"]
    reasons = []

    def add(code, text_, top, low=False):
        reasons.append((code, text_, min(1, top) if low else top))

    areas = feature_areas(sources, cfg)
    if len(areas) == 2:
        add("areas", "2 feature areas", pts["areas"], low=True)
    elif len(areas) >= 3:
        add("areas", f"{len(areas)} feature areas", pts["areas"])
    if 4 <= len(sources) <= 7:
        add("files", f"{len(sources)} source files", pts["files"], low=True)
    elif len(sources) >= 8:
        add("files", f"{len(sources)} source files", pts["files"])
    lines = sum(len(d["added"]) + len(d["removed"]) for p, d in files.items() if kinds.get(p) in ("source", "test"))
    if 150 <= lines <= 400:
        add("lines", "diff 150-400", pts["lines"], low=True)
    elif lines > 400:
        add("lines", "diff >400", pts["lines"])
    hits = risk_word_hits(files, sources, cfg)
    if hits:
        add("risk_words", "risk words: " + ", ".join(hits[:5]), pts["risk_words"])
    if CONTRACT_LINE.search(text or "") or contract_changes(files, sources):
        add("contract", "public contract changed", pts["contract"])
    if authority_hits(paths, cfg):
        add("authority", "authority doc changed", pts["authority"])
    if sources and not tests:
        add("no_tests", "no test change", pts["no_tests"])
    if (history or {}).get("changes_requested"):
        add("changes_requested", "changes requested earlier", pts["changes_requested"])
    shared = defect_areas(history, areas, cfg)
    if shared is None:
        reasons.append(("defect_unknown", "defect history unknown", 0))
    elif shared:
        add("defect", f"post-merge defect in {shared[0]} within {DEFECT_DAYS} days", pts["defect"])
    return sum(p for _, _, p in reasons), reasons


def hard_stop(paths, diff=None, cfg=None, goal="", declared=None, round_=1):
    """The first rule that sends a review to opus whatever the score, as (code, text), or None. No setting can
    switch these off."""
    paths = norm(paths)
    files = parse_diff(diff) if diff else {}
    kinds = _kinds(paths, files, cfg)
    risky = sensitive_paths(paths, cfg)
    if risky:
        return "risk_path", f"risk path {risky[0]}"
    words = RISK_TEXT.search(goal or "")
    if words:
        return "risk_goal", f"the goal mentions {words.group(1).lower()}"
    if declared == "high":
        return "risk_declared", "the plan declares Risk: high"
    weak = test_weakening(files, kinds)
    if weak:
        return "test_weakened", weak
    if round_ >= 3:
        return "round3", "the third review round"
    if authority_hits(paths, cfg) and not [p for p, k in kinds.items() if k == "source"]:
        return "authority_only", "authority doc changed with no code"
    return None


def why_text(points, reasons, docs_only):
    """`score N (<top 3 reasons by points>)`, plus `defect history unknown` when it was."""
    scored = sorted([r for r in reasons if r[2] > 0], key=lambda r: -r[2])[:3]
    parts = [r[1] for r in scored] or (["documentation only"] if docs_only else ["no risk signals"])
    parts += [r[1] for r in reasons if r[0] == "defect_unknown"]
    return f"score {points} ({'; '.join(parts)})"


def review_pick(paths, diff, cfg, history, text, goal, declared, round_):
    """Routing v2 for the review step: {tier, why, score, threshold, reasons, hard_stop, hard_stop_code}."""
    threshold = (cfg or {}).get("threshold") or 3
    points, reasons = score(paths, diff, cfg, history, text)
    stop = hard_stop(paths, diff, cfg, goal, declared, round_)
    out = {"score": points, "threshold": threshold,
           "reasons": [{"code": c, "text": t, "points": p} for c, t, p in reasons],
           "hard_stop": stop[1] if stop else None, "hard_stop_code": stop[0] if stop else None}
    if stop:
        return dict(out, tier="opus", why=f"hard stop ({stop[1]})")
    tier = "opus" if points >= threshold else "sonnet"
    return dict(out, tier=tier, why=why_text(points, reasons, is_docs_only(paths)))


def pick(step, paths=(), text="", tasks=0, attempt=1, round_=1, session=None, declared=None, cfg=None, diff=None,
         history=None):
    if step not in STEPS:
        raise ValueError(f"unknown step {step!r}; use one of {', '.join(STEPS)}")
    paths = norm(paths)
    docs_only = is_docs_only(paths)
    risk_paths = sensitive_paths(paths, cfg)  # shared with route.py and the merge gate (rules.py)
    sources = source_files(paths, cfg)
    goal = objective_of(text or "")
    risk_text = RISK_TEXT.search(goal)
    risky = bool(risk_paths or risk_text or declared == "high")
    large = len(sources) >= 8 or tasks >= 5
    heavy = bool(ARCHITECTURE.search(goal))
    why_risk = ("sensitive files: " + ", ".join(risk_paths[:3])) if risk_paths else (
        f"the goal mentions {risk_text.group(1).lower()}" if risk_text else
        "the plan declares Risk: high" if declared == "high" else "")
    forced = forced_tier(text) if step in THINKING else None
    review = None

    if step in ("merge", "verify"):
        tier, why = "haiku", "a scripted command: run it and read its exit code"
    elif forced and step == "review":
        review = review_pick(paths, diff, cfg, history, text, goal, declared, round_)
        if review["hard_stop"] and forced != "opus":
            tier = "opus"
            why = f"{review['why']}: the owner's Model: {forced} cannot lower a hard stop"
        else:
            tier = "sonnet" if forced == "haiku" else forced
            lifted = "; haiku lifted to the sonnet floor" if forced == "haiku" else ""
            why = f"the owner's request sets the model to {forced}{lifted}"
            review = dict(review, tier=tier, why=f"owner's Model line ({forced}{lifted})")
    elif forced:
        tier, why = forced, f"the owner's request sets the model to {forced}"
    elif step == "report":
        tier, why = "sonnet", "the report states results as facts, so keep it accurate"
    elif step in ("plan", "revise"):
        tier, why = "sonnet", "planning needs real reasoning, so sonnet is the floor"
        if risky:
            tier, why = "opus", why_risk + "; plan it with the stronger model"
        elif heavy:
            tier, why = "opus", "an architecture-heavy goal"
        elif large:
            tier, why = "opus", "a big change"
        elif step == "revise" and round_ >= 2:
            tier, why = "opus", "the owner has asked for a second revision"
    elif step == "review":
        review = review_pick(paths, diff, cfg, history, text, goal, declared, round_)
        tier = review["tier"]
        why = (f"{review['why']}: review it with the stronger model" if tier == "opus" else
               f"{review['why']}: sonnet is the review floor")
    elif step == "build":
        tier, why = ("haiku", "documentation only") if docs_only else ("sonnet", "ordinary implementation")
        if risky and large:
            tier, why = "opus", "a big change in sensitive code" + (": " + why_risk if why_risk else "")
    else:  # fix
        tier, why = ("haiku", "documentation only") if docs_only else ("sonnet", "an ordinary fix")
        if attempt >= 2:
            tier, why = "opus", "the second attempt at the same failure: escalate before parking"
        elif risky:
            tier, why = "opus", why_risk + "; fix it with the stronger model"
        elif round_ >= 3:
            tier, why = "opus", "the third review round: the earlier fixes did not settle it"

    running = parse_session(session)
    tail = f". Why: {review['why']}" if review else ""
    if RANK[tier] > RANK[running]:
        action = "delegate"
        note = (f"Hand the judgment to a subagent with model={tier}; keep the scripts and the posting in this "
                f"session. With no Agent tool, run inline and say so in the reply.")
        lines = {"subagent": f"Model: {tier} (via subagent){tail}",
                 "inline": f"Model: {running} (wanted {tier}; ran inline, no subagent){tail}"}
    elif RANK[tier] < RANK[running]:
        action = "run inline"
        note = f"{tier} would be enough. Run inline, because a subagent restarts cold and costs more than it saves."
        lines = {"inline": f"Model: {running} (wanted {tier}; ran inline){tail}"}
    else:
        action = "run inline"
        note = "This task's model fits."
        lines = {"inline": f"Model: {running}{tail}"}
    report = {
        "step": step, "tier": tier, "action": action, "session": running, "reasons": [why], "note": note,
        "model_line": lines,  # paste the one that is true; check_reply.py rejects a reply without it
        "forced": bool(forced), "forced_tier": forced,
        "signals": {"docs_only": docs_only, "risk_paths": risk_paths,
                    "risk_text": risk_text.group(1).lower() if risk_text else None,
                    "large": large, "files": len(paths), "source_files": len(sources), "tasks": tasks,
                    "attempt": attempt, "round": round_},
    }
    if review:
        report["review"] = review
    return report


def paths_from_git(rng):
    proc = subprocess.run(["git", "diff", "--name-only", rng], capture_output=True, text=True)
    if proc.returncode != 0:
        raise ValueError(f"git diff --name-only {rng} failed: {proc.stderr.strip()[:200]}")
    return proc.stdout.split()


def diff_from_git(rng):
    proc = subprocess.run(["git", "diff", "--no-color", "--no-ext-diff", "-U0", rng], capture_output=True, text=True)
    if proc.returncode != 0:
        raise ValueError(f"git diff {rng} failed: {proc.stderr.strip()[:200]}")
    return proc.stdout


def read_text(path):
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as f:
        return f.read()


def read_history(path):
    """The --history file (review_history.py output). A missing --history means the history is unknown."""
    if not path:
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: the history must be a JSON object")
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--step", required=True, choices=STEPS)
    ap.add_argument("--paths", nargs="*", default=[], help="changed or planned files")
    ap.add_argument("--git-range", default=None, help="take the files from git diff --name-only <range>")
    ap.add_argument("--text", default=None, help="the issue or request text file, or - for stdin")
    ap.add_argument("--tasks", type=int, default=0, help="number of tasks in the plan")
    ap.add_argument("--attempt", type=int, default=1, help="attempt at the same failure, 1 or 2")
    ap.add_argument("--round", type=int, default=1, dest="round_", help="plan revision or review round")
    ap.add_argument("--session", default=None, help="model of the running task: haiku, sonnet, opus (default sonnet)")
    ap.add_argument("--declared-risk", choices=("low", "normal", "high"), default=None,
                    help="the plan's Risk: line; high counts as a sensitive change")
    ap.add_argument("--config", default=None, help="settings file (default .github/github-loop.json)")
    ap.add_argument("--diff", default=None, help="unified diff file for the review score (default: from --git-range)")
    ap.add_argument("--history", default=None, help="review_history.py output; without it the defect history is "
                                                    "unknown")
    args = ap.parse_args()

    try:
        paths = list(args.paths)
        if args.git_range:
            paths += paths_from_git(args.git_range)
        text = ""
        if args.text:
            text = sys.stdin.read() if args.text == "-" else open(args.text, encoding="utf-8").read()
        cfg = loop_config.load(args.config)
        diff = read_text(args.diff) if args.diff else (
            diff_from_git(args.git_range) if args.git_range and args.step == "review" else None)
        report = pick(args.step, paths, text, args.tasks, args.attempt, args.round_, args.session, args.declared_risk,
                      cfg, diff, read_history(args.history))
    except (ValueError, OSError) as e:
        json.dump({"ok": False, "error": str(e)}, sys.stdout, indent=2)
        print()
        sys.exit(2)
    json.dump(report, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
