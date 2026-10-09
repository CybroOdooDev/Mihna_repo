import unittest

from odoo.tests import tagged

from ..services.sandbox import DevLocalSandbox, SandboxError, get_sandbox
from .common import LindaCommon


@tagged("post_install", "-at_install", "linda")
class TestSandbox(LindaCommon):
    """Runs the shipped reference solutions for real (dev-local sandbox) on every toolchain present."""

    def test_dev_local_requires_opt_in(self):
        with self.assertRaises(SandboxError):
            get_sandbox({"kind": "dev_local"})

    def _check_question(self, xmlid):
        question = self.env.ref(xmlid)
        tests = [{"stdin": t.stdin or "", "stdout": t.stdout or "", "hidden": t.hidden} for t in question.test_case_ids]
        self.assertGreaterEqual(len(tests), 6)
        sandbox = DevLocalSandbox({"kind": "dev_local", "allow_dev_local": True})
        ran = 0
        for sol in question.solution_ids:
            if not DevLocalSandbox.available(sol.language):
                continue
            results = sandbox.run(sol.language, sol.code, tests)
            failed = [(i, r) for i, r in enumerate(results) if not r["passed"]]
            self.assertFalse(failed, f"{xmlid} / {sol.language}: {failed}")
            ran += 1
        if not ran:
            raise unittest.SkipTest("No local toolchain")

    def test_second_largest_solutions(self):
        self._check_question("linda_ai_interview.q_coding_second_largest")

    def test_kvl_solutions(self):
        self._check_question("linda_ai_interview.q_learn_kvl")

    def test_wrong_answer_and_timeout(self):
        sandbox = DevLocalSandbox({"kind": "dev_local", "allow_dev_local": True, "time_limits": {"python": 0.5}})
        tests = [{"stdin": "1\n", "stdout": "2"}]
        self.assertEqual(sandbox.run("python", "print(1)", tests)[0]["status"], "wrong_answer")
        self.assertEqual(sandbox.run("python", "while True: pass", tests)[0]["status"], "timeout")
        self.assertEqual(sandbox.run("python", "print(", tests)[0]["status"], "runtime_error")

    def test_question_validation_flow(self):
        """Pool rule: usable only if every language has a passing reference solution, then admin approval."""
        source = self.env.ref("linda_ai_interview.q_coding_second_largest")
        complete = source.copy({"state": "draft"})
        self.assertEqual(len(complete.solution_ids), 4)
        self.assertTrue(complete.action_validate())  # mock sandbox (tests run offline)
        self.assertEqual(complete.state, "validated")
        self.assertTrue(complete.reference_answer_ids, "reference AI answers generated on validation")
        complete.action_approve()
        self.assertEqual(complete.state, "approved")

        partial = source.copy({"state": "draft"})
        partial.solution_ids.filtered(lambda s: s.language != "python").unlink()
        partial.action_validate()
        self.assertEqual(partial.state, "failed")
        self.assertIn("Missing reference solutions", partial.validation_log)
        with self.assertRaises(Exception):
            partial.action_approve()

    def test_generate_wizard(self):
        wizard = self.env["ai.interview.question.generate"].create({"qtype": "coding", "count": 2, "validate_now": True})
        self.assertIn("Approved / target", wizard.pool_status)
        action = wizard.action_generate()
        generated = self.env["ai.interview.question"].browse(action["domain"][0][2])
        self.assertEqual(len(generated), 2)
        self.assertEqual(set(generated.mapped("source")), {"ai"})
        self.assertEqual(set(generated.mapped("state")), {"validated"}, "awaits admin approval")
        self.assertTrue(all(len(q.solution_ids) == 4 and q.canary for q in generated))
