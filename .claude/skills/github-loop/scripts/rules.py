#!/usr/bin/env python3
"""Shared risk rules: which files and goals count as sensitive.

pick_model.py (model tier), route.py (experts and gates) and `loop_gh.py merge` (who merges) all
read these rules, so they never disagree.

High risk (the owner's list): authentication and permissions, secrets and credentials, sensitive
data, database schema and migrations, payments, production config and deploys, `.github/`
(workflows), Apps Script deploy files, and the loop's own skill folder, installed under
`.claude/skills/` or kept as source in a top-level `github-loop/` (its scripts, SKILL.md and setup are
the loop's safety controls). A repository adds its own sensitive paths with the `risk_paths` setting;
settings only ever add to these rules. Sensitive data and destructive operations cannot be seen in
a file name, so the plan's `Risk:` line covers them; it can raise the tier, never lower it.
"""
import fnmatch
import functools
import re

DOCS = re.compile(r"\.(md|txt|rst)$", re.I)
RISK_PATH = re.compile(
    r"(auth(?!or)|permission|(^|[^a-z])roles?([^a-z]|$)|(^|[^a-z])acl([^a-z]|$)|secret|token|credential|passw|"
    r"(^|[^a-z])pin([^a-z]|$)|schema|migration|\.sql$|payment|billing|payroll|security|^\.github/|"
    r"(^|/)appsscript\.json$|\.clasp|deploy|(^|/)\.env)", re.I)
SKILL_PATH = re.compile(r"(^|/)\.claude/skills/|^github-loop/")
RISK_TEXT = re.compile(
    r"(authenticat|authoriz|permission|access control|role-based|data integrity|schema|migration|payment|"
    r"billing|payroll|credential|destructive|delete (all|data))", re.I)
ARCHITECTURE = re.compile(
    r"(new system|new project|from scratch|architecture|rewrite|redesign|rebuild|platform|re-platform)", re.I)
RISK_LINE = re.compile(r"(?im)^[ \t>*-]*risk[ \t]*:[ \t]*\**[ \t]*(low|normal|high)\b")
# Bold markers are allowed around the label ("**Files in scope:**"), never eaten from the patterns themselves.
SCOPE_LINE = re.compile(r"(?im)^[ \t>*-]*(?:\*\*)?files in scope(?:\*\*)?[ \t]*:(?:\*\*)?[ \t]*(.*)$")
TOO_BROAD = {"*", "**", "/", ".", "./", "**/*", "*/**"}
TIERS = ("low", "normal", "high")
AUTHORITY = ("**/CLAUDE.md", "**/AGENTS.md")
LOCKFILES = ("**/*.lock", "**/package-lock.json")
GENERATED = ("**/*.min.js", "dist/**", "build/**")
TESTS = ("**/tests/**", "**/test/**", "**/__tests__/**", "**/evals/**", "**/*.test.*", "**/*.spec.*",
         "**/test_*.py", "**/*_test.py", "**/*_test.go")
KINDS = ("source", "test", "doc", "lockfile", "generated")


def norm(paths):
    return [re.sub(r"^\./", "", p.replace("\\", "/")) for p in paths if p]


def _segment(seg):
    out, i = [], 0
    while i < len(seg):
        c = seg[i]
        if c == "*":
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "[" and seg.find("]", i + 2) != -1:
            j = seg.find("]", i + 2)
            body = seg[i + 1:j].replace("\\", "\\\\")
            out.append("[^/" + body[1:] + "]" if body[:1] in ("!", "^") else "[" + body + "]")
            i = j
        else:
            out.append(re.escape(c))
        i += 1
    return "".join(out)


@functools.lru_cache(maxsize=1024)
def _glob(pattern):
    p = norm([pattern])[0].lstrip("/").lower()
    if p.endswith("/"):
        p += "**"
    parts = p.split("/")
    rx = []
    for k, part in enumerate(parts):
        last = k == len(parts) - 1
        if part == "**":
            rx.append(".*" if last else "(?:[^/]+/)*")
        else:
            rx.append(_segment(part) + ("" if last else "/"))
    return re.compile("".join(rx))


def glob_match(path, pattern):
    """The one matcher for the settings' path lists (risk_paths, authority_docs, test_globs, doc_globs,
    feature_roots). Case is ignored; paths use `/` and a leading `./` is dropped. `*`, `?` and `[...]` match
    inside one folder level and never cross `/`. A `**` level matches zero or more whole levels, so
    `src/**/env*` matches `src/env.js` and `src/core/env.js`. A pattern ending in `/**` or `/` matches
    everything under that folder. Any other pattern must match the whole path. (`Files in scope:` keeps its
    own matcher, in_scope, so approved plans read the same.)"""
    return bool(_glob(pattern).fullmatch(norm([path])[0].lower()))


def any_glob(path, patterns):
    return any(glob_match(path, g) for g in patterns or ())


def _setting(cfg, key):
    return list((cfg or {}).get(key) or [])


def is_docs_only(paths):
    paths = norm(paths)
    return bool(paths) and all(DOCS.search(p) and not p.startswith(".github/") for p in paths)


def sensitive_paths(paths, cfg=None):
    """Files that make a change sensitive: the built-in names, or a `risk_paths` glob from the settings.
    Documentation alone is not, except under .github/ or the skill."""
    paths = norm(paths)
    skill = [p for p in paths if SKILL_PATH.search(p)]
    if is_docs_only(paths):
        return skill
    extra = _setting(cfg, "risk_paths")
    return skill + [p for p in paths if p not in skill and (RISK_PATH.search(p) or any_glob(p, extra))]


def authority_hits(paths, cfg=None):
    """Changed documents that decide rules: CLAUDE.md and AGENTS.md in any folder, plus the `authority_docs`
    globs. On its own an authority document does not make the merge gate high risk."""
    pats = list(AUTHORITY) + _setting(cfg, "authority_docs")
    return [p for p in norm(paths) if any_glob(p, pats)]


def classify(paths, cfg=None):
    """{path: kind}, kind one of source, test, doc, lockfile, generated. Lockfiles and generated files come
    first, then tests (built-in patterns plus `test_globs`), then documentation (.md, .txt, .rst plus
    `doc_globs`); everything else is source."""
    tests = list(TESTS) + _setting(cfg, "test_globs")
    docs = _setting(cfg, "doc_globs")
    out = {}
    for p in norm(paths):
        if any_glob(p, LOCKFILES):
            out[p] = "lockfile"
        elif any_glob(p, GENERATED):
            out[p] = "generated"
        elif any_glob(p, tests):
            out[p] = "test"
        elif DOCS.search(p) or any_glob(p, docs):
            out[p] = "doc"
        else:
            out[p] = "source"
    return out


def source_files(paths, cfg=None):
    return [p for p, kind in classify(paths, cfg).items() if kind == "source"]


def _root(pattern):
    p = norm([pattern])[0].lstrip("/")
    if p.endswith("/**"):
        p = p[:-3]
    return p.rstrip("/")


def feature_areas(source_paths, cfg=None):
    """The feature areas the files touch, in first-seen order. A file's area is the longest `feature_roots`
    folder pattern that matches the start of its path (`src/*` gives `src/repository` for
    src/repository/sheets.js). Without a matching root, the area is the file's folder (`.` at the top)."""
    roots = [_root(r) for r in _setting(cfg, "feature_roots")]
    areas = []
    for path in norm(source_paths):
        segs = path.split("/")
        best = None
        for r in roots:
            n = len(r.split("/"))
            if len(segs) > n and glob_match("/".join(segs[:n]), r) and (best is None or n > best[0]):
                best = (n, "/".join(segs[:n]))
        area = best[1] if best else ("/".join(segs[:-1]) or ".")
        if area not in areas:
            areas.append(area)
    return areas


def declared_risk(text):
    """The tier a plan or plan reply declares on a `Risk: low|normal|high` line, or None."""
    m = RISK_LINE.search(text or "")
    return m.group(1).lower() if m else None


def risk_tier(paths=(), declared=None, cfg=None):
    """(tier, reasons). 'high' when a sensitive file or the skill changes, or the plan declares high;
    'low' for documentation only; otherwise 'normal'. A declared tier only ever raises the result."""
    paths = norm(paths)
    hits = sensitive_paths(paths, cfg)
    tier, reasons = ("low", ["documentation only"]) if is_docs_only(paths) else ("normal", ["ordinary change"])
    if hits:
        tier, reasons = "high", ["sensitive files: " + ", ".join(hits[:5]) + (" ..." if len(hits) > 5 else "")]
    if declared in TIERS and TIERS.index(declared) > TIERS.index(tier):
        tier, reasons = declared, reasons + [f"the plan declares Risk: {declared}"]
    return tier, reasons


def declared_scope(text):
    """The patterns on a `Files in scope: a/, b/**, docs/plan-x.md` line, or None when there is no such line.
    Patterns are separated by commas or spaces; backticks are ignored."""
    m = SCOPE_LINE.search(text or "")
    if not m:
        return None
    return [p for p in re.split(r"[,\s]+", m.group(1).replace("`", "")) if p]


def scope_problems(patterns):
    """Why a declared scope cannot be used: missing, empty, or so broad that it checks nothing."""
    if patterns is None:
        return ["declare the files the plan may change on one line: `Files in scope: <folder/>, <file>, ...`"]
    if not patterns:
        return ["`Files in scope:` lists no files or folders"]
    broad = [p for p in patterns if p in TOO_BROAD]
    if broad:
        return [f"`Files in scope:` must name real folders or files, not {', '.join(broad)}"]
    return []


def in_scope(path, patterns):
    """`dir/` and `dir/**` cover everything under dir; `*`, `?` and `[...]` are globs; anything else is one file."""
    path = norm([path])[0]
    for raw in patterns:
        p = norm([raw])[0]
        if p.endswith("/**"):
            p = p[:-2]
        if p.endswith("/"):
            if path.startswith(p):
                return True
        elif any(ch in p for ch in "*?["):
            if fnmatch.fnmatchcase(path, p):
                return True
        elif path == p:
            return True
    return False


def outside_scope(paths, patterns):
    return [p for p in norm(paths) if not in_scope(p, patterns)]
