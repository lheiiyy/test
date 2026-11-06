"""Tests for PR-C of docs/plan-skill-fixes.md: process fit (lite plans, plan_dir, commit references, branch
prefix lists, the merge phrase and exit 10, deploy off, readiness wording, the smoke test).
Run: python3 -B evals/test_process_fit.py

Offline: GitHub is simulated with fixtures, as in test_scripts.py. Kept out of the packaged skill.
"""
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPTS = os.path.join(SKILL, "scripts")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import check_plan  # noqa: E402
import check_reply as cr  # noqa: E402
import config as loop_config  # noqa: E402
import loop_gh  # noqa: E402
import readiness  # noqa: E402
import test_scripts as ts  # noqa: E402  (shared fixtures; its test classes are not collected here)

LITE_PLAN = """# Plan: status labels on the trip list

## Goal
Show each trip's status label on the list screen.

## Tasks
1. Code: add the labels to src/ui/trip-list.js; check: the list shows them for all four statuses.
Model plan: build sonnet; review sonnet (score 2); fix sonnet, opus on a second attempt.

## Tests
`node --test` covers the four labels; the 375 px screenshot shows them.

## Merge plan
Branch feat/trip-labels, method: merge commit, after an approved Lead verdict. Deploy: none (the owner deploys).
Commits: feat(#12): <what changed>
Risk: normal
CI required: no
Files in scope: src/ui/, tests/, docs/plans/

AWAITING APPROVAL
"""
LITE = {"plan_sections": "lite"}
PATTERN = r"^(Commits: )?(feat|docs)\(#\d+\)"


def problems(text, rel="docs/plans/plan-trip-labels.md", cfg=None, changed=None):
    return check_plan.check(text, rel, changed, cfg)["problems"]


def write(text, name="cfg.json"):
    d = tempfile.mkdtemp()
    path = os.path.join(d, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text if isinstance(text, str) else json.dumps(text))
    return path


class PlanTests(unittest.TestCase):
    def test_a_lite_plan_passes(self):
        self.assertEqual(problems(LITE_PLAN, cfg=LITE), [])
        cfg = dict(LITE, plan_dir="docs/plans", commit_ref_pattern=PATTERN)
        self.assertEqual(problems(LITE_PLAN, cfg=cfg), [], "the TDMS-style lite plan")

    def test_a_lite_plan_without_a_merge_plan_fails(self):
        cut = LITE_PLAN.split("## Merge plan")[0] + "AWAITING APPROVAL\n"
        self.assertIn("missing section: Merge plan", problems(cut, cfg=LITE))

    def test_the_merge_plan_lines_and_the_tier_always_stay(self):
        self.assertTrue(any("Risk:" in p for p in problems(LITE_PLAN.replace("Risk: normal\n", ""), cfg=LITE)))
        self.assertTrue(any("CI required" in p for p in problems(LITE_PLAN.replace("CI required: no\n", ""), cfg=LITE)))
        no_tier = LITE_PLAN.replace("Model plan: build sonnet; review sonnet (score 2); fix sonnet, opus on a second "
                                    "attempt.", "Model plan: later.")
        self.assertTrue(any("model plan" in p for p in problems(no_tier, cfg=LITE)))
        self.assertTrue(any("AWAITING APPROVAL" in p for p in problems(LITE_PLAN.replace("AWAITING APPROVAL", "ok"),
                                                                          cfg=LITE)))
        self.assertTrue(any("branch" in p.lower() for p in problems(LITE_PLAN.replace("Branch feat/trip-labels, ", ""),
                                                                    cfg=LITE)), "Merge plan topics stay")

    def test_the_heavy_default_is_unchanged(self):
        self.assertEqual(ts.check_plan_text(ts.GOOD_PLAN), [])
        self.assertEqual(problems(ts.GOOD_PLAN, rel="docs/plan-readme.md", cfg=loop_config.defaults()), [])
        heavy = problems(LITE_PLAN)
        self.assertIn("missing section: Business plan", heavy)
        self.assertIn("missing section: Readiness", heavy)

    def test_a_list_of_sections_always_gets_the_merge_plan(self):
        self.assertEqual(check_plan.required_sections({"plan_sections": ["Goal", "Tasks"]}),
                         ["Goal", "Tasks", "Merge plan"])
        self.assertEqual(problems(LITE_PLAN, cfg={"plan_sections": ["Goal", "Tests"]}), [], "a tier anywhere counts")

    def test_a_plan_outside_plan_dir_fails(self):
        cfg = dict(LITE, plan_dir="docs/plans")
        self.assertTrue(any("must be under docs/plans/" in p for p in problems(LITE_PLAN, rel="docs/plan-x.md", cfg=cfg)))
        self.assertEqual(problems(LITE_PLAN, rel="docs/plans/sub/plan-x.md", cfg=cfg), [])

    def test_the_commit_reference_format(self):
        cfg = dict(LITE, commit_ref_pattern=PATTERN)
        cut = LITE_PLAN.replace("Commits: feat(#12): <what changed>\n", "")
        self.assertTrue(any("commit reference format" in p for p in problems(cut, cfg=cfg)))
        self.assertEqual(problems(cut, cfg=LITE), [], "no pattern, no rule")

    def test_the_command_line_and_post_plan_read_the_settings(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "docs", "plans"))
        plan = os.path.join(d, "docs", "plans", "plan-x.md")
        with open(plan, "w") as f:
            f.write(LITE_PLAN)
        code, out, _ = ts.run(os.path.join(SCRIPTS, "check_plan.py"), plan, "--config", write(LITE))
        self.assertEqual((code, out["problems"]), (0, []))
        code, out, _ = ts.run(os.path.join(SCRIPTS, "check_plan.py"), plan, "--config", write({}))
        self.assertEqual(code, 1)
        a = types.SimpleNamespace(plan_file=plan, no_plan_file=None, git_base=None, cfg=loop_config.load(write(LITE)))
        self.assertEqual(loop_gh.plan_file_problems(a), [])
        a.cfg = loop_config.defaults()
        self.assertTrue(loop_gh.plan_file_problems(a))


def commit(sha, message, date="2026-10-29T10:00:00Z"):
    return {"sha": sha, "commit": {"message": message, "committer": {"date": date}}}


def phrase_comment(text="OK i-merge #6", when="2026-10-29T11:00:00Z", user=None):
    return dict(ts.c(text), created_at=when, **({"user": {"login": user}, "author_association": "NONE"} if user else {}))


class MergeGateTests(unittest.TestCase):
    PHRASE = {"merge_phrase": "OK i-merge #{n}"}

    def merge(self, cfg, commits=None, pr_comments=None, issue_extra=(), files=None, ref="claude/readme", extra=()):
        issue_ = ts.ap_issue(["code-working"])
        issue_.pop("comments")
        pr = dict(ts.MergeTests.PR, head=dict(ts.MergeTests.PR["head"], ref=ref))
        fx = {"issue.json": issue_, "comments.json": ts.MergeTests.REVIEWED + list(issue_extra), "pr.json": pr,
              "commits.json": commits if commits is not None else [commit(ts.SHA1, "feat(#9): add the README")],
              "pr_comments.json": pr_comments or []}
        if files is not None:
            fx["files.json"] = [{"filename": f} for f in files]
        return ts.run(os.path.join(SCRIPTS, "loop_gh.py"), "merge", "--repo", "o/r", "--issue", "9", "--pr", "6",
                      "--owner", ts.OWNER, "--fixtures", ts.write_fixtures(fx), "--dry-run", "--config", write(cfg),
                      *extra)

    def test_without_the_new_keys_nothing_changes(self):
        self.assertEqual(self.merge({})[0], 0)
        self.assertEqual(self.merge({}, files=["src/auth.js"])[0], 8)

    def test_a_missing_commit_reference_fails_and_names_the_commit(self):
        cfg = {"commit_ref_pattern": r"^(feat|docs)\(#\d+\)"}
        bad = [commit("c" * 40, "feat(#9): add the README"), commit(ts.SHA1, "fix typo\n\nlonger text")]
        code, out, _ = self.merge(cfg, commits=bad)
        self.assertEqual(code, 5)
        self.assertIn(f'{ts.SHA1[:7]} "fix typo"', out["problem"])
        self.assertNotIn("ccccccc", out["problem"], "a matching commit is not named")
        self.assertEqual(self.merge(cfg)[0], 0)
        base_merge = dict(commit("d" * 40, "Merge branch 'main' into feat/x"), parents=[{"sha": "1"}, {"sha": "2"}])
        self.assertEqual(self.merge(cfg, commits=[base_merge, commit(ts.SHA1, "feat(#9): fix")])[0], 0,
                         "merging the base into the branch (the exit-5 fix) is not a task commit")

    def test_branch_prefix_lists(self):
        cfg = {"branch_prefix": ["feat/", "docs/"]}
        self.assertEqual(self.merge(cfg, ref="feat/x")[0], 0)
        self.assertEqual(self.merge(cfg, ref="docs/x")[0], 0)
        self.assertEqual(self.merge(cfg, ref="fix/x")[0], 5)

    def test_a_missing_phrase_is_exit_10_with_its_own_message(self):
        code, out, _ = self.merge(self.PHRASE)
        self.assertEqual(code, 10)
        self.assertIn("waiting for the owner's merge phrase: comment `OK i-merge #6` on the PR", out["problem"])
        self.assertNotIn("high-risk", out["problem"])
        self.assertEqual(out["dry_run_calls"], [])

    def test_high_risk_waits_for_the_phrase_first_then_the_owner(self):
        self.assertEqual(self.merge(self.PHRASE, files=["src/auth.js"])[0], 10)
        code, out, _ = self.merge(self.PHRASE, files=["src/auth.js"], pr_comments=[phrase_comment()])
        self.assertEqual(code, 8, out)
        self.assertIn("high-risk", out["problem"])

    def test_wrong_phrases_are_ignored(self):
        cases = {"a stranger": phrase_comment(user="mallory"),
                 "older than the head": phrase_comment(when="2026-10-29T09:00:00Z"),
                 "another PR number": phrase_comment("OK i-merge #7"),
                 "extra words": phrase_comment("OK i-merge #6 please"),
                 "lowercase": phrase_comment("ok i-merge #6")}
        for name, comment in cases.items():
            with self.subTest(name):
                self.assertEqual(self.merge(self.PHRASE, pr_comments=[comment])[0], 10)

    def test_the_phrase_on_the_pr_or_on_the_issue_passes(self):
        self.assertEqual(self.merge(self.PHRASE, pr_comments=[phrase_comment()])[0], 0)
        self.assertEqual(self.merge(self.PHRASE, issue_extra=[phrase_comment()])[0], 0)
        self.assertEqual(self.merge(self.PHRASE, pr_comments=[phrase_comment("  OK i-merge #6\n")])[0], 0)

    def test_an_unknown_head_time_never_passes(self):
        self.assertEqual(self.merge(self.PHRASE, commits=[], pr_comments=[phrase_comment()])[0], 10)

    def test_a_merge_quote_does_not_clear_exit_10(self):
        quote = ("--owner-merge-quote", "MERGE it, I checked it")
        self.assertEqual(self.merge(self.PHRASE, extra=quote)[0], 10)
        self.assertEqual(self.merge(self.PHRASE, files=["src/auth.js"], extra=quote)[0], 10)
        code, out, _ = self.merge(self.PHRASE, files=["src/auth.js"], pr_comments=[phrase_comment()], extra=quote)
        self.assertEqual(code, 0, out)

    def test_the_exit_code_is_documented(self):
        for path in ("scripts/loop_gh.py", "SKILL.md", "references/runbook.md", "references/autopilot.md",
                     "references/lead.md"):
            with open(os.path.join(SKILL, path), encoding="utf-8") as f:
                text = f.read()
            with self.subTest(path):
                self.assertTrue("exit 10" in text or "Exit code 10" in text or "10 waiting" in text)


class HoldForThePhraseTests(unittest.TestCase):
    REASON = "Waiting for the owner's merge phrase: OK i-merge #6"

    def hold(self, comments=(), work_type="merge", reason=REASON):
        fx = ts.write_fixtures({"comments.json": list(comments)})
        return ts.run(os.path.join(SCRIPTS, "loop_gh.py"), "hold", "--repo", "o/r", "--issue", "9", "--turn", "7",
                      "--from", "code", "--work-type", work_type, "--reason", reason, "--owner", ts.OWNER,
                      "--fixtures", fx, "--dry-run", "--config", write({}))

    def test_it_keeps_reviewed_and_adds_needs_leo(self):
        code, out, _ = self.hold()
        self.assertEqual(code, 0, out)
        self.assertIn("Comment the phrase on the PR or here", out["comment"])
        self.assertTrue(out["dry_run_calls"][-2].endswith("labels[]=reviewed"))
        self.assertTrue(out["dry_run_calls"][-1].endswith("labels[]=needs-leo"))

    def test_the_same_hold_is_not_posted_twice(self):
        earlier = ts.c(f"<!-- loop:v1 from=code type=hold turn=6 -->\nOn hold: {self.REASON}. Every other merge gate "
                       "is green.")
        code, out, _ = self.hold([earlier])
        self.assertEqual((code, out["already_posted"]), (0, True))
        self.assertFalse(any("/comments" in c for c in out["dry_run_calls"]))
        newer = ts.MergeTests.REVIEWED[-1]
        self.assertFalse(self.hold([earlier, newer])[1].get("already_posted"), "a reply after it: post again")

    def test_only_for_a_merge(self):
        self.assertEqual(self.hold(work_type="review")[0], 1)
        self.assertEqual(self.hold(reason="Waiting for lunch")[0], 1)


class DeployOffTests(unittest.TestCase):
    OFF = ts.SUMMARY.replace("Deployed: not part of this plan.", "Deployed: no (deploy: off, manual step for the owner)")

    def finish(self, summary, cfg):
        issue_ = ts.ap_issue(["code-working"])
        issue_.pop("comments")
        fx = ts.write_fixtures({"issue.json": issue_, "comments.json": ts.APPROVED_THREAD,
                                "pr.json": {"merged": True, "merge_commit_sha": ts.SHA2}})
        path = write(summary, "summary.md")
        return ts.run(os.path.join(SCRIPTS, "loop_gh.py"), "finish", "--repo", "o/r", "--issue", "9", "--pr", "6",
                      "--turn", "6", "--file", path, "--owner", ts.OWNER, "--fixtures", fx, "--dry-run",
                      "--config", write(cfg))

    def test_the_report_line(self):
        self.assertEqual(cr.check(self.OFF, 6, ["done"], ["code-working"], expect_from="code")["problems"], [])
        self.assertEqual(self.finish(self.OFF, {"deploy": "off"})[0], 0)
        code, out, _ = self.finish(ts.SUMMARY.replace("Deployed: not part of this plan.", "Deployed: yes, to Pages"),
                                   {"deploy": "off"})
        self.assertEqual(code, 1)
        self.assertIn("Deployed: no (deploy: off, manual step for the owner)", out["problems"][0])
        self.assertEqual(self.finish(ts.SUMMARY.replace("Deployed: not part of this plan.", "Deployed: yes, to Pages"),
                                     {})[0], 0, "deploy auto is unchanged")


class ReadinessTests(unittest.TestCase):
    FREE_403 = "HTTP 403: Upgrade to GitHub Pro or make this repository public to enable this feature."

    def rows(self, extra=None, cfg=None):
        fx = ts.write_fixtures(dict(ts.ReadinessTests.BASE, **(extra or {})))
        for name, text in (extra or {}).items():
            if name.endswith(".error"):
                with open(os.path.join(fx, name), "w") as f:
                    f.write(text)
        rows, err = readiness.audit("o/r", ts.OWNER, fx, cfg=dict(loop_config.defaults(), **(cfg or {})))
        self.assertIsNone(err)
        return {r["item"]: r for r in rows}

    def test_a_free_plan_403_or_a_404_says_plainly_there_is_no_protection(self):
        for error in (self.FREE_403, "HTTP 404: Branch not protected"):
            with self.subTest(error):
                r = self.rows({"protection.json.error": error})["Branch protection on main"]
                self.assertEqual(r["status"], "NOT REQUIRED")
                self.assertIn("No branch protection (private repo on a free plan). `loop_gh.py merge` is the only "
                              "gate. Do not merge from the GitHub page", r["evidence"])
        other = self.rows({"protection.json.error": "HTTP 403: Resource not accessible by integration"})
        self.assertEqual(other["Branch protection on main"]["status"], "UNVERIFIED")
        self.assertEqual(self.rows()["Branch protection on main"]["status"], "UNVERIFIED", "a missing fixture")

    def test_markdown_shows_the_wording(self):
        fx = ts.write_fixtures(dict(ts.ReadinessTests.BASE))
        with open(os.path.join(fx, "protection.json.error"), "w") as f:
            f.write(self.FREE_403)
        proc = subprocess.run([sys.executable, "-B", os.path.join(SCRIPTS, "readiness.py"), "--repo", "o/r", "--owner",
                               ts.OWNER, "--fixtures", fx, "--markdown", "--config", write({})],
                              capture_output=True, text=True)
        code, out = proc.returncode, proc.stdout
        self.assertEqual(code, 0, proc.stderr)
        self.assertIn("| Branch protection on main | NOT REQUIRED | No branch protection (private repo on a free plan)",
                      out)

    def test_the_open_pr_row_uses_the_prefixes(self):
        pulls = [{"number": 1, "head": {"ref": "feat/a"}}, {"number": 2, "head": {"ref": "claude/b"}}]
        row = self.rows({"pulls.json": pulls}, {"branch_prefix": ["feat/", "docs/"]})["Open pull requests"]
        self.assertIn("not from the loop: #2 claude/b", row["evidence"])
        self.assertNotIn("#1", row["evidence"])
        row = self.rows({"pulls.json": pulls})["Open pull requests"]
        self.assertIn("not from the loop: #1 feat/a", row["evidence"], "claude/ by default, as before")

    def test_the_merge_gate_and_pages_rows(self):
        self.assertNotIn("Merge gate", self.rows())
        gate = self.rows(cfg={"merge_phrase": "OK i-merge #{n}"})["Merge gate"]
        self.assertIn("`OK i-merge #<PR number>`", gate["evidence"])
        self.assertEqual(self.rows()["GitHub Pages / hosting"]["status"], "UNVERIFIED")
        self.assertEqual(self.rows(cfg={"deploy": "off"})["GitHub Pages / hosting"]["status"], "NOT REQUIRED")


class SmokeTestDocTests(unittest.TestCase):
    def test_six_parts_and_the_link(self):
        with open(os.path.join(SKILL, "references", "smoke-test.md"), encoding="utf-8") as f:
            text = f.read()
        for n, name in enumerate(("Events", "Negative test", "Model check", "Cost log", "Notes", "Pass criteria"), 1):
            self.assertIn(f"## {n}. {name}", text)
        for must in ("Model: sonnet", "hard stop", "loop_gh.py defect", "| Run | Role | Model | Usage before | "
                     "Usage after | Delta |", "API trigger", "not** an event", "Refresh `.claude/skills/github-loop/`"):
            self.assertIn(must, text)
        with open(os.path.join(SKILL, "references", "events.md"), encoding="utf-8") as f:
            self.assertIn("references/smoke-test.md", f.read())


if __name__ == "__main__":
    unittest.main()
