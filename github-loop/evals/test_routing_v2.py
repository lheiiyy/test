"""Tests for PR-B of docs/plan-skill-fixes.md: review routing v2 (score, hard stops, Why line, confidence and
recheck, the Opus cap over a rolling window and holds, defect links, review history, outcomes fields,
improve proposals).
Run: python3 -B evals/test_routing_v2.py

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
import check_reply as cr  # noqa: E402
import config as loop_config  # noqa: E402
import improve  # noqa: E402
import loop_guard as g  # noqa: E402
import outcomes  # noqa: E402
import pick_model as pm  # noqa: E402
import route as rt  # noqa: E402
import test_scripts as ts  # noqa: E402  (shared fixtures; its test classes are not collected here)

PROFILE = os.path.join(SKILL, "references", "profiles", "tdms.example.json")
CASES = os.path.join(HERE, "routing_cases.json")
NO_HISTORY = {"changes_requested": False, "defects": []}
SHA1, SHA2 = ts.SHA1, ts.SHA2


def profile():
    return loop_config.load(PROFILE)


def plain():
    return loop_config.defaults()


def filler(path):
    if path.endswith(".md"):
        return "Some notes."
    if path.endswith(".html"):
        return "<p>row</p>"
    return "  value += 1;"


def diff_of(files):
    """A unified diff: each file's sample lines, then neutral filler up to its line count."""
    out = []
    for f in files:
        lines = list(f.get("sample", []))
        lines += [filler(f["path"])] * (f["lines"] - len(lines))
        out += [f"diff --git a/{f['path']} b/{f['path']}", f"--- a/{f['path']}", f"+++ b/{f['path']}",
                f"@@ -0,0 +1,{len(lines)} @@"] + ["+" + l for l in lines]
    return "\n".join(out) + "\n"


def unified(path, added=(), removed=(), deleted=False):
    head = [f"diff --git a/{path} b/{path}"] + (["deleted file mode 100644"] if deleted else []) + \
           [f"--- a/{path}", "+++ /dev/null" if deleted else f"+++ b/{path}", "@@ -1 +1 @@"]
    return "\n".join(head + ["-" + l for l in removed] + ["+" + l for l in added]) + "\n"


def review(paths, diff=None, cfg=None, history=NO_HISTORY, text="", round_=1, declared=None, session="sonnet"):
    return pm.pick("review", paths, text, round_=round_, session=session, declared=declared, cfg=cfg or plain(),
                   diff=diff, history=history)


class ScoreTableTests(unittest.TestCase):
    def test_every_case(self):
        with open(CASES) as f:
            cases = json.load(f)["cases"]
        self.assertEqual(len(cases), 13)
        for case in cases:
            with self.subTest(case["name"]):
                cfg = profile() if case["profile"] == "tdms" else plain()
                paths = [f["path"] for f in case["files"]]
                r = review(paths, diff_of(case["files"]), cfg)
                self.assertEqual(r["tier"], case["tier"])
                self.assertEqual(r["review"]["why"], case["why"])
                if "score" in case:
                    self.assertEqual(r["review"]["score"], case["score"])
                self.assertIn("Why: " + case["why"], r["model_line"]["inline"] if "inline" in r["model_line"] else
                              r["model_line"]["subagent"])

    def test_route_prints_a_why_line_for_every_case(self):
        with open(CASES) as f:
            cases = json.load(f)["cases"]
        for case in cases:
            with self.subTest(case["name"]):
                cfg = profile() if case["profile"] == "tdms" else plain()
                r = rt.route("review", [f["path"] for f in case["files"]], session="sonnet", cfg=cfg,
                             diff=diff_of(case["files"]), history=NO_HISTORY)
                for line in r["model"]["model_line"].values():
                    self.assertIn(". Why: ", line)

    def test_without_new_keys_docs_review_on_sonnet_and_sensitive_on_opus(self):
        self.assertEqual(review(["docs/guide.md"], diff_of([{"path": "docs/guide.md", "lines": 40}]))["tier"], "sonnet")
        self.assertEqual(review(["src/auth/login.js", "tests/login.test.js"])["tier"], "opus")

    def test_a_threshold_and_a_point_from_the_settings(self):
        files = [{"path": "src/app/a.js", "lines": 50}, {"path": "src/app/b.js", "lines": 50}]
        cfg = dict(plain(), threshold=2)
        self.assertEqual(review([f["path"] for f in files], diff_of(files), cfg)["tier"], "opus")
        cfg = dict(plain(), points=dict(loop_config.DEFAULT_POINTS, no_tests=0))
        r = review([f["path"] for f in files], diff_of(files), cfg)
        self.assertEqual((r["tier"], r["review"]["score"], r["review"]["why"]), ("sonnet", 0, "score 0 (no risk signals)"))
        cfg = dict(plain(), points=dict(loop_config.DEFAULT_POINTS, areas=0))
        three = [{"path": f"src/{d}/x.js", "lines": 10} for d in "abc"] + [{"path": "tests/x.test.js", "lines": 5}]
        self.assertEqual(review([f["path"] for f in three], diff_of(three), cfg)["review"]["score"], 0)

    def test_only_source_and_test_lines_count_toward_the_diff(self):
        files = [{"path": "src/app/a.js", "lines": 50}, {"path": "src/app/b.js", "lines": 50},
                 {"path": "tests/a.test.js", "lines": 20}, {"path": "docs/guide.md", "lines": 200}]
        self.assertEqual(review([f["path"] for f in files], diff_of(files))["review"]["score"], 0)

    def test_unknown_defect_history_is_said_and_scores_zero(self):
        r = review(["src/app/a.js", "tests/a.test.js"], history=None)
        self.assertEqual(r["review"]["why"], "score 0 (no risk signals; defect history unknown)")


class TokenTests(unittest.TestCase):
    def hits(self, line, path="src/app/a.js", cfg=None):
        return pm.risk_word_hits(pm.parse_diff(unified(path, added=[line])), [path], cfg or profile())

    def test_whole_words_only(self):
        for word in ("update", "validate", "generate", "migrate", "separate", "operate", "candidate",
                     "updateRecord", "validated_rows", "accurate", "dated"):
            with self.subTest(word):
                self.assertEqual(self.hits(f"const x = {word}(y)"), [])

    def test_identifiers_are_split(self):
        self.assertEqual(self.hits("const d = dueDate"), ["due", "date"])
        self.assertEqual(self.hits("calc_total(rows)"), ["total"])
        self.assertEqual(self.hits("if (isOverdue(t))"), ["overdue"])
        self.assertEqual(self.hits("computePrice(x)", cfg=plain()), ["price"])
        self.assertEqual(self.hits("late-fee-rate"), ["rate"])
        self.assertEqual(self.hits("SLA_LIMIT_2"), ["sla"])

    def test_only_changed_source_lines_count(self):
        def why(path, line):
            return review(["src/a.js", path], unified(path, added=[line]), profile())["review"]["why"]
        self.assertIn("risk words: due", why("src/b.js", "const due = 1"))
        self.assertNotIn("risk words", why("tests/a.test.js", "const due = 1"), "a test file never counts")
        self.assertNotIn("risk words", why("docs/a.md", "due date"), "a document never counts")
        context = "diff --git a/src/a.js b/src/a.js\n--- a/src/a.js\n+++ b/src/a.js\n@@ -1 +1 @@\n const dueDate = 1\n"
        self.assertEqual(pm.risk_word_hits(pm.parse_diff(context), ["src/a.js"], profile()), [], "context lines")
        self.assertEqual(self.hits("const dueDate = 1", cfg=plain()), [], "date words live only in a profile")


class HardStopTests(unittest.TestCase):
    def stop(self, paths, diff=None, **kw):
        return review(paths, diff, **kw)["review"]["hard_stop"]

    def test_each_hard_stop_on_its_own(self):
        self.assertEqual(self.stop(["src/auth.js", "tests/a.test.js"]), "risk path src/auth.js")
        self.assertEqual(self.stop(["src/a.js", "tests/a.test.js"], text="## Objective\nAdd role-based access.\n"),
                         "the goal mentions role-based")
        self.assertEqual(self.stop(["src/a.js", "tests/a.test.js"], declared="high"), "the plan declares Risk: high")
        self.assertEqual(self.stop(["src/a.js", "tests/a.test.js"], unified("tests/a.test.js", deleted=True,
                                                                          removed=["expect(x).toBe(1)"])),
                         "test deleted: tests/a.test.js")
        for skip in ("it.skip('x', fn)", "describe.only('x')", "xit('x')", "test.todo('later')",
                     "@unittest.skip('slow')"):
            with self.subTest(skip):
                self.assertEqual(self.stop(["src/a.js", "tests/a.test.js"], unified("tests/a.test.js", added=[skip])),
                                 "test skipped: tests/a.test.js")
        self.assertEqual(self.stop(["src/a.js", "tests/a.test.js"],
                                   unified("tests/a.test.js", removed=["  expect(total).toBe(3)"])),
                         "assertion removed: tests/a.test.js")
        self.assertIsNone(self.stop(["src/a.js", "tests/a.test.js"],
                                    unified("tests/a.test.js", removed=["  expect(a).toBe(3)"],
                                            added=["  expect(a).toBe(4)"])), "a changed assertion is fine")
        self.assertEqual(self.stop(["src/a.js", "tests/a.test.js"], round_=3), "the third review round")
        self.assertEqual(self.stop(["CLAUDE.md"]), "authority doc changed with no code")
        self.assertEqual(self.stop(["docs/DECISIONS.md", "tests/a.test.js"], cfg=profile()),
                         "authority doc changed with no code")
        self.assertIsNone(self.stop(["CLAUDE.md", "src/a.js", "tests/a.test.js"]))

    def test_a_hard_stop_wins_over_a_low_score_and_names_its_code(self):
        r = review(["src/platform/props.js", "tests/p.test.js"], cfg=profile())
        self.assertEqual((r["tier"], r["review"]["hard_stop_code"]), ("opus", "risk_path"))

    def test_the_owner_override_is_clamped_and_never_lowers_a_hard_stop(self):
        r = review(["src/a.js", "tests/a.test.js"], text="Model: haiku")
        self.assertEqual((r["tier"], r["forced"]), ("sonnet", True))
        self.assertIn("Why: owner's Model line (haiku; haiku lifted to the sonnet floor)", r["model_line"]["inline"])
        self.assertEqual(review(["src/a.js", "tests/a.test.js"], text="Model: sonnet")["tier"], "sonnet")
        for lower in ("sonnet", "haiku"):
            with self.subTest(lower):
                r = review(["src/auth.js"], text=f"Model: {lower}")
                self.assertEqual((r["tier"], r["forced_tier"]), ("opus", lower))
                self.assertIn("Why: hard stop (risk path src/auth.js)", r["model_line"]["subagent"])
                self.assertIn("cannot lower a hard stop", r["reasons"][0])
        r = review(["src/a.js", "tests/a.test.js"], text="Model: opus")
        self.assertEqual((r["tier"], r["forced_tier"]), ("opus", "opus"), "Model: opus always raises")
        self.assertNotEqual(review(["src/a.js"], text="Model: opus")["tier"], "fable")


class ContractAndDefectTests(unittest.TestCase):
    def test_public_contract(self):
        renamed = unified("src/api.js", removed=["export function listTrips(a) {"], added=["export function getTrips(a) {"])
        r = review(["src/api.js", "tests/api.test.js"], renamed)
        self.assertIn("public contract changed", r["review"]["why"])
        same = unified("src/api.js", removed=["export function listTrips(a) {"], added=["export function listTrips(a, b) {"])
        self.assertNotIn("public contract", review(["src/api.js", "tests/api.test.js"], same)["review"]["why"])
        exports = unified("src/api.js", removed=["module.exports = { a, b };"], added=["module.exports = { a };"])
        self.assertIn("public contract changed", review(["src/api.js", "tests/t.test.js"], exports)["review"]["why"])
        inner = unified("src/api.js", removed=["  function helper() {"])
        self.assertNotIn("public contract", review(["src/api.js", "tests/t.test.js"], inner)["review"]["why"])
        r = review(["src/api.js", "tests/t.test.js"], text="## Merge plan\nPublic contract: changed\n")
        self.assertIn("public contract changed", r["review"]["why"])

    def test_earlier_changes_and_a_post_merge_defect(self):
        paths = ["src/repository/sheets.js", "tests/sheets.test.js"]
        cfg = dict(plain(), feature_roots=["src/*"])
        history = {"changes_requested": True,
                   "defects": [{"pr": 7, "merged_at": "2026-10-01T00:00:00Z", "opened_at": "2026-10-10T00:00:00Z",
                                "files": ["src/repository/cache.js"]},
                               {"pr": 8, "merged_at": "2026-09-01T00:00:00Z", "opened_at": "2026-10-10T00:00:00Z",
                                "files": ["src/repository/old.js"]}]}
        r = review(paths, cfg=cfg, history=history)
        self.assertEqual(r["review"]["score"], 3)
        self.assertEqual(r["review"]["why"], "score 3 (post-merge defect in src/repository within 14 days; "
                                             "changes requested earlier)")
        late = dict(history, defects=history["defects"][1:], changes_requested=False)
        self.assertEqual(review(paths, cfg=cfg, history=late)["review"]["score"], 0, "older than 14 days")


class CheckReplyTests(unittest.TestCase):
    def problems(self, text):
        return cr.check(text, 5, ["reviewed"], ["code-working"], expect_from="lead")["problems"]

    def test_verdict_lines(self):
        self.assertEqual(self.problems(ts.verdict_text(5)), [])
        no_why = ts.verdict_text(5).replace(ts.VERDICT_MODEL, "Model: sonnet")
        self.assertTrue(any("Why:" in p for p in self.problems(no_why)))
        free = ts.verdict_text(5).replace(ts.VERDICT_MODEL, "Model: sonnet. Why: it felt fine")
        self.assertTrue(any("Why:" in p for p in self.problems(free)))
        for missing, name in (("Confidence: high\n", "Confidence"), ("Unchecked: none\n", "Unchecked")):
            with self.subTest(name):
                self.assertTrue(any(name in p for p in self.problems(ts.verdict_text(5).replace(missing, ""))))
        opus = ts.verdict_text(5).replace(ts.VERDICT_MODEL, "Model: opus. Why: hard stop (risk path src/auth.js)")
        opus = opus.replace("Confidence: high\n", "").replace("Unchecked: none\n", "")
        self.assertEqual(self.problems(opus), [], "only a sonnet verdict needs Confidence and Unchecked")
        gap = ts.verdict_text(5).replace(ts.VERDICT_MODEL, "Model: sonnet (wanted opus; ran inline, no subagent). "
                                                           "Why: hard stop (risk path src/auth.js)")
        self.assertEqual(self.problems(gap), [])
        owner = ts.verdict_text(5).replace(ts.VERDICT_MODEL, "Model: sonnet. Why: owner's Model line (sonnet)")
        self.assertEqual(self.problems(owner), [])

    def test_a_hold_note(self):
        text = "<!-- loop:v1 from=lead type=hold turn=5 -->\nOn hold: Opus cap 3/3 reached (last 5 hours).\n"
        self.assertEqual(cr.check(text, 5, ["needs-leo"], ["code-working"], expect_from="lead")["problems"], [])


def low_verdict(turn, verdict="approved", head=SHA1, unchecked="the CSV export path", recheck=False, model=None):
    text = ts.verdict_text(turn, verdict, head, confidence="low", unchecked=unchecked)
    if recheck:
        text = text.replace(f"turn={turn} -->", f"recheck=yes turn={turn} -->")
    if model:
        text = text.replace(ts.VERDICT_MODEL, model)
    return ts.c(text)


class CascadeTests(unittest.TestCase):
    def decide(self, comments, labels=("reviewed",)):
        return g.decide(ts.ap_issue(list(labels), comments), ts.OWNER)

    def status(self, comments, head=SHA1):
        return g.review_status(ts.ap_issue(["reviewed"], comments), ts.OWNER, head, pr=6)

    def test_a_low_confidence_approval_gets_one_recheck_before_the_merge(self):
        thread = ts.APPROVED_THREAD + [ts.result_reply(4), low_verdict(5)]
        d = self.decide(thread)
        self.assertEqual((d["work_type"], d["role"], d["head"]), ("review-recheck", "lead", SHA1))
        self.assertIn("recheck=yes", d["reply_header"])
        self.assertIn("the CSV export path", d["notes"])
        self.assertFalse(self.status(thread)["approved"])
        self.assertIn("recheck", self.status(thread)["reason"])

    def test_after_the_recheck_the_merge_follows_its_verdict(self):
        opus = "Model: opus (via subagent). Why: hard stop (risk path src/auth.js)"
        approved = ts.APPROVED_THREAD + [ts.result_reply(4), low_verdict(5), low_verdict(6, recheck=True, model=opus)]
        self.assertEqual(self.decide(approved)["work_type"], "merge")
        self.assertTrue(self.status(approved)["approved"])
        changes = ts.APPROVED_THREAD + [ts.result_reply(4), low_verdict(5),
                                        low_verdict(6, "changes", recheck=True, model=opus)]
        self.assertEqual(self.decide(changes)["work_type"], "fix")

    def test_at_most_one_recheck_per_head(self):
        again = ts.APPROVED_THREAD + [ts.result_reply(4), low_verdict(5), low_verdict(6, recheck=True)]
        self.assertEqual(self.decide(again)["work_type"], "merge", "a low-confidence recheck is not rechecked")
        self.assertTrue(self.status(again)["approved"])
        later = again + [low_verdict(7)]
        self.assertEqual(self.decide(later)["work_type"], "merge", "a later low review of the same head is not "
                                                                   "rechecked again")
        self.assertTrue(self.status(later)["approved"])

    def test_no_recheck_for_high_confidence_changes_or_opus(self):
        self.assertEqual(self.decide(ts.APPROVED_THREAD + [ts.result_reply(4), ts.verdict_reply(5)])["work_type"],
                         "merge")
        self.assertEqual(self.decide(ts.APPROVED_THREAD + [ts.result_reply(4), low_verdict(5, "changes")])["work_type"],
                         "fix")
        opus = low_verdict(5, model="Model: opus. Why: score 4 (3 feature areas; diff 150-400)")
        self.assertEqual(self.decide(ts.APPROVED_THREAD + [ts.result_reply(4), opus])["work_type"], "merge")

    def test_a_new_head_is_reviewed_as_usual(self):
        thread = ts.APPROVED_THREAD + [ts.result_reply(4), low_verdict(5, "changes"), ts.result_reply(6, SHA2)]
        d = self.decide(thread, ("to-review",))
        self.assertEqual((d["work_type"], d["head"], d["review_round"]), ("review", SHA2, 2))


def opus_reply(when, model="opus"):
    return dict(ts.c(f"<!-- loop:v1 from=lead type=verdict phase=2 pr=1 head={SHA1} verdict=approved turn=3 -->\n"
                     f"ok\nModel: {model}. Why: hard stop (risk path src/auth.js)\n"), created_at=when)


class CapTests(unittest.TestCase):
    RISKY = ts.REQUEST.replace("Add a README to odometer-trips.", "Add role-based permissions.")
    CAP = {"max_opus_per_window": 3}

    def triage(self, recent, issues=None, extra=None, now=ts.NOW, cfg=None):
        files = {"issues.json": issues or [ts.ap_item(9, ["to-code"], body=self.RISKY)],
                 "9.events.json": [ts.event("to-code", ts.OWNER, "2026-10-29T11:50:00Z")]}
        if recent is not None:
            files["comments.recent.json"] = recent
        files.update(extra or {})
        d = ts.write_fixtures(files)
        cfg_path = os.path.join(d, "cfg.json")
        with open(cfg_path, "w") as f:
            json.dump(self.CAP if cfg is None else cfg, f)
        code, out, err = ts.run(os.path.join(SCRIPTS, "triage.py"), "--repo", "o/r", "--owner", ts.OWNER, "--role",
                                "lead", "--fixtures", d, "--now", now, "--config", cfg_path)
        self.assertEqual(code, 0, err)
        return out

    def test_no_cap_by_default(self):
        many = [opus_reply("2026-10-29T11:0%d:00Z" % m) for m in range(9)]
        out = self.triage(many, cfg={})
        self.assertEqual((len(out["work"]), out["hold"]), (1, []))
        self.assertNotIn("opus_left", out["work"][0])
        self.assertEqual(self.triage(None, cfg={})["work"][0]["tier"], "opus", "nothing is read without a cap")

    def test_the_fourth_opus_item_is_held_and_stays_opus(self):
        three = [opus_reply("2026-10-29T1%d:00:00Z" % h) for h in (0, 1, 1)]
        out = self.triage(three)
        self.assertEqual(out["work"], [])
        self.assertEqual(len(out["hold"]), 1)
        held = out["hold"][0]
        self.assertEqual((held["tier"], held["work_type"], held["reason"]),
                         ("opus", "plan", "Opus cap 3/3 reached (last 5 hours)"))
        self.assertIn("to hold (Opus cap)", out["summary"])

    def test_under_the_cap_it_runs_and_counts(self):
        out = self.triage([opus_reply("2026-10-29T10:00:00Z")])
        self.assertEqual((out["work"][0]["tier"], out["work"][0]["opus_left"]), ("opus", 1))
        sonnet_only = [opus_reply("2026-10-29T10:00:00Z", model="sonnet")] * 5
        self.assertEqual(self.triage(sonnet_only)["work"][0]["opus_left"], 2, "sonnet replies do not count")

    def test_the_window_is_the_last_five_hours(self):
        recent = [opus_reply("2026-10-29T07:01:00Z")] * 3          # 4 h 59 min before NOW (12:00)
        self.assertEqual(len(self.triage(recent)["hold"]), 1)
        old = [opus_reply("2026-10-29T06:59:00Z")] * 3             # 5 h 1 min before NOW
        self.assertEqual(len(self.triage(old)["work"]), 1, "a slot frees up after 5 hours")
        self.assertEqual(len(self.triage(recent, cfg=dict(self.CAP, opus_window_hours=4))["work"]), 1)

    def test_the_owners_opus_is_counted_but_never_held(self):
        forced = ts.ap_item(9, ["to-code"], body=self.RISKY + "\nModel: opus\n")
        out = self.triage([opus_reply("2026-10-29T10:00:00Z")] * 3, issues=[forced])
        self.assertEqual((len(out["work"]), out["work"][0]["opus_left"]), (1, 0))

    def test_an_overruled_model_sonnet_is_still_held(self):
        """Model: sonnet on a review with a hard stop runs opus (R3), so it counts against the cap like any opus."""
        issue = ts.ap_item(9, ["to-review"], body=ts.REQUEST + "\nModel: sonnet\n")
        thread = ts.APPROVED_THREAD + [ts.result_reply(4)]
        out = self.triage([opus_reply("2026-10-29T10:00:00Z")] * 3, issues=[issue],
                          extra={"9.comments.json": thread, "pr6.files.json": [{"filename": "src/auth.js"}]})
        self.assertEqual((out["work"], out["hold"][0]["work_type"]), ([], "review"))

    def test_a_zero_cap_holds_every_opus_item(self):
        out = self.triage([], cfg={"max_opus_per_window": 0})
        self.assertEqual(out["hold"][0]["reason"], "Opus cap 0/0 reached (last 5 hours)")

    def test_a_held_issue_is_not_held_twice(self):
        hold = ts.c("<!-- loop:v1 from=lead type=hold turn=2 -->\nOn hold: Opus cap 3/3 reached (last 5 hours).")
        issue = ts.ap_item(9, ["to-code", "needs-leo"], body=self.RISKY)
        out = self.triage([opus_reply("2026-10-29T1%d:00:00Z" % h) for h in (0, 1, 1)], issues=[issue],
                          extra={"9.comments.json": [hold]})
        self.assertEqual(out["hold"], [])
        self.assertTrue(any("on hold" in i.get("reason", "") for i in out["ignored"]))

    def test_a_hold_is_not_a_reply(self):
        """A waiting APPROVED still counts after a hold note, so the build resumes by itself."""
        hold = ts.c("<!-- loop:v1 from=code type=hold turn=4 -->\nOn hold: Opus cap 3/3 reached (last 5 hours).")
        issue = ts.ap_issue(["awaiting-approval", "needs-leo"],
                            [ts.c(ts.plan_reply()["body"]), ts.c("APPROVED"), hold])
        self.assertEqual(g.decide(issue, ts.OWNER)["work_type"], "build")
        self.assertEqual(g.decide(issue, ts.OWNER)["next_turn"], 5, "the hold's turn still counts")

    def test_the_recheck_is_opus_and_counts(self):
        issue = ts.ap_item(9, ["reviewed"])
        thread = ts.APPROVED_THREAD + [ts.result_reply(4), low_verdict(5)]
        out = self.triage([], issues=[issue], extra={"9.comments.json": thread})
        self.assertEqual((out["work"][0]["work_type"], out["work"][0]["tier"], out["work"][0]["opus_left"]),
                         ("review-recheck", "opus", 2))

    def test_route_holds_only_with_a_cap(self):
        capped = dict(plain(), max_opus_per_window=3)
        r = rt.route("review", ["src/auth.js"], session="sonnet", cfg=capped, opus_left=0)
        self.assertEqual(r["hold"]["reason"], "Opus cap 3/3 reached (last 5 hours)")
        self.assertNotIn("hold", rt.route("review", ["src/auth.js"], session="sonnet", cfg=plain(), opus_left=0),
                         "no cap set")
        self.assertNotIn("hold", rt.route("review", ["src/auth.js"], session="sonnet", cfg=capped, opus_left=1))
        self.assertNotIn("hold", rt.route("review", ["src/a.js", "tests/a.test.js"], session="sonnet", cfg=capped,
                                          opus_left=0), "a sonnet step is never held")
        forced = rt.route("review", ["src/auth.js"], "## Objective\nx\nModel: opus\n", session="sonnet", cfg=capped,
                          opus_left=0)
        self.assertNotIn("hold", forced)
        lowered = rt.route("review", ["src/auth.js"], "## Objective\nx\nModel: sonnet\n", session="sonnet",
                           cfg=capped, opus_left=0)
        self.assertIn("hold", lowered, "a Model: sonnet that a hard stop overruled is still held, never downgraded")

    def run_gh(self, cmd, *args, fixtures=None, cfg="{}"):
        fx = ts.write_fixtures(fixtures or {"comments.json": []})
        path = os.path.join(fx, "cfg.json")
        with open(path, "w") as f:
            f.write(cfg)
        owner = ("--owner", ts.OWNER) if cmd == "hold" else ()  # PR-C: hold reads the newest owner-account note
        return ts.run(os.path.join(SCRIPTS, "loop_gh.py"), cmd, "--repo", "o/r", "--issue", "9", "--turn", "5",
                      "--from", "lead", "--fixtures", fx, "--dry-run", "--config", path, *owner, *args)

    def test_the_hold_command(self):
        code, out, _ = self.run_gh("hold", "--work-type", "review", "--reason", "Opus cap 3/3 reached (last 5 hours)")
        self.assertEqual(code, 0, out)
        calls = out["dry_run_calls"]
        self.assertIn("labels/code-working", calls[1])
        self.assertTrue(calls[2].endswith("labels[]=to-review") and calls[3].endswith("labels[]=needs-leo"))
        self.assertIn("the cap counts the last 5 hours", out["comment"])
        code, out, _ = self.run_gh("hold", "--work-type", "review", "--reason", "Opus cap 1/1 reached (last 3 hours)",
                                   cfg='{"opus_window_hours": 3}')
        self.assertIn("the cap counts the last 3 hours", out["comment"])
        code, out, _ = self.run_gh("hold", "--work-type", "review", "--reason", "tired")
        self.assertEqual((code, out["dry_run_calls"]), (1, []))


class DefectLinkTests(unittest.TestCase):
    """R7: the loop, not the owner, links a bug to the merged loop PR that caused it."""
    MERGED = {"merged_at": "2026-10-15T00:00:00Z", "head": {"ref": "claude/totals"}}

    def defect(self, pr_json, pr="12"):
        fx = ts.write_fixtures({"comments.json": [], "pr.json": pr_json})
        path = os.path.join(fx, "cfg.json")
        with open(path, "w") as f:
            f.write("{}")
        return ts.run(os.path.join(SCRIPTS, "loop_gh.py"), "defect", "--repo", "o/r", "--issue", "9", "--turn", "5",
                      "--pr", pr, "--fixtures", fx, "--dry-run", "--config", path)

    def test_it_posts_galing_sa_and_labels_bug(self):
        code, out, err = self.defect(self.MERGED)
        self.assertEqual(code, 0, err)
        self.assertEqual(out["defect_of"], 12)
        calls = out["dry_run_calls"]
        self.assertIn("-X POST repos/o/r/issues/9/comments", calls[0])
        self.assertTrue(calls[-1].endswith("labels[]=bug"))

    def test_only_a_merged_loop_pr(self):
        for pr_json in ({"merged_at": None, "head": {"ref": "claude/x"}},
                        {"merged_at": "2026-10-15T00:00:00Z", "head": {"ref": "someone/else"}}):
            with self.subTest(pr_json):
                code, out, _ = self.defect(pr_json)
                self.assertEqual((code, out["dry_run_calls"]), (1, []))

    def test_the_note_is_not_a_reply_and_passes_the_check(self):
        note = "<!-- loop:v1 from=lead type=defect pr=12 turn=3 -->\nGaling sa #12 (merged 2026-10-15)."
        self.assertEqual(cr.check(note, 3, None, None, expect_from="lead")["problems"], [])
        self.assertTrue(cr.check(note.replace("pr=12 ", ""), 3, None, None, expect_from="lead")["problems"])
        issue = ts.ap_issue(["awaiting-approval"], [ts.c(ts.plan_reply()["body"]), ts.c(note), ts.c("APPROVED")])
        self.assertEqual(g.decide(issue, ts.OWNER)["work_type"], "build")

    def test_review_history_and_outcomes_read_the_note(self):
        note = ts.c("<!-- loop:v1 from=lead type=defect pr=12 turn=3 -->\nGaling sa #12.")
        bug = dict(ts.ap_item(40, ["bug"]), body=ts.REQUEST, created_at="2026-10-20T00:00:00Z")
        files = {"issue.json": dict(ts.ap_issue(["to-review"]), comments=None), "comments.json": [],
                 "bug.json": [bug], "40.comments.json": [note], "pr12.json": self.MERGED,
                 "pr12.files.json": [{"filename": "src/rules/totals.js"}]}
        d = ts.write_fixtures(files)
        path = os.path.join(d, "cfg.json")
        with open(path, "w") as f:
            f.write("{}")
        code, out, err = ts.run(os.path.join(SCRIPTS, "review_history.py"), "--repo", "o/r", "--issue", "9",
                                "--owner", ts.OWNER, "--fixtures", d, "--config", path)
        self.assertEqual(code, 0, err)
        self.assertEqual([x["pr"] for x in out["defects"]], [12])
        record = dict(ts.ap_item(9, ["done"]), created_at="2026-10-01T00:00:00Z")
        summary = dict(ts.c("<!-- loop:v1 from=code type=summary phase=2 turn=7 -->\nMerged: yes\nModel: haiku"),
                       created_at="2026-10-15T00:00:00Z")
        d = ts.write_fixtures({"issues.json": [record, bug], "40.comments.json": [note],
                               "9.comments.json": ts.APPROVED_THREAD + [ts.result_reply(4, pr=12), ts.verdict_reply(5, pr=12),
                                                                        summary]})
        recs = {r["number"]: r for r in outcomes.collect("o/r", ts.OWNER, d, cfg=plain())["issues"]}
        self.assertTrue(recs[9]["defect_after"], "outcomes reads the loop's note on the bug issue")
        loaded = dict(bug, comments=[note])
        self.assertEqual(outcomes.defect_notes(loaded, ts.OWNER), [(12, "2026-10-20T00:00:00Z")])
        self.assertEqual(outcomes.defect_notes(dict(loaded, labels=[]), ts.OWNER), [], "only on a bug issue")


class HistoryScriptTests(unittest.TestCase):
    def run_history(self, files, cfg=None):
        d = ts.write_fixtures(files)
        cfg_path = os.path.join(d, "cfg.json")
        with open(cfg_path, "w") as f:
            json.dump(cfg or {}, f)
        return ts.run(os.path.join(SCRIPTS, "review_history.py"), "--repo", "o/r", "--issue", "9", "--owner", ts.OWNER,
                      "--fixtures", d, "--config", cfg_path)

    def test_changes_and_defects(self):
        issue = dict(ts.ap_issue(["to-review"]), comments=None)
        thread = ts.APPROVED_THREAD + [ts.result_reply(4), ts.verdict_reply(5, "changes"), ts.result_reply(6, SHA2)]
        bug = {"number": 30, "user": {"login": ts.OWNER}, "title": "Totals wrong after #12", "body": "see #12, #99, #13",
               "created_at": "2026-10-20T00:00:00Z"}
        stranger = dict(bug, number=31, user={"login": "mallory"}, title="#14")
        files = {"issue.json": issue, "comments.json": thread, "bug.json": [bug, stranger],
                 "pr12.json": {"merged_at": "2026-10-15T00:00:00Z", "head": {"ref": "claude/totals"}},
                 "pr12.files.json": [{"filename": "src/rules/totals.js"}],
                 "pr13.json": {"merged_at": "2026-10-15T00:00:00Z", "head": {"ref": "someone/else"}},
                 "pr14.json": {"merged_at": "2026-10-15T00:00:00Z", "head": {"ref": "claude/x"}}}
        code, out, err = self.run_history(files)
        self.assertEqual(code, 0, err)
        self.assertTrue(out["changes_requested"])
        self.assertEqual(out["defects"], [{"pr": 12, "merged_at": "2026-10-15T00:00:00Z",
                                           "opened_at": "2026-10-20T00:00:00Z", "files": ["src/rules/totals.js"]}])
        self.assertNotIn("Totals wrong", json.dumps(out), "issue text never leaves the script")

    def test_unreadable_parts_are_null(self):
        code, out, _ = self.run_history({})
        self.assertEqual((code, out["changes_requested"], out["defects"]), (0, None, []))
        self.assertTrue(out["errors"])


class OutcomesAndImproveTests(unittest.TestCase):
    def record(self, comments, labels=("done",), files=(), defects=()):
        return outcomes.record_for(ts.ap_issue(list(labels), comments), ts.OWNER, list(files), list(defects),
                                   dict(plain(), feature_roots=["src/*"]))

    def test_the_new_fields(self):
        summary = dict(ts.c("<!-- loop:v1 from=code type=summary phase=2 turn=7 -->\nMerged: yes\nModel: haiku"),
                       created_at="2026-10-10T00:00:00Z")
        hold = ts.c("<!-- loop:v1 from=lead type=hold turn=3 -->\nOn hold: Opus cap 3/3 reached (last 5 hours).")
        thread = ts.APPROVED_THREAD + [hold, ts.result_reply(4), low_verdict(5),
                                       low_verdict(6, recheck=True), summary]
        r = self.record(thread, files=["src/ui/a.js", "tests/a.test.js"], defects=[(6, "2026-10-20T00:00:00Z")])
        self.assertEqual((r["review_score"], r["why"], r["hard_stop"], r["confidence"]), (1, ["lines"], None, "low"))
        self.assertEqual((r["rechecked"], r["cap_parked"], r["areas"], r["defect_after"]), (True, True, ["src/ui"], True))
        stopped = self.record(ts.APPROVED_THREAD + [ts.result_reply(4), ts.c(ts.verdict_text(5).replace(
            ts.VERDICT_MODEL, "Model: opus. Why: hard stop (risk path src/auth.js)"))])
        self.assertEqual((stopped["review_score"], stopped["hard_stop"]), (None, "risk_path"))

    def test_free_text_is_rejected(self):
        r = self.record(ts.APPROVED_THREAD + [ts.result_reply(4), ts.verdict_reply(5)])
        for key, bad in (("why", ["it felt risky"]), ("hard_stop", "because"), ("confidence", "medium"),
                         ("areas", ["src/a; rm -rf /"])):
            with self.subTest(key):
                with self.assertRaises(ValueError):
                    outcomes.validate(dict(r, **{key: bad}))

    def base(self, n, **changes):
        r = self.record(ts.APPROVED_THREAD + [ts.result_reply(4), ts.verdict_reply(5)])
        return dict(r, number=n, **changes)

    def test_routing_proposals_need_three_issues(self):
        calm = [self.base(n, models={"verdict": "opus"}, review_score=4, merged=True) for n in (1, 2, 3)]
        missed = [self.base(n, models={"verdict": "sonnet"}, defect_after=True, areas=["src/rules"]) for n in (4, 5, 6)]
        unsure = [self.base(n, confidence="low") for n in (7, 8, 9)]
        held = [self.base(n, cap_parked=True) for n in (10, 11, 12)]
        ids = {p["id"]: p for p in improve.proposals(calm + missed + unsure + held)}
        for pid in ("routing-opus-found-nothing", "routing-sonnet-then-defect", "routing-low-confidence",
                    "routing-cap-holds"):
            self.assertIn(pid, ids)
        self.assertIn("src/rules", ids["routing-sonnet-then-defect"]["proposal"])
        self.assertTrue(ids["routing-cap-holds"]["needs_owner_approval"])
        self.assertEqual(improve.proposals(calm[:2] + missed[:2] + unsure[:2] + held[:2]), [])

    def test_open_issue_dry_run_posts_once_and_writes_no_file(self):
        held = [self.base(n, cap_parked=True) for n in (10, 11, 12)]
        d = tempfile.mkdtemp()
        path = os.path.join(d, "outcomes.json")
        with open(path, "w") as f:
            json.dump({"issues": held}, f)
        before = set(os.listdir(d))
        fx = ts.write_fixtures({"improve_issues.json": []})
        args = (os.path.join(SCRIPTS, "improve.py"), "--input", path, "--open-issue", "--repo", "o/r", "--dry-run",
                "--fixtures", fx, "--config", os.path.join(fx, "none.json"))
        code, out, err = ts.run(*args)
        self.assertEqual(code, 0, err)
        calls = out["issue"]["dry_run_calls"]
        self.assertEqual(len(calls), 1)
        self.assertIn("-X POST repos/o/r/issues", calls[0])
        self.assertIn("labels[]=improve-proposal", calls[0])
        self.assertEqual(set(os.listdir(d)), before)
        title = out["issue"]["title"]
        fx2 = ts.write_fixtures({"improve_issues.json": [{"title": title}]})
        code, out, _ = ts.run(*args[:-4], "--fixtures", fx2, "--config", os.path.join(fx2, "none.json"))
        self.assertEqual((code, out["issue"]["opened"]), (0, False))
        self.assertNotIn("dry_run_calls", out["issue"])


if __name__ == "__main__":
    unittest.main()
