"""Static checks on the loop-fire workflow template (references/templates/loop-fire.yml).

The template is the source; a repository's own .github/workflows/loop-fire.yml must equal it.
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
TEMPLATE = os.path.join(SKILL, "references", "templates", "loop-fire.yml")
INSTALLED = os.path.join(SKILL, "..", "..", "..", ".github", "workflows", "loop-fire.yml")
with open(TEMPLATE, encoding="utf-8") as _f:
    TEXT = _f.read()
LINES = TEXT.splitlines()


class WorkflowChecks(unittest.TestCase):
    def test_no_pull_request_target(self):
        self.assertNotIn("pull_request_target", TEXT)
        self.assertNotRegex(TEXT, r"(?m)^\s*pull_request\s*:")

    def test_no_event_expression_in_run_lines(self):
        for line in LINES:
            if re.match(r"\s*run:", line):
                self.assertNotIn("${{", line, line)

    def test_actions_pinned_to_sha(self):
        uses = re.findall(r"(?m)^\s*-?\s*uses:\s*(\S+)", TEXT)
        self.assertTrue(uses)
        for u in uses:
            self.assertRegex(u, r"@[0-9a-f]{40}\Z", u)

    def test_secrets_only_in_fire_step_env(self):
        fire_start = next(i for i, l in enumerate(LINES) if "name: Fire the roles" in l)
        for i, l in enumerate(LINES):
            if "secrets." in l:
                self.assertGreater(i, fire_start, l)
                self.assertRegex(l, r"^\s+LOOP_(LEAD|CODE)_FIRE_(URL|TOKEN): \$\{\{ secrets\.LOOP_(LEAD|CODE)_FIRE_(URL|TOKEN) \}\}$")
        self.assertEqual(TEXT.count("secrets."), 4)

    def test_owner_if_concurrency_permissions(self):
        self.assertIn("if: github.actor == github.repository_owner", TEXT)
        self.assertRegex(TEXT, r"(?m)^concurrency:")
        self.assertIn("cancel-in-progress: false", TEXT)
        self.assertRegex(TEXT, r"(?m)^permissions:\n  contents: read\n")
        self.assertIn("persist-credentials: false", TEXT)

    def test_triggers(self):
        for t in ("issues:", "issue_comment:", "workflow_dispatch:"):
            self.assertIn(t, TEXT)

    def test_no_secret_values(self):
        for bad in ("trig_", "Bearer ", "sk-", "ghp_"):
            self.assertNotIn(bad, TEXT)

    def test_it_calls_only_scripts_that_exist(self):
        scripts = re.findall(r"\.claude/skills/github-loop/scripts/([a-z_]+\.py)", TEXT)
        self.assertEqual(sorted(set(scripts)), ["fire.py", "route_event.py"])
        for name in set(scripts):
            self.assertTrue(os.path.isfile(os.path.join(SKILL, "scripts", name)), name)

    def test_the_repo_copy_of_the_workflow_matches_the_template(self):
        if not os.path.isfile(INSTALLED):
            self.skipTest("this repository has no installed copy")
        with open(INSTALLED, encoding="utf-8") as f:
            installed = f.read()
        self.assertEqual(installed, TEXT, "copy references/templates/loop-fire.yml over .github/workflows/loop-fire.yml")


if __name__ == "__main__":
    unittest.main()
