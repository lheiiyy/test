"""Tests for PR-A of docs/plan-skill-fixes.md: the settings schema, the one glob matcher, file kinds,
feature areas, source-only counting and the TDMS example profile. Run: python3 -B evals/test_config_rules.py

Offline: GitHub is simulated with fixtures, as in test_scripts.py. Kept out of the packaged skill.
"""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPTS = os.path.join(SKILL, "scripts")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import config as loop_config  # noqa: E402
import pick_model as pm  # noqa: E402
import route as rt  # noqa: E402
import rules  # noqa: E402
import test_scripts as ts  # noqa: E402  (shared fixtures; its test classes are not collected here)

PROFILE = os.path.join(SKILL, "references", "profiles", "tdms.example.json")
OLD_DEFAULTS = {"owner": None, "owner_name": None, "language": "English", "base": "main", "branch_prefix": "claude/",
                "owner_associations": ["OWNER"], "improve": True}


def write_config(data):
    d = tempfile.mkdtemp()
    path = os.path.join(d, "github-loop.json")
    with open(path, "w") as f:
        json.dump(data, f)
    return path


def load_profile():
    return loop_config.load(PROFILE)


class ConfigSchemaTests(unittest.TestCase):
    EVERY_KEY = {
        "owner": "lheiiyy", "owner_name": "Leo", "language": "Taglish", "base": "main",
        "branch_prefix": ["feat/", "docs/"], "owner_associations": ["OWNER"], "improve": False,
        "risk_paths": ["src/repository/**"], "authority_docs": ["docs/RULES.md"], "risk_words": ["date", "sla"],
        "feature_roots": ["src/*"], "test_globs": ["spec/**"], "doc_globs": ["handbook/**"],
        "points": {"areas": 2, "no_tests": 0}, "threshold": 4, "max_opus_per_day": 0, "plan_dir": "docs/plans",
        "plan_sections": "lite", "commit_ref_pattern": r"^(feat|docs)\(#\d+\)", "merge_phrase": "OK i-merge #{n}",
        "deploy": "off"}

    def test_every_documented_key_loads(self):
        self.assertEqual(set(self.EVERY_KEY), set(loop_config.SCHEMA))
        cfg = loop_config.load(write_config(self.EVERY_KEY))
        for key, value in self.EVERY_KEY.items():
            if key != "points":
                self.assertEqual(cfg[key], value, key)
        self.assertEqual(cfg["points"]["areas"], 2)
        self.assertEqual(cfg["points"]["defect"], 2, "points not given keep their default")

    def test_an_unknown_key_names_the_closest_one(self):
        with self.assertRaises(ValueError) as e:
            loop_config.load(write_config({"risk_path": ["src/x/**"]}))
        self.assertIn("unknown key `risk_path`", str(e.exception))
        self.assertIn("did you mean `risk_paths`", str(e.exception))
        with self.assertRaises(ValueError) as e:
            loop_config.load(write_config({"zzzz": 1}))
        self.assertIn("known keys", str(e.exception))

    def test_bad_types_and_ranges_fail_with_the_key_name(self):
        cases = {
            "threshold": ({"threshold": 1}, "threshold:"),
            "threshold type": ({"threshold": "3"}, "threshold:"),
            "threshold bool": ({"threshold": True}, "threshold:"),
            "negative point": ({"points": {"no_tests": -1}}, "points:"),
            "point too high": ({"points": {"areas": 6}}, "points:"),
            "unknown point": ({"points": {"vibes": 1}}, "unknown point names vibes"),
            "opus cap": ({"max_opus_per_day": 51}, "max_opus_per_day:"),
            "risk word case": ({"risk_words": ["Date"]}, "risk_words:"),
            "risk word phrase": ({"risk_words": ["due date"]}, "risk_words:"),
            "bad regex": ({"commit_ref_pattern": "(feat"}, "commit_ref_pattern:"),
            "phrase without number": ({"merge_phrase": "OK merge"}, "merge_phrase:"),
            "deploy": ({"deploy": "manual"}, "deploy:"),
            "broad glob": ({"risk_paths": ["**"]}, "risk_paths:"),
            "deep feature root": ({"feature_roots": ["src/**/features"]}, "feature_roots:"),
            "empty prefix list": ({"branch_prefix": []}, "branch_prefix:"),
            "plan sections": ({"plan_sections": "short"}, "plan_sections:"),
            "improve": ({"improve": "yes"}, "improve:"),
        }
        for name, (data, text) in cases.items():
            with self.subTest(name):
                with self.assertRaises(ValueError) as e:
                    loop_config.load(write_config(data))
                self.assertIn(text, str(e.exception))

    def test_null_means_the_default(self):
        cfg = loop_config.load(write_config({"threshold": None, "deploy": None}))
        self.assertEqual((cfg["threshold"], cfg["deploy"]), (3, "auto"))

    def test_the_example_profile_loads_clean(self):
        cfg = load_profile()
        self.assertEqual(loop_config.prefixes(cfg), ("feat/", "docs/"))
        self.assertEqual(cfg["deploy"], "off")
        with open(PROFILE) as f:
            text = f.read()
        for secret_like in ("token", "secret", "password", "@", "AKfy"):
            self.assertNotIn(secret_like, text.lower() if secret_like.islower() else text)

    def test_the_seven_key_file_loads_to_the_same_values_as_before(self):
        repo_cfg = os.path.join(os.path.dirname(SKILL), ".github", "github-loop.json")
        data = {"owner": "lheiiyy", "owner_name": "Leo", "language": "Taglish", "base": "main",
                "branch_prefix": "claude/", "owner_associations": ["OWNER"], "improve": True}
        if os.path.exists(repo_cfg):
            with open(repo_cfg) as f:
                data = json.load(f)
        cfg = loop_config.load(write_config(data))
        before = dict(OLD_DEFAULTS, **{k: v for k, v in data.items() if v is not None})
        self.assertEqual({k: cfg[k] for k in OLD_DEFAULTS}, before)
        self.assertEqual(loop_config.prefixes(cfg), ("claude/",))
        empty = loop_config.load(write_config({}))
        self.assertEqual({k: empty[k] for k in OLD_DEFAULTS}, OLD_DEFAULTS)


class GlobTests(unittest.TestCase):
    MUST_MATCH = ["src/core/env.js", "src/env.js", "src/api/session.js", "src/repository/sheets.js",
                  "src/rules/scoring.js", "src/platform/lock.js", "src/platform/cache.js", "config/settings.json",
                  "docs/PERMISSIONS.md", "docs/DATA-MODEL.md", "docs/DECISIONS.md", "docs/BUSINESS-RULES.md"]
    MUST_NOT = ["src/ui/index.html", "src/rules/dates.js", "README.md", "docs/ROADMAP.md"]

    def hit(self, cfg, path):
        return any(rules.glob_match(path, g) for g in cfg["risk_paths"] + cfg["authority_docs"])

    def test_the_tdms_list(self):
        cfg = load_profile()
        for path in self.MUST_MATCH:
            with self.subTest(path=path):
                self.assertTrue(self.hit(cfg, path))
        for path in self.MUST_NOT:
            with self.subTest(path=path):
                self.assertFalse(self.hit(cfg, path))
                self.assertEqual(rules.sensitive_paths([path, "src/ui/app.js"]), [], "no built-in hit either")

    def test_matcher_rules(self):
        g = rules.glob_match
        self.assertFalse(g("src/a/b.js", "src/*.js"), "* does not cross /")
        self.assertTrue(g("src/b.js", "src/*.js"))
        self.assertTrue(g("src/env.js", "src/**/env*"), "** matches zero levels")
        self.assertTrue(g("src/a/b/c/env.js", "src/**/env*"))
        self.assertTrue(g("docs/permissions.md", "docs/PERMISSIONS.md"), "case is ignored")
        self.assertTrue(g("./src/x.js", "src/x.js"))
        self.assertTrue(g("src\\x.js", "src/x.js"))
        for path in ("src/x/y.js", "src/x/deep/z.js"):
            self.assertTrue(g(path, "src/x/**"))
            self.assertEqual(g(path, "src/x/**"), g(path, "src/x/"), "trailing /** and / are the same")
        self.assertFalse(g("src/xy/z.js", "src/x/"))
        self.assertFalse(g("other/src/x.js", "src/x.js"), "a plain pattern matches the whole path")
        self.assertTrue(g("src/a1.js", "src/a?.js"))
        self.assertTrue(g("src/a1.js", "src/a[0-9].js"))
        self.assertFalse(g("src/a/1.js", "src/a[!x]1.js"), "[!...] never matches /")
        self.assertTrue(g("CLAUDE.md", "**/CLAUDE.md"))
        self.assertTrue(g("pkg/CLAUDE.md", "**/CLAUDE.md"))


class KindsAndAreasTests(unittest.TestCase):
    def test_authority_docs_are_hits_but_not_sensitive_alone(self):
        self.assertEqual(rules.authority_hits(["CLAUDE.md", "pkg/AGENTS.md", "README.md"]),
                         ["CLAUDE.md", "pkg/AGENTS.md"])
        self.assertEqual(rules.sensitive_paths(["CLAUDE.md"]), [])
        self.assertEqual(rules.sensitive_paths(["docs/x.md"]), [])
        cfg = load_profile()
        self.assertEqual(rules.authority_hits(["docs/DECISIONS.md", "docs/ROADMAP.md"], cfg), ["docs/DECISIONS.md"])
        self.assertEqual(rules.risk_tier(["docs/DECISIONS.md"], None, cfg)[0], "low")

    def test_classify(self):
        kinds = rules.classify(["src/a.js", "tests/a.test.js", "src/__tests__/b.js", "src/b.spec.ts", "docs/x.md",
                                "package-lock.json", "web/package-lock.json", "yarn.lock", "dist/x.js",
                                "build/app.js", "src/vendor.min.js", "evals/test_x.py", "scripts/test_y.py",
                                ".github/workflows/t.yml"])
        self.assertEqual([p for p, k in kinds.items() if k == "source"], ["src/a.js", ".github/workflows/t.yml"])
        self.assertEqual(kinds["docs/x.md"], "doc")
        self.assertEqual(kinds["yarn.lock"], "lockfile")
        self.assertEqual(kinds["dist/x.js"], "generated")
        self.assertEqual(kinds["scripts/test_y.py"], "test")
        cfg = {"test_globs": ["spec/**"], "doc_globs": ["handbook/**"]}
        self.assertEqual(rules.classify(["spec/a.js", "handbook/a.html", "src/a.js"], cfg),
                         {"spec/a.js": "test", "handbook/a.html": "doc", "src/a.js": "source"})

    def test_feature_areas(self):
        paths = ["src/repository/sheets.js", "src/repository/cache.js", "src/ui/form.js", "app.js"]
        self.assertEqual(rules.feature_areas(paths), ["src/repository", "src/ui", "."])
        self.assertEqual(rules.feature_areas(paths, {"feature_roots": ["src/*"]}), ["src/repository", "src/ui", "."])
        self.assertEqual(rules.feature_areas(["src/a/b/c.js", "src/a/d.js"], {"feature_roots": ["src/*"]}), ["src/a"])
        self.assertEqual(rules.feature_areas(["src/a/b/c.js"], {"feature_roots": ["src/*", "src/*/*"]}), ["src/a/b"],
                         "the longest root wins")
        self.assertEqual(rules.feature_areas(["src/a/b/c.js"], {"feature_roots": ["src/*/*", "src/*"]}), ["src/a/b"],
                         "the longest root wins, whatever the order")
        self.assertEqual(rules.feature_areas(["lib/x/y.js"], {"feature_roots": ["src/*"]}), ["lib/x"])

    def test_the_skill_source_folder_is_sensitive(self):
        self.assertEqual(rules.sensitive_paths(["github-loop/scripts/x.py"]), ["github-loop/scripts/x.py"])
        self.assertEqual(rules.sensitive_paths(["github-loop/references/a.md"]), ["github-loop/references/a.md"])
        self.assertEqual(rules.risk_tier(["github-loop/SKILL.md"])[0], "high")
        self.assertEqual(rules.sensitive_paths(["src/github-loop/x.js"]), [], "only the top-level folder")

    def test_risk_paths_only_add(self):
        cfg = load_profile()
        self.assertEqual(rules.sensitive_paths(["src/platform/props.js", "src/ui/a.js"], cfg), ["src/platform/props.js"])
        self.assertEqual(rules.sensitive_paths(["src/platform/props.js"]), [], "without the setting it is ordinary")
        self.assertEqual(rules.sensitive_paths(["src/auth.js"], {"risk_paths": ["lib/**"]}), ["src/auth.js"],
                         "a setting never removes a built-in hit")
        self.assertEqual(rules.risk_tier(["src/platform/props.js"], None, cfg)[0], "high")


class SourceOnlyCountingTests(unittest.TestCase):
    def test_tests_and_docs_do_not_make_a_change_big(self):
        paths = [f"src/f{i}.js" for i in range(5)] + [f"tests/f{i}.test.js" for i in range(4)] + ["docs/notes.md"]
        r = pm.pick("review", paths=paths, session="sonnet")
        self.assertEqual((r["signals"]["large"], r["signals"]["files"], r["signals"]["source_files"]), (False, 10, 5))
        self.assertEqual(r["tier"], "sonnet")
        r = pm.pick("review", paths=[f"src/f{i}.js" for i in range(8)], session="sonnet")
        self.assertEqual((r["signals"]["large"], r["tier"]), (True, "opus"))
        lock = ["package-lock.json", "dist/a.js", "dist/b.js"] + [f"src/f{i}.js" for i in range(6)]
        self.assertFalse(pm.pick("review", paths=lock)["signals"]["large"])

    def test_route_passes_the_settings(self):
        cfg = load_profile()
        r = rt.route("review", ["src/platform/props.js", "tests/props.test.js"], session="sonnet", cfg=cfg)
        self.assertEqual((r["risk"], r["model"]["tier"]), ("high", "opus"))
        r = rt.route("review", ["src/platform/props.js", "tests/props.test.js"], session="sonnet")
        self.assertEqual((r["risk"], r["model"]["tier"]), ("normal", "sonnet"))
        specs = [f"spec/f{i}.js" for i in range(8)] + ["src/a.js"]
        self.assertEqual(rt.route("review", specs, session="sonnet")["model"]["tier"], "opus")
        r = rt.route("review", specs, session="sonnet", cfg={"test_globs": ["spec/**"]})
        self.assertEqual((r["model"]["tier"], r["model"]["signals"]["source_files"]), ("sonnet", 1),
                         "route hands the settings to the model pick")

    def test_command_lines_read_the_config(self):
        args = ("--step", "review", "--paths", "src/platform/props.js", "--session", "sonnet", "--config", PROFILE)
        code, out, _ = ts.run(os.path.join(SCRIPTS, "pick_model.py"), *args)
        self.assertEqual((code, out["tier"]), (0, "opus"))
        code, out, _ = ts.run(os.path.join(SCRIPTS, "route.py"), *args)
        self.assertEqual((code, out["risk"]), (0, "high"))
        bad = write_config({"threshold": 99})
        code, out, _ = ts.run(os.path.join(SCRIPTS, "route.py"), "--step", "review", "--config", bad)
        self.assertEqual(code, 2)
        self.assertIn("threshold:", out["error"])


class MergeGateTests(unittest.TestCase):
    def merge(self, ref="claude/readme", files=None, config=None):
        issue_ = ts.ap_issue(["code-working"])
        issue_.pop("comments")
        pr = dict(ts.MergeTests.PR, head=dict(ts.MergeTests.PR["head"], ref=ref))
        fx = {"issue.json": issue_, "comments.json": ts.MergeTests.REVIEWED, "pr.json": pr}
        if files is not None:
            fx["files.json"] = [{"filename": f} for f in files]
        extra = ("--config", write_config(config)) if config is not None else ("--config", write_config({}))
        return ts.run(os.path.join(SCRIPTS, "loop_gh.py"), "merge", "--repo", "o/r", "--issue", "9", "--pr", "6",
                      "--owner", ts.OWNER, "--fixtures", ts.write_fixtures(fx), "--dry-run", *extra)

    def test_a_prefix_list_is_accepted(self):
        cfg = {"branch_prefix": ["feat/", "docs/"]}
        self.assertEqual(self.merge("feat/x", config=cfg)[0], 0)
        self.assertEqual(self.merge("docs/x", config=cfg)[0], 0)
        code, out, _ = self.merge("fix/x", config=cfg)
        self.assertEqual(code, 5)
        self.assertIn("not a feat/ or docs/ branch", out["problem"])
        code, out, _ = self.merge("feat/x")
        self.assertEqual(code, 5)
        self.assertIn("not a claude/ branch", out["problem"])

    def test_risk_paths_reach_the_merge_gate(self):
        self.assertEqual(self.merge(files=["src/platform/props.js"])[0], 0)
        code, out, _ = self.merge(files=["src/platform/props.js"], config={"risk_paths": ["src/platform/**"]})
        self.assertEqual(code, 8, out)
        self.assertIn("src/platform/props.js", out["problem"])


class ProfileRunsTests(unittest.TestCase):
    """Acceptance: readiness.py and triage.py run on fixtures with the TDMS example profile."""

    def test_triage_and_readiness_run_with_the_profile(self):
        d = ts.write_fixtures({"issues.json": [ts.ap_item(9, ["to-code"])],
                               "9.events.json": [ts.event("to-code", ts.OWNER, "2026-10-29T11:50:00Z")]})
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", GITHUB_LOOP_CONFIG=PROFILE)
        code, out, err = ts.run_env(env, os.path.join(SCRIPTS, "triage.py"), "--repo", "o/r", "--role", "lead",
                                    "--owner", ts.OWNER, "--fixtures", d, "--now", ts.NOW)
        self.assertEqual(code, 0, err)
        self.assertIn("work", out)
        code, out, err = ts.run(os.path.join(SCRIPTS, "readiness.py"), "--repo", "o/r", "--owner", ts.OWNER,
                                "--config", PROFILE, "--fixtures", ts.write_fixtures(ts.ReadinessTests.BASE))
        self.assertEqual(code, 0, err)
        self.assertTrue(out["rows"])


if __name__ == "__main__":
    unittest.main()
