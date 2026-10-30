import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_event as R  # noqa: E402

OWNER = "owner-test"
AUTO = "### Phase 1: Plan\nx\n### Phase 2: Build\ny\n"


def user(login=OWNER, assoc="OWNER"):
    return {"login": login, "author_association": assoc}


def issue(body=AUTO, labels=("to-code",), by=OWNER, assoc="OWNER", pr=False):
    d = {"number": 1, "body": body, "user": user(by, assoc), "labels": [{"name": n} for n in labels]}
    if pr:
        d["pull_request"] = {}
    return d


def issues_event(action="labeled", label="to-code", sender=OWNER, **kw):
    p = {"action": action, "issue": issue(**kw), "sender": {"login": sender}}
    if action == "labeled":
        p["label"] = {"name": label}
    return p


def comment(body, by=OWNER, assoc="OWNER", **kw):
    return {"action": "created", "issue": issue(**kw), "comment": {"body": body, "user": user(by, assoc)}}


def roles(event, payload):
    return R.route(event, payload, OWNER)


class IssueRows(unittest.TestCase):
    def test_autopilot_label_fires_lead(self):
        self.assertEqual(roles("issues", issues_event()), ["lead"])

    def test_opened_with_label_fires_lead(self):
        self.assertEqual(roles("issues", issues_event(action="opened")), ["lead"])

    def test_classic_issue_fires_code(self):
        self.assertEqual(roles("issues", issues_event(body="just do it")), ["code"])

    def test_other_label_nothing(self):
        self.assertEqual(roles("issues", issues_event(label="bug")), [])

    def test_issue_without_label_nothing(self):
        self.assertEqual(roles("issues", issues_event(action="opened", labels=())), [])

    def test_stranger_issue_nothing(self):
        self.assertEqual(roles("issues", issues_event(by="stranger", assoc="NONE")), [])

    def test_stranger_sender_nothing(self):
        self.assertEqual(roles("issues", issues_event(sender="stranger")), [])

    def test_pull_request_nothing(self):
        self.assertEqual(roles("issues", issues_event(pr=True)), [])

    def test_closed_action_nothing(self):
        p = issues_event()
        p["action"] = "closed"
        self.assertEqual(roles("issues", p), [])


class CommentRows(unittest.TestCase):
    def test_approved_fires_code(self):
        self.assertEqual(roles("issue_comment", comment("APPROVED")), ["code"])

    def test_approved_with_words_fires_code(self):
        self.assertEqual(roles("issue_comment", comment("APPROVED, go ahead")), ["code"])

    def test_revise_fires_lead(self):
        self.assertEqual(roles("issue_comment", comment("REVISE: smaller scope")), ["lead"])

    def test_continue_fires_both(self):
        self.assertEqual(roles("issue_comment", comment("CONTINUE: merged")), ["lead", "code"])

    def test_relayed_approval_fires_code(self):
        self.assertEqual(roles("issue_comment", comment("<!-- loop:v1 from=lead type=approval turn=3 -->\nAPPROVED by L in chat")), ["code"])

    def test_code_result_phase2_fires_lead(self):
        self.assertEqual(roles("issue_comment", comment("<!-- loop:v1 from=code type=result phase=2 pr=2 head=abc turn=4 -->\nx")), ["lead"])

    def test_lead_verdict_fires_code(self):
        self.assertEqual(roles("issue_comment", comment("<!-- loop:v1 from=lead type=verdict pr=2 head=abc verdict=approved turn=5 -->")), ["code"])

    def test_plan_question_summary_nothing(self):
        for h in ("from=lead type=plan phase=1 turn=2", "from=code type=question turn=3",
                  "from=code type=summary phase=2 turn=6"):
            self.assertEqual(roles("issue_comment", comment("<!-- loop:v1 %s -->\nx" % h)), [], h)

    def test_classic_result_nothing(self):
        self.assertEqual(roles("issue_comment", comment("<!-- loop:v1 from=code type=result turn=2 -->")), [])

    def test_lowercase_nothing(self):
        self.assertEqual(roles("issue_comment", comment("approved")), [])

    def test_keyword_not_at_start_nothing(self):
        self.assertEqual(roles("issue_comment", comment("I think APPROVED is fine")), [])

    def test_header_not_first_nothing(self):
        self.assertEqual(roles("issue_comment", comment("hello\n<!-- loop:v1 from=lead type=verdict -->")), [])

    def test_keyword_after_header_nothing(self):
        self.assertEqual(roles("issue_comment", comment("<!-- loop:v1 from=code type=question turn=3 -->\nAPPROVED")), [])

    def test_stranger_comment_nothing(self):
        self.assertEqual(roles("issue_comment", comment("APPROVED", by="stranger", assoc="NONE")), [])

    def test_stranger_issue_nothing(self):
        p = comment("APPROVED")
        p["issue"] = issue(by="stranger", assoc="NONE")
        self.assertEqual(roles("issue_comment", p), [])

    def test_comment_on_pull_request_nothing(self):
        self.assertEqual(roles("issue_comment", comment("APPROVED", pr=True)), [])

    def test_edited_nothing(self):
        p = comment("APPROVED")
        p["action"] = "edited"
        self.assertEqual(roles("issue_comment", p), [])


class Dispatch(unittest.TestCase):
    def test_owner_dispatch(self):
        p = {"sender": {"login": OWNER}, "inputs": {"role": "code"}}
        self.assertEqual(roles("workflow_dispatch", p), ["code"])

    def test_bad_role_or_sender(self):
        self.assertEqual(roles("workflow_dispatch", {"sender": {"login": OWNER}, "inputs": {"role": "x"}}), [])
        self.assertEqual(roles("workflow_dispatch", {"sender": {"login": "s"}, "inputs": {"role": "lead"}}), [])

    def test_unknown_event(self):
        self.assertEqual(roles("pull_request_target", comment("APPROVED")), [])


class Cli(unittest.TestCase):
    def test_output_file_and_no_comment_text(self):
        with tempfile.TemporaryDirectory() as d:
            pf, of = os.path.join(d, "p.json"), os.path.join(d, "out")
            with open(pf, "w") as f:
                json.dump(comment("APPROVED secret-looking-text"), f)
            self.assertEqual(R.main(["--event", "issue_comment", "--payload", pf, "--owner", OWNER, "--output", of]), 0)
            with open(of) as f:
                self.assertEqual(f.read(), "roles=code\nissue=1\n")


if __name__ == "__main__":
    unittest.main()
