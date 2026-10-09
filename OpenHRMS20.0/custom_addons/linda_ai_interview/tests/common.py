from odoo.tests import TransactionCase

from ..services import speech


class LindaCommon(TransactionCase):
    """Shared fixtures: offline (mock) providers, a job linked to the default template, an applicant."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Provider = cls.env["ai.interview.provider"].with_context(active_test=False)
        Provider.search([("kind", "!=", "mock")]).write({"active": False})
        Provider.search([("kind", "=", "mock")]).write({"active": True})
        cls.template = cls.env.ref("linda_ai_interview.template_fresher_odoo")
        cls.job = cls.env["hr.job"].create({"name": "Odoo Developer (Fresher)"})
        cls.template.job_ids = [(6, 0, cls.job.ids)]
        cls.applicant = cls._make_applicant("Anu Krishnan", "anu.krishnan@example.com")
        cls.wav = speech.synthesize({"kind": "mock"}, "test answer")[0]

    @classmethod
    def _make_applicant(cls, name, email):
        partner = cls.env["res.partner"].create({"name": name, "email": email})
        return cls.env["hr.applicant"].create({
            "partner_name": name, "partner_id": partner.id, "email_from": email, "job_id": cls.job.id,
        })

    def _invite(self, applicant=None):
        applicant = applicant or self.applicant
        applicant.action_send_ai_interview()
        session = applicant.ai_session_ids[:1]
        self.assertEqual(session.state, "invited")
        return session

    def _complete_interview(self, session, code=None, canary_in_code=False):
        """Walk every section like a candidate would, using the portal methods."""
        session._portal_consent(True, "127.0.0.1")
        self.assertTrue(session._portal_start())
        # Written
        self.assertEqual(session.current_section, "written")
        for resp in session.response_ids.filtered(lambda r: r.section == "written"):
            text = ("Dear client, I am sorry to inform you that the delivery will be two days late because we "
                    "found a testing issue. We will deliver on Friday. Regards.")
            session._portal_save(resp.id, answer_text=text, keystrokes=[[1, "i", len(text), 0, text]])
            session._portal_submit_answer(resp.id, text)
        session._portal_submit_section()
        # Coding
        self.assertEqual(session.current_section, "coding")
        resp = session.response_ids.filtered(lambda r: r.section == "coding")[:1]
        code = code or ("import sys\nd = sys.stdin.read().split()\nn = int(d[0]) if d else 0\n"
                        "v = sorted(set(int(x) for x in d[1:1 + n]))\nprint(v[-2] if len(v) > 1 else 'NONE')\n")
        if canary_in_code:
            code = "def solve_qz():\n    pass\n" + code
        session._portal_run_code(resp.id, code, "python")
        item = session._portal_submit_code(resp.id, code, "python")
        for f in item["followups"]:
            session._portal_followup_answer(resp.id, f["index"], "Line 2 reads all the numbers from input.")
        session._portal_submit_section()
        # Learn and apply
        self.assertEqual(session.current_section, "learn")
        resp = session.response_ids.filtered(lambda r: r.section == "learn")[:1]
        session._portal_ask_doc(resp.id, "Are keys case-sensitive?")
        session._portal_submit_code(resp.id, "print('MISSING')\n", "python")
        session._portal_submit_section()
        # Voice
        self.assertEqual(session.current_section, "voice")
        for _i in range(20):
            open_items = session.response_ids.filtered(lambda r: r.section == "voice" and not r.is_final)
            if not open_items:
                break
            resp = open_items[0]
            pending = [i for i, f in enumerate(resp.followups or []) if not f.get("a")]
            session._portal_audio_answer(resp.id, self.wav, "audio/wav", pending[0] if pending else -1, 1200)
        session._portal_submit_section()
        self.assertEqual(session.state, "submitted")
        return session
