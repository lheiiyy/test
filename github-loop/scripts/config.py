#!/usr/bin/env python3
"""Per-repository settings, so the skill works for any owner, repository and language.

Read from --config, else the GITHUB_LOOP_CONFIG environment variable, else
`.github/github-loop.json` at the top of the git checkout the command runs in. The file and
every key in it are optional. Example:

    {
      "owner": "lheiiyy",
      "owner_name": "Leo",
      "language": "Taglish",
      "base": "main",
      "branch_prefix": "claude/",
      "owner_associations": ["OWNER"],
      "improve": true
    }

owner               the Product Owner's GitHub login. Without it, the repo's owner is used when
                    the repo belongs to a user; an organization repo must set it.
owner_name          how relayed approvals and messages name the owner (default: the login).
language            language of the agents' final messages to the owner (default: English).
base                the branch the loop merges into (default: main).
branch_prefix       the only PR branches the merge gate accepts: one prefix or a list
                    (default: claude/).
owner_associations  author_association values that count as the owner. Keep ["OWNER"] for a
                    personal repo; an organization repo adds "MEMBER" (the login must still match).
improve             false switches off improve.py proposals.

Risk and routing keys (all optional; the glob rules are in rules.glob_match and setup.md). The
list keys only ADD to the built-in rules; no key can switch a built-in rule off:
risk_paths          globs that make a change high risk, on top of the built-in sensitive names.
authority_docs      globs of documents that decide rules (CLAUDE.md and AGENTS.md always count).
risk_words          lowercase single words that count as risky logic, on top of the defaults.
feature_roots       folder globs that name the feature areas, for example ["src/*"].
test_globs          globs of test files, on top of the built-in test patterns.
doc_globs           globs of documentation files, on top of .md, .txt and .rst.
points, threshold, max_opus_per_day   review scoring and the daily Opus cap (checked now,
                    used by review routing v2).
plan_dir, plan_sections, commit_ref_pattern, merge_phrase, deploy   process settings (checked
                    now, used by the plan check and the merge gate).

A value of the wrong type or out of range raises ValueError("<key>: <why>"). An unknown key raises
too, and names the closest known key, because a typo would otherwise be ignored silently.
"""
import difflib
import json
import os
import re
import subprocess

from ghapi import ApiError, from_fixture, get_json

FILE = os.path.join(".github", "github-loop.json")
POINT_NAMES = ("areas", "files", "lines", "risk_words", "contract", "authority", "no_tests",
               "changes_requested", "defect")
DEFAULT_POINTS = {"areas": 3, "files": 3, "lines": 2, "risk_words": 3, "contract": 2, "authority": 2,
                  "no_tests": 2, "changes_requested": 1, "defect": 2}
LITE_SECTIONS = "lite"
TOKEN = re.compile(r"^[a-z][a-z0-9]*$")


def _str(key, v):
    if not isinstance(v, str) or not v.strip():
        return "must be a non-empty string"


def _opt_str(key, v):
    return None if v is None else _str(key, v)


def _bool(key, v):
    if not isinstance(v, bool):
        return "must be true or false"


def _int_range(lo, hi):
    def check(key, v):
        if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
            return f"must be a whole number from {lo} to {hi}"
    return check


def _str_list(key, v):
    if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
        return "must be a list of non-empty strings"


def _globs(key, v):
    bad = _str_list(key, v)
    if bad:
        return bad
    broad = [p for p in v if p.strip() in ("*", "**", "/", ".", "./", "**/*", "*/**")]
    if broad:
        return f"{', '.join(broad)} would match every file; name real folders or files"


def _feature_roots(key, v):
    bad = _globs(key, v)
    if bad:
        return bad
    deep = [p for p in v if "**" in (p[:-3] if p.endswith("/**") else p.rstrip("/"))]
    if deep:
        return f"name folders level by level with * (for example src/*), not **: {', '.join(deep)}"


def _branch_prefix(key, v):
    if isinstance(v, str):
        return _str(key, v)
    if isinstance(v, list) and v:
        return _str_list(key, v)
    return "must be a prefix string or a non-empty list of prefixes"


def _risk_words(key, v):
    bad = _str_list(key, v)
    if bad:
        return bad
    wrong = [w for w in v if not TOKEN.match(w)]
    if wrong:
        return f"use lowercase single words (letters and digits): {', '.join(wrong)}"


def _points(key, v):
    if not isinstance(v, dict):
        return "must be an object of point names to whole numbers"
    unknown = [k for k in v if k not in POINT_NAMES]
    if unknown:
        return f"unknown point names {', '.join(sorted(unknown))}; use {', '.join(POINT_NAMES)}"
    for k, n in v.items():
        if isinstance(n, bool) or not isinstance(n, int) or not 0 <= n <= 5:
            return f"{k} must be a whole number from 0 to 5"


def _plan_sections(key, v):
    if v is None or v == LITE_SECTIONS:
        return None
    if isinstance(v, list) and v:
        return _str_list(key, v)
    return f'must be "{LITE_SECTIONS}" or a non-empty list of section names'


def _regex(key, v):
    if v is None:
        return None
    if not isinstance(v, str) or not v:
        return "must be a regular expression string"
    try:
        re.compile(v)
    except re.error as e:
        return f"is not a valid regular expression ({e})"


def _merge_phrase(key, v):
    if v is None:
        return None
    if not isinstance(v, str) or "#{n}" not in v:
        return 'must be a string that contains #{n} (the PR number), for example "OK i-merge #{n}"'


def _deploy(key, v):
    if v not in ("auto", "off"):
        return 'must be "auto" or "off"'


# key: (default, check). The defaults reproduce the settings the loop had before these keys existed.
SCHEMA = {
    "owner": (None, _opt_str),
    "owner_name": (None, _opt_str),
    "language": ("English", _str),
    "base": ("main", _str),
    "branch_prefix": ("claude/", _branch_prefix),
    "owner_associations": (["OWNER"], _str_list),
    "improve": (True, _bool),
    "risk_paths": ([], _globs),
    "authority_docs": ([], _globs),
    "risk_words": ([], _risk_words),
    "feature_roots": ([], _feature_roots),
    "test_globs": ([], _globs),
    "doc_globs": ([], _globs),
    "points": (dict(DEFAULT_POINTS), _points),
    "threshold": (3, _int_range(2, 10)),
    "max_opus_per_day": (3, _int_range(0, 50)),
    "plan_dir": (None, _opt_str),
    "plan_sections": (None, _plan_sections),
    "commit_ref_pattern": (None, _regex),
    "merge_phrase": (None, _merge_phrase),
    "deploy": ("auto", _deploy),
}


def defaults():
    """A fresh copy of every default (lists and dicts are copied, so callers can change them)."""
    return {k: json.loads(json.dumps(d)) for k, (d, _) in SCHEMA.items()}


DEFAULTS = defaults()


def default_path():
    try:
        proc = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    except FileNotFoundError:
        return None
    return os.path.join(proc.stdout.strip(), FILE) if proc.returncode == 0 else None


def validate(data, where="settings"):
    """Raise ValueError for an unknown key or a bad value. Returns the data unchanged."""
    if not isinstance(data, dict):
        raise ValueError(f"{where} must hold a JSON object")
    for key in sorted(data):
        if key not in SCHEMA:
            close = difflib.get_close_matches(key, SCHEMA, n=1, cutoff=0.6)
            hint = f" (did you mean `{close[0]}`?)" if close else f"; known keys: {', '.join(SCHEMA)}"
            raise ValueError(f"{where}: unknown key `{key}`{hint}")
        value = data[key]
        if value is None:
            continue
        why = SCHEMA[key][1](key, value)
        if why:
            raise ValueError(f"{key}: {why}")
    return data


def load(path=None):
    """Settings merged over the defaults. A file that is not valid JSON, has an unknown key or a bad value
    raises ValueError. A null value means "use the default"."""
    path = path or os.environ.get("GITHUB_LOOP_CONFIG") or default_path()
    cfg = defaults()
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        validate(data, path)
        for k, v in data.items():
            if v is None:
                continue
            cfg[k] = dict(cfg["points"], **v) if k == "points" else v
    return cfg


def prefixes(cfg):
    """The accepted PR branch prefixes as a tuple (branch_prefix may be one string or a list)."""
    value = (cfg or {}).get("branch_prefix") or SCHEMA["branch_prefix"][0]
    return (value,) if isinstance(value, str) else tuple(value)


def resolve_owner(repo, given=None, cfg=None, fixtures=None):
    """The owner's login: --owner, else the config, else the user who owns the repo."""
    if given:
        return given
    if (cfg or {}).get("owner"):
        return cfg["owner"]
    info = from_fixture(fixtures, "repo.json") if fixtures else get_json(f"repos/{repo}")
    owner = info.get("owner") or {}
    if owner.get("login") and owner.get("type", "User") == "User":
        return owner["login"]
    raise ApiError(f"{repo} belongs to an organization: pass --owner or set \"owner\" in {FILE}")


def owner_name(cfg, owner):
    return (cfg or {}).get("owner_name") or owner
