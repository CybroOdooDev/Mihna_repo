from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from ..services import mock_responses
from .common import LindaCommon


@tagged("post_install", "-at_install", "linda")
class TestInterviewFlow(LindaCommon):

    def test_invite(self):
        session = self._invite()
        self.assertTrue(session.access_token)
        self.assertTrue(session._check_token(session.access_token))
        self.assertFalse(session._check_token(session.access_token[:-1] + "x"))
        self.assertEqual(session.candidate_email, "anu.krishnan@example.com")
        self.assertEqual(session.partner_id, self.applicant.partner_id)
        self.assertFalse(self.applicant.ai_can_invite, "no second active session")
        with self.assertRaises(UserError):
            self.applicant.action_send_ai_interview()
        mail = self.env["mail.mail"].search([("model", "=", "ai.interview.session"), ("res_id", "=", session.id)])
        self.assertTrue(mail and session.access_token in mail.body_html, "invite e-mail carries the link")

    def test_expired_token(self):
        session = self._invite()
        session.expires_at = fields.Datetime.now() - timedelta(minutes=1)
        self.assertFalse(session._check_token(session.access_token))
        session._cron_expire_invites()
        self.assertEqual(session.state, "expired")

    def test_consent_required_and_declined(self):
        session = self._invite()
        with self.assertRaises(UserError):
            session._portal_start()
        session._portal_consent(False)
        self.assertTrue(session.consent_declined)
        self.assertIn("consent_declined", session.flag_ids.mapped("type"))
        session._portal_consent(True, "10.0.0.1")
        self.assertTrue(session.consent_at)
        self.assertEqual(session.consent_version, 1)

    def test_full_interview_and_scoring(self):
        session = self._complete_interview(self._invite())
        self.assertEqual(session.scoring_state, "queued")
        # written(2) + coding(1) + learn(1) + voice(5)
        self.assertEqual(len(session.response_ids), 9)
        coding = session.response_ids.filtered(lambda r: r.section == "coding")
        self.assertTrue(2 <= len(coding.followups) <= 3)
        self.assertTrue(all(f["a"] for f in coding.followups))
        voice = session.response_ids.filtered(lambda r: r.section == "voice")
        self.assertTrue(all(voice.mapped("is_final")))
        self.assertEqual(voice[0].prompt_text, self.env.ref("linda_ai_interview.q_voice_intro").prompt,
                         "mandatory introduction comes first")
        self.assertTrue(all(len(r.followups) == 1 for r in voice), "one follow-up per voice question")
        self.assertTrue(voice.audio_attachment_ids)

        self.assertTrue(session._run_scoring())
        self.assertEqual(session.state, "scored")
        self.assertEqual(len(session.score_ids), 5)
        for score in session.score_ids:
            self.assertTrue(1 <= score.ai_score <= 5)
            self.assertTrue(score.evidence)
        expected = sum(session.template_id._weights()[s.dimension] * s.final_score for s in session.score_ids) / 100 * 20
        self.assertAlmostEqual(session.total_score, round(expected, 1))
        self.assertEqual(session.band, session.template_id._band_for(session.total_score))
        self.assertEqual(self.applicant.ai_state, "scored")
        self.assertEqual(self.applicant.ai_band, session.band)
        self.assertTrue(coding.tests_total >= 6)
        self.assertTrue(session.call_log_ids.filtered(lambda l: l.role == "llm_scorer"))
        self.assertTrue(voice[0].transcript_final, "accurate re-transcription used for scoring")
        self.assertTrue(session.activity_ids, "reviewer activity scheduled")

    def test_scorer_gets_anonymised_material(self):
        session = self._complete_interview(self._invite())
        resp = session.response_ids.filtered(lambda r: r.section == "written")[:1]
        resp.answer_text = "My name is Anu Krishnan, mail anu.krishnan@example.com or call +91 98765 43210."
        material = session._scoring_materials()["written_english"]
        self.assertNotIn("Krishnan", material)
        self.assertNotIn("example.com", material)
        self.assertNotIn("98765", material)

    def test_canary_and_risk(self):
        session = self._complete_interview(self._invite(), canary_in_code=True)
        session._run_scoring()
        self.assertIn("canary", session.flag_ids.mapped("type"))
        self.assertEqual(session.risk, "high")
        self.assertTrue(session.live_recheck_required)

    def test_double_scoring_disagreement(self):
        session = self._complete_interview(self._invite())
        original = mock_responses.respond
        calls = {"n": 0}

        def disagreeing(system, user, schema):
            text = original(system, user, schema)
            if "TASK: score_dimension" in system and "Coding and problem solving" in user:
                calls["n"] += 1
                score = 1 if calls["n"] == 1 else 4
                text = text.replace('"score": 3', f'"score": {score}').replace('"score": 4', f'"score": {score}')
            return text

        with patch.object(mock_responses, "respond", disagreeing):
            session._run_scoring()
        coding = session.score_ids.filtered(lambda s: s.dimension == "coding")
        # runs execute concurrently, so either run may come back first
        self.assertEqual(sorted((coding.ai_score_run1, coding.ai_score_run2)), [1, 4])
        self.assertTrue(coding.needs_review)
        self.assertTrue(session.needs_review)

    def test_override_requires_reason_and_review_gate(self):
        session = self._complete_interview(self._invite())
        session._run_scoring()
        score = session.score_ids[:1]
        with self.assertRaises(ValidationError):
            score.write({"human_score": 2})
        score.write({"human_score": 1, "override_reason": "Could not explain own code in the follow-ups."})
        self.assertEqual(score.final_score, 1)
        self.assertTrue(score.is_red_flag)
        self.assertGreaterEqual(session.red_flag_count, 1)
        self.assertTrue(score.ai_score, "AI score is kept")

        next_stage = self.env["hr.recruitment.stage"].search([], order="sequence desc", limit=1)
        with self.assertRaises(UserError):
            self.applicant.stage_id = next_stage
        with self.assertRaises(UserError):
            session.action_confirm_review()  # decision missing
        session.write({"decision": "advance", "review_notes": "<p>Checked integrity signals.</p>"})
        session.action_confirm_review()
        self.assertEqual(session.state, "reviewed")
        self.assertTrue(session.band_confirmed)
        self.applicant.stage_id = next_stage
        self.assertEqual(self.applicant.stage_id, next_stage)

    def test_section_time_limit(self):
        session = self._invite()
        session._portal_consent(True)
        session._portal_start()
        session.section_used = {"written": 10 * 60 + 5}
        session._tick()
        self.assertEqual(session.current_section, "coding")
        self.assertIn("written", session.section_done)
        self.assertIn("time_up", session.flag_ids.mapped("type"))

    def test_total_time_cap(self):
        session = self._invite()
        session._portal_consent(True)
        session._portal_start()
        session.section_used = {"written": 5 * 60, "coding": 66 * 60}
        session.current_section = "coding"
        session._tick()
        self.assertEqual(session.state, "submitted")

    def test_disconnect_does_not_burn_time(self):
        session = self._invite()
        session._portal_consent(True)
        session._portal_start()
        session.last_tick_at = fields.Datetime.now() - timedelta(minutes=5)
        session._tick()
        self.assertLessEqual(session.section_used["written"], 20)

    def test_fullscreen_exit_pauses_timer(self):
        session = self._invite()
        session._portal_consent(True)
        session._portal_start()
        session._portal_event("fullscreen_exit")
        self.assertTrue(session.paused)
        session.last_tick_at = fields.Datetime.now() - timedelta(seconds=15)
        session._tick()
        self.assertEqual(session.section_used.get("written", 0), 0)

    def test_answer_routes_do_not_write_session(self):
        """Slow AI-backed answer routes must not update the session row (avoids conflicts with the
        heartbeat, which would make Odoo replay the request and repeat the AI call)."""
        session = self._invite()
        session._portal_consent(True)
        session._portal_start()
        session._portal_submit_section()
        session._portal_submit_section()  # -> learn
        past = fields.Datetime.now() - timedelta(seconds=15)
        session.last_tick_at = past
        session.flush_recordset()
        resp = session.response_ids.filtered(lambda r: r.section == "learn")
        self.env.cr.execute("SELECT write_date FROM ai_interview_session WHERE id = %s", [session.id])
        before = self.env.cr.fetchone()[0]
        session._portal_save(resp.id, code="print(1)", language="python", keystrokes=[[1, "i", 8, 0, "print(1)"]])
        session._portal_ask_doc(resp.id, "Are keys case-sensitive?")
        self.env.flush_all()
        self.env.cr.execute("SELECT write_date, last_tick_at FROM ai_interview_session WHERE id = %s", [session.id])
        after, tick = self.env.cr.fetchone()
        self.assertEqual(after, before)
        self.assertEqual(tick, past)

    def test_scoring_runs_concurrently(self):
        session = self._complete_interview(self._invite())
        engine = type(self.env["ai.interview.engine"])
        with patch.object(engine, "_llm_batch", wraps=self.env["ai.interview.engine"]._llm_batch) as batch:
            session._run_scoring()
        scorer_calls = [c for c in batch.call_args_list if c.args[0] == "llm_scorer"]
        self.assertEqual(len(scorer_calls), 1, "all dimension runs go out in one concurrent batch")
        self.assertEqual(len(scorer_calls[0].args[1]), 10)
        self.assertEqual(len(session.call_log_ids.filtered(lambda l: l.role == "llm_scorer"
                                                          and l.task.startswith("score_"))), 10)

    def test_resume_limit(self):
        session = self._invite()
        session._portal_consent(True)
        session._portal_start()
        session._portal_state(fresh_load=True)
        session._portal_state(fresh_load=True)
        self.assertEqual(session.state, "in_progress")
        self.assertEqual(session.resume_count, 2)
        session._portal_state(fresh_load=True)
        self.assertEqual(session.state, "submitted")
        self.assertIn("resume_limit", session.flag_ids.mapped("type"))

    def test_concurrency_queue(self):
        first = self._invite()
        first._portal_consent(True)
        first._portal_start()
        other = self._invite(self._make_applicant("Rahul Das", "rahul@example.com"))
        other._portal_consent(True)
        self.assertFalse(other._portal_start(), "waits while a slot is busy")
        self.assertTrue(other._portal_state()["waiting"])
        first.last_seen_at = fields.Datetime.now() - timedelta(minutes=10)
        self.assertTrue(other._portal_start())

    def test_language_cannot_switch_mid_problem(self):
        session = self._invite()
        session._portal_consent(True)
        session._portal_start()
        session._portal_submit_section()
        resp = session.response_ids.filtered(lambda r: r.section == "coding")
        session._portal_save(resp.id, code="print(1)", language="python")
        with self.assertRaises(UserError):
            session._portal_save(resp.id, code="int main(){}", language="c")

    def test_portal_item_hides_hidden_tests(self):
        session = self._invite()
        session._portal_consent(True)
        session._portal_start()
        session._portal_submit_section()
        item = session._portal_state()["items"][0]
        hidden = session.response_ids.filtered(lambda r: r.section == "coding").question_id.test_case_ids.filtered("hidden")
        shown = {e["stdin"] for e in item["examples"]}
        self.assertFalse(shown & set(hidden.mapped("stdin")))
        state = session._portal_state()
        for key in ("total_score", "band", "risk", "score_ids", "criteria", "rubric"):
            self.assertNotIn(key, state)
            self.assertNotIn(key, item)

    def test_withdraw_deletes_data(self):
        session = self._complete_interview(self._invite())
        session._run_scoring()
        response_ids = session.response_ids.ids
        audio = session.response_ids.audio_attachment_ids
        self.assertTrue(audio)
        session.action_withdraw_consent()
        self.assertEqual(session.state, "cancelled")
        self.assertFalse(session.response_ids)
        self.assertFalse(session.score_ids)
        self.assertFalse(audio.exists())
        self.assertFalse(self.env["ir.attachment"].search([("res_model", "=", "ai.interview.response"),
                                                           ("res_id", "in", response_ids)]))

    def test_retention_purge(self):
        session = self._complete_interview(self._invite())
        session._run_scoring()
        session.write({"decision": "hold", "review_notes": "<p>ok</p>"})
        session.action_confirm_review()
        session.reviewed_at = fields.Datetime.now() - timedelta(days=200)
        self.env["ai.interview.session"]._cron_purge_retention()
        voice = session.response_ids.filtered(lambda r: r.section == "voice")
        self.assertFalse(voice.mapped("audio_attachment_ids"))
        self.assertFalse(any(voice.mapped("transcript_final")))
        self.assertFalse(any(session.response_ids.mapped("keystroke_log")))
        self.assertEqual(len(session.score_ids), 5, "scores and decision are kept")

    def test_scoring_failure_is_retried(self):
        session = self._complete_interview(self._invite())
        from ..services.llm import LLMError
        with patch.object(type(self.env["ai.interview.engine"]), "_llm_batch", side_effect=LLMError("down")):
            self.assertFalse(session._run_scoring())
        self.assertEqual(session.scoring_state, "queued")
        self.assertEqual(session.scoring_attempts, 1)
        self.assertGreater(session.scoring_next_at, fields.Datetime.now())
        self.assertTrue(session._run_scoring())
        self.assertEqual(session.state, "scored")

    def test_campaign_dashboard_and_peer_match(self):
        campaign = self.env["ai.interview.campaign"].create({
            "name": "Campus drive", "job_id": self.job.id, "template_id": self.template.id})
        campaign.action_start()
        other = self._make_applicant("Rahul Das", "rahul@example.com")
        campaign.applicant_ids = [(6, 0, (self.applicant | other).ids)]
        campaign.action_invite_applicants()
        s1, s2 = campaign.session_ids
        code = ("import sys\ndata = sys.stdin.read().split()\ncount = int(data[0]) if data else 0\n"
                "unique = sorted(set(int(x) for x in data[1:1 + count]))\n"
                "print(unique[-2] if len(unique) > 1 else 'NONE')\n")
        self._complete_interview(s1, code=code)
        s1._run_scoring()
        s1.last_seen_at = fields.Datetime.now() - timedelta(minutes=10)
        self._complete_interview(s2, code=code.replace("unique", "u"))
        s2._run_scoring()
        self.assertIn("peer_match", s2.flag_ids.mapped("type"))
        data = campaign.get_dashboard_data(campaign.id)
        self.assertEqual(data["kpis"]["invited"], 2)
        self.assertEqual(data["funnel"][3], ("scored", 2))
        self.assertEqual(len(data["candidates"]), 2)
        self.assertEqual(sum(data["bands"].values()), 2)
        cand = s2.get_dashboard_data()
        self.assertEqual(len(cand["scores"]), 5)
        self.assertTrue(cand["sections"])
        s2.save_review({"overrides": [{"id": cand["scores"][0]["id"], "human_score": 4, "reason": "Strong explanation"}],
                        "decision": "advance", "review_notes": "<p>ok</p>", "confirm": True})
        self.assertEqual(s2.state, "reviewed")

    def test_token_usage_per_section(self):
        session = self._complete_interview(self._invite())
        session._run_scoring()
        logs = session.call_log_ids
        self.assertFalse(logs.filtered(lambda l: not l.section or not l.phase), "every call is tagged")
        self.assertEqual(set(logs.filtered(lambda l: l.task == "code_followups").mapped("section")), {"coding"})
        self.assertEqual(set(logs.filtered(lambda l: l.task == "ask_doc").mapped("section")), {"learn"})
        self.assertEqual(set(logs.filtered(lambda l: l.role == "stt_accurate").mapped("phase")), {"scoring"})
        self.assertEqual(set(logs.filtered(lambda l: l.task.startswith("score_learning")).mapped("section")), {"learn"})
        self.assertEqual(set(logs.filtered(lambda l: l.task == "run_code" and l.phase == "scoring")
                             .mapped("section")), {"coding", "learn"})
        usage = {u["section"]: u for u in session.get_dashboard_data()["usage"]}
        self.assertTrue({"written", "coding", "learn", "voice"} <= set(usage))
        self.assertTrue(usage["coding"]["interview"] and usage["coding"]["scoring"])
        self.assertEqual(sum(u["total"] for u in usage.values()), session.tokens_total)
        for u in usage.values():
            self.assertEqual(u["interview"] + u["scoring"], u["total"])

    def test_history_across_applications(self):
        session = self._invite()
        second = self.env["hr.applicant"].create({
            "partner_name": "Anu Krishnan", "partner_id": self.applicant.partner_id.id,
            "email_from": "anu.krishnan@example.com", "job_id": self.job.id})
        self.assertEqual(second.ai_session_count, 1, "history follows the candidate across applications")
        self.assertIn(session, self.env["ai.interview.session"].search(second._ai_history_domain()))

    def test_pdf_report_renders(self):
        session = self._complete_interview(self._invite())
        session._run_scoring()
        html = self.env["ir.actions.report"]._render_qweb_html(
            "linda_ai_interview.report_scorecard", session.ids)[0].decode()
        self.assertIn("AI interview scorecard", html)
        self.assertIn("Coding and problem solving", html)
