import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import fire as F  # noqa: E402

URL = "https://api.anthropic.com/v1/claude_code/routines/trig_DUMMY123/fire"
DUMMY = "dummy-secret-value-xyz"
ENV = {"LOOP_LEAD_FIRE_URL": URL, "LOOP_LEAD_FIRE_TOKEN": DUMMY,
       "LOOP_CODE_FIRE_URL": URL, "LOOP_CODE_FIRE_TOKEN": DUMMY}


class Resp:
    def __init__(self, status=200):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Opener:
    def __init__(self, status=200, boom=None):
        self.calls, self.status, self.boom = [], status, boom

    def __call__(self, req, timeout=None):
        self.calls.append((req, timeout))
        if self.boom:
            raise self.boom
        return Resp(self.status)


def run(args, env, opener):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = F.main(args, env, opener)
    return code, out.getvalue()


class FireTests(unittest.TestCase):
    def test_request_shape(self):
        op = Opener()
        code, out = run(["--roles", "lead", "--issue", "16", "--event", "issue_comment"], ENV, op)
        self.assertEqual(code, 0)
        req, timeout = op.calls[0]
        self.assertEqual(timeout, 20)
        self.assertEqual(req.full_url, URL)
        self.assertEqual(req.get_method(), "POST")
        h = {k.lower(): v for k, v in req.header_items()}
        self.assertEqual(h["anthropic-beta"], "experimental-cc-routine-2026-04-01")
        self.assertEqual(h["anthropic-version"], "2023-06-01")
        self.assertEqual(h["authorization"], "Bearer " + DUMMY)
        self.assertEqual(req.data, b'{"text": "loop-fire v1 role=lead issue=16 event=issue_comment"}')

    def test_no_secret_or_url_in_output(self):
        for op in (Opener(), Opener(status=500), Opener(boom=OSError(URL + DUMMY))):
            code, out = run(["--roles", "lead,code", "--issue", "1", "--event", "issues"], ENV, op)
            self.assertNotIn(DUMMY, out)
            self.assertNotIn("trig_", out)
            self.assertNotIn("anthropic.com", out)

    def test_both_missing_warns_exit0(self):
        op = Opener()
        code, out = run(["--roles", "lead,code", "--issue", "1", "--event", "issues"], {}, op)
        self.assertEqual(code, 0)
        self.assertIn("::warning::", out)
        self.assertEqual(op.calls, [])

    def test_half_set_fails_but_tries_other_role(self):
        op = Opener()
        env = dict(ENV)
        del env["LOOP_LEAD_FIRE_TOKEN"]
        code, out = run(["--roles", "lead,code", "--issue", "1", "--event", "issues"], env, op)
        self.assertEqual(code, 1)
        self.assertEqual(len(op.calls), 1)

    def test_http_error_fails_and_continues(self):
        op = Opener(status=500)
        code, out = run(["--roles", "lead,code", "--issue", "1", "--event", "issues"], ENV, op)
        self.assertEqual(code, 1)
        self.assertEqual(len(op.calls), 2)

    def test_exception_with_code_fails(self):
        err = type("E", (Exception,), {"code": 401})()
        code, out = run(["--roles", "code", "--issue", "1", "--event", "issues"], ENV, Opener(boom=err))
        self.assertEqual(code, 1)
        self.assertIn("401", out)

    def test_wrong_host_refused_without_call(self):
        op = Opener()
        env = dict(ENV, LOOP_LEAD_FIRE_URL="https://evil.example/v1/claude_code/routines/trig_x/fire")
        code, out = run(["--roles", "lead", "--issue", "1", "--event", "issues"], env, op)
        self.assertEqual(code, 1)
        self.assertEqual(op.calls, [])
        self.assertNotIn("evil", out)

    def test_dry_run_no_call(self):
        op = Opener()
        code, out = run(["--roles", "lead", "--issue", "0", "--event", "workflow_dispatch", "--dry-run"], ENV, op)
        self.assertEqual(code, 0)
        self.assertEqual(op.calls, [])
        self.assertIn("would fire lead", out)

    def test_bad_args(self):
        self.assertEqual(run(["--roles", "root", "--event", "issues"], ENV, Opener())[0], 1)
        self.assertEqual(run(["--roles", "lead", "--event", "bogus"], ENV, Opener())[0], 1)

    def test_no_roles(self):
        self.assertEqual(run(["--roles", "", "--event", "issues"], ENV, Opener())[0], 0)


if __name__ == "__main__":
    unittest.main()
