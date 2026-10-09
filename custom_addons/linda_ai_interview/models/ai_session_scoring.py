"""Post-submission pipeline: accurate transcription, hidden tests, double LLM scoring,
integrity signals, weighted total and band (FRD §5, §9)."""
import logging
import re
from collections import Counter
from datetime import timedelta

from odoo import _, api, fields, models

from ..services import integrity, prompts, similarity
from ..services.llm import LLMError
from ..services.sandbox import SandboxError

from .ai_template import DIMENSION_SELECTION, LANGUAGE_SELECTION

_logger = logging.getLogger(__name__)

RETRY_DELAYS_MIN = [2, 10, 30, 60, 180]
REFERENCE_MATCH_CODE = 0.80
REFERENCE_MATCH_TEXT = 0.50
PEER_MATCH_CODE = 0.85
PEER_MATCH_TEXT = 0.60


class AiInterviewSessionScoring(models.Model):
    _inherit = "ai.interview.session"

    @api.model
    def _cron_process_scoring(self):
        now = fields.Datetime.now()
        sessions = self.sudo().search([("scoring_state", "=", "queued"), ("state", "in", ("submitted", "scored")),
                                       "|", ("scoring_next_at", "=", False), ("scoring_next_at", "<=", now)],
                                      limit=5, order="scoring_next_at, id")
        for index, session in enumerate(sessions):
            session._run_scoring()
            self.env["ir.cron"]._commit_progress(1, remaining=len(sessions) - index - 1)

    def _run_scoring(self):
        """Score with retry bookkeeping: failed AI calls are retried, then the session is queued again."""
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                self._score_session()
        except (LLMError, SandboxError, Exception) as exc:  # noqa: BLE001 - every failure is retried/logged
            retryable = getattr(exc, "retryable", True)
            attempts = self.scoring_attempts + 1
            _logger.warning("Scoring session %s failed (attempt %s): %s", self.id, attempts, exc)
            if retryable and attempts < len(RETRY_DELAYS_MIN):
                self.write({"scoring_attempts": attempts, "scoring_error": str(exc),
                            "scoring_next_at": fields.Datetime.now() + timedelta(minutes=RETRY_DELAYS_MIN[attempts - 1])})
            else:
                self.write({"scoring_attempts": attempts, "scoring_state": "failed", "scoring_error": str(exc)})
                self.message_post(body=_("Automatic scoring failed: %s. Use 'Re-score' after fixing the provider "
                                         "configuration.", exc))
                self._schedule_owner_activity(_("AI interview scoring failed"))
            return False
        return True

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    def _score_session(self):
        self.ensure_one()
        self._transcribe_final()
        self._run_hidden_tests()
        criteria = self.env["ai.interview.criterion"].sudo().search([])
        materials = self._scoring_materials()
        signals = {}
        Score = self.env["ai.interview.score"].sudo()
        # Every dimension is scored twice; all runs are independent, so they go out concurrently.
        calls, scored_dims = [], []
        for dim, _label in DIMENSION_SELECTION:
            material = materials.get(dim, "").strip()
            if not material:
                continue
            system, messages = prompts.score_dimension(
                dim, criteria.filtered(lambda c, d=dim: c.dimension == d)._rubric(), material)
            scored_dims.append(dim)
            calls += [(f"score_{dim}_run{run}", system, messages, prompts.SCORE_SCHEMA, 4000) for run in (1, 2)]
        results = self.env["ai.interview.engine"]._llm_batch("llm_scorer", calls, session=self)
        runs_by_dim = {dim: [results[2 * i].data, results[2 * i + 1].data] for i, dim in enumerate(scored_dims)}
        self.score_ids.sudo().unlink()
        for dim, _label in DIMENSION_SELECTION:
            if dim not in runs_by_dim:
                Score.create({"session_id": self.id, "dimension": dim, "ai_score": 1, "ai_score_run1": 1,
                              "ai_score_run2": 1, "evidence": [], "criteria": [],
                              "rationale": _("Insufficient evidence: the candidate gave no answers for this "
                                             "dimension.")})
                continue
            runs = runs_by_dim[dim]
            s1, s2 = runs[0]["score"], runs[1]["score"]
            final = int((s1 + s2) / 2 + 0.5)
            best = min(runs, key=lambda r: abs(r["score"] - final))
            Score.create({
                "session_id": self.id, "dimension": dim, "ai_score": final, "ai_score_run1": s1,
                "ai_score_run2": s2, "needs_review": abs(s1 - s2) > 1, "evidence": best["evidence"][:3],
                "criteria": best["criteria"], "rationale": best["rationale"],
            })
            signals[dim] = [r.get("signals") or {} for r in runs]
        self._compute_integrity(signals)
        self._compute_totals()
        self.write({"state": "scored", "scoring_state": "done", "scoring_error": False})
        band = dict(self._fields["band"].selection).get(self.band, "-")
        body = _("AI interview scored: %(total)s/100, band %(band)s, AI-assistance risk %(risk)s.",
                 total=round(self.total_score), band=band, risk=dict(self._fields["risk"].selection).get(self.risk))
        self.message_post(body=body)
        self.applicant_id.message_post(body=body)
        self._schedule_review_activity()

    def _transcribe_final(self):
        """Re-transcribe every recording with the accurate model; that transcript is used for scoring."""
        engine = self.env["ai.interview.engine"]
        for resp in self.response_ids.filtered("audio_attachment_ids"):
            followups = [dict(f) for f in (resp.followups or [])]
            for att in resp.audio_attachment_ids:
                try:
                    text = engine.with_context(linda_section=resp.section)._stt(
                        att.raw, "stt_accurate", att.name, att.mimetype, session=self)["text"]
                except Exception as exc:  # keep the fast transcript
                    _logger.warning("Accurate transcription failed for %s: %s", att.id, exc)
                    continue
                if att.name.startswith(f"answer_{resp.id}_main"):
                    resp.transcript_final = text
                else:
                    for f in followups:
                        if f.get("audio_id") == att.id:
                            f["a_final"] = text
            resp.followups = followups

    def _run_hidden_tests(self):
        engine = self.env["ai.interview.engine"]
        for resp in self.response_ids.filtered(lambda r: r.section in ("coding", "learn") and r.question_id):
            tests = [{"stdin": t.stdin or "", "stdout": t.stdout or "", "hidden": t.hidden}
                     for t in resp.question_id.test_case_ids]
            if not (resp.code or "").strip() or not resp.language or not tests:
                resp.write({"test_results": [], "tests_passed": 0, "tests_total": len(tests)})
                continue
            results = engine.with_context(linda_section=resp.section)._run_code(resp.language, resp.code, tests,
                                                                                session=self)
            resp.write({"test_results": [dict(r, stdin=t["stdin"], expected=t["stdout"]) for t, r in zip(tests, results)],
                        "tests_passed": sum(r["passed"] for r in results), "tests_total": len(results)})

    def _anonymise(self, text):
        """The scorer never sees name, e-mail, phone, gender, age, photo or location (FRD §8)."""
        applicant = self.applicant_id
        tokens = set()
        for value in (applicant.partner_name, applicant.partner_id.name):
            tokens.update(t for t in (value or "").split() if len(t) > 2)
        for value in (applicant.email_from, applicant.partner_phone, applicant.partner_id.city):
            if value:
                tokens.add(value)
        for token in sorted(tokens, key=len, reverse=True):
            text = re.sub(re.escape(token), "[candidate]", text, flags=re.I)
        text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[email]", text)
        text = re.sub(r"\+?\d[\d\s-]{8,}\d", "[phone]", text)
        return text

    def _scoring_materials(self):
        by = lambda section: self.response_ids.filtered(lambda r: r.section == section)
        langs = dict(LANGUAGE_SELECTION)
        coding = []
        for i, r in enumerate(by("coding").filtered(lambda r: (r.code or "").strip()), 1):
            statuses = Counter(t.get("status") for t in (r.test_results or []))
            fups = "\n".join(f"Q: {f.get('q')}\nA: {f.get('a_final') or f.get('a') or '(no answer)'}"
                             for f in r.followups or [])
            coding.append(f"[coding problem {i}]\nProblem: {r.prompt_text}\nLanguage: {langs.get(r.language, '')}\n"
                          f"Final code:\n{r.code}\nHidden test results: {r.tests_passed}/{r.tests_total} passed "
                          f"({dict(statuses)}). Pass rate is one input, not the score.\n"
                          f"[coding follow-ups]\n{fups or '(none)'}")
        learning = []
        for r in by("learn"):
            runs = "; ".join(f"run {k + 1}: {x.get('passed')}/{x.get('total')} ({x.get('status')})"
                             for k, x in enumerate(r.run_log or []))
            qs = "\n".join(f"Q: {d.get('q')}\nA: {d.get('a')}" for d in r.doc_questions or [])
            learning.append(f"[learn and apply]\nTask: {r.prompt_text}\nDoc questions asked:\n{qs or '(none)'}\n"
                            f"Code runs while working (shows recovery after errors): {runs or '(none)'}\n"
                            f"Final code ({langs.get(r.language, '-')}):\n{r.code or '(none)'}\n"
                            f"Final tests: {r.tests_passed}/{r.tests_total} passed")
        written = [f"[written task {i}]\nTask: {r.prompt_text}\nAnswer: {r.answer_text or '(no answer)'}"
                   for i, r in enumerate(by("written"), 1) if (r.answer_text or "").strip()]
        voice = [f"[voice question {i}]\n{r._qa_text()}" for i, r in enumerate(by("voice"), 1)
                 if (r._final_transcript() or "").strip()]
        materials = {
            "coding": "\n\n".join(coding),
            "learning": "\n\n".join(learning) if any((r.code or "").strip() for r in by("learn")) else "",
            "written_english": "\n\n".join(written),
            "oral_english": "\n\n".join(voice),
            "attitude": "\n\n".join(voice + [w for w in written]) if voice else "",
        }
        return {k: self._anonymise(v) for k, v in materials.items()}

    # ------------------------------------------------------------------
    # Integrity
    # ------------------------------------------------------------------

    def _compute_integrity(self, scorer_signals):
        self.ensure_one()
        self.flag_ids.filtered(lambda f: f.is_signal).sudo().unlink()
        responses = self.response_ids

        # 1. Canary text in answers (near-certain evidence).
        for r in responses:
            texts = [r.answer_text or "", r.code or ""] + [f.get("a", "") for f in r.followups or []]
            if r.canary and any(similarity.contains_canary(t, r.canary) for t in texts):
                self._flag("canary", _("Answer contains the hidden canary instruction: %s", r.canary), response=r)

        # 2. Explanation gap / AI-style writing from the scorer (both runs must agree).
        coding = scorer_signals.get("coding") or []
        if len(coding) == 2 and all(s.get("explanation_gap") for s in coding):
            self._flag("explanation_gap", coding[0].get("explanation_gap_note") or "")
        written = scorer_signals.get("written_english") or []
        if len(written) == 2 and all(s.get("ai_style") for s in written):
            self._flag("ai_style", written[0].get("ai_style_note") or "")

        # 3. Typing replay.
        for r in responses.filtered(lambda r: r.section in ("written", "coding", "learn") and r.keystroke_log):
            suspicious, details = integrity.analyse_keystrokes(r.keystroke_log, r.code or r.answer_text or "")
            if suspicious:
                self._flag("typing_replay", _("Typing pattern: %s", ", ".join(details.get("reasons", []))),
                           response=r, evidence=details)

        # 4. Match with reference AI answers.
        engine = self.env["ai.interview.engine"]
        for r in responses.filtered(lambda r: r.section in ("written", "coding", "learn")):
            answer = r.code if r.section != "written" else r.answer_text
            if not (answer or "").strip():
                continue
            refs = []
            if r.question_id:
                refs = [(a.model_name, a.answer) for a in r.question_id.reference_answer_ids
                        if not a.language or a.language == r.language]
            if not refs and r.section == "written":
                system, messages = prompts.reference_answer(r.prompt_text)
                try:
                    res = engine._llm_call("llm_generator", "reference_answer", system, messages,
                                           schema=prompts.REFERENCE_ANSWER_SCHEMA, session=self, max_tokens=1500)
                    refs = [(res.model, res.data["answer"])]
                except LLMError:
                    refs = []
            for model_name, ref in refs:
                sim = similarity.code_similarity(answer, ref) if r.section != "written" else \
                    similarity.text_similarity(answer, ref)
                if sim >= (REFERENCE_MATCH_CODE if r.section != "written" else REFERENCE_MATCH_TEXT):
                    self._flag("reference_ai_match", _("%(pct)s%% similar to a reference answer from %(model)s.",
                                                       pct=int(sim * 100), model=model_name),
                               response=r, evidence={"similarity": round(sim, 3), "model": model_name})
                    break

        # 5. Match with other candidates (shared / leaked answers).
        Response = self.env["ai.interview.response"].sudo()
        for r in responses.filtered(lambda r: r.section in ("written", "coding", "learn")):
            answer = r.code if r.section != "written" else r.answer_text
            if not (answer or "").strip() or len(answer) < 60:
                continue
            domain = [("session_id", "!=", self.id), ("section", "=", r.section),
                      ("session_id.state", "in", ("submitted", "scored", "reviewed"))]
            if r.question_id:
                domain.append(("question_id", "=", r.question_id.id))
            elif self.campaign_id:
                domain.append(("session_id.campaign_id", "=", self.campaign_id.id))
            else:
                continue
            for other in Response.search(domain, limit=200, order="id desc"):
                other_answer = other.code if r.section != "written" else other.answer_text
                if not other_answer:
                    continue
                sim = similarity.code_similarity(answer, other_answer) if r.section != "written" else \
                    similarity.text_similarity(answer, other_answer)
                if sim >= (PEER_MATCH_CODE if r.section != "written" else PEER_MATCH_TEXT):
                    self._flag("peer_match", _("%(pct)s%% similar to another candidate's answer (%(other)s).",
                                               pct=int(sim * 100), other=other.session_id.name),
                               response=r, evidence={"similarity": round(sim, 3), "other_session": other.session_id.id})
                    break

        # 6. Written vs spoken English gap.
        written_text = "\n".join(r.answer_text or "" for r in responses.filtered(lambda r: r.section == "written"))
        spoken_text = "\n".join(r._final_transcript() for r in responses.filtered(lambda r: r.section == "voice"))
        if len(written_text) > 200 and len(spoken_text) > 200:
            system, messages = prompts.written_spoken_gap(self._anonymise(written_text), self._anonymise(spoken_text))
            try:
                res = engine._llm_call("llm_scorer", "written_spoken_gap", system, messages,
                                       schema=prompts.GAP_SCHEMA, session=self, max_tokens=500)
                if res.data["written_level"] - res.data["spoken_level"] >= 2:
                    self._flag("written_spoken_gap", res.data["note"], evidence=res.data)
            except LLMError as exc:
                _logger.info("Gap check skipped: %s", exc)

        # 7. Focus and paste events.
        events = Counter(self.flag_ids.filtered(lambda f: f.type in ("blur", "tab_switch", "fullscreen_exit", "paste"))
                         .mapped("type"))
        hit, total = integrity.focus_signal(dict(events))
        if hit:
            self._flag("focus_paste", _("%(n)s focus/paste events: %(detail)s", n=total,
                                        detail=", ".join(f"{k} ×{v}" for k, v in events.items())),
                       evidence=dict(events))

        # 8. Voice answer pattern (note only).
        for r in responses.filtered(lambda r: r.section == "voice"):
            if integrity.voice_pattern(r.silence_ms, r._final_transcript()):
                self._flag("voice_pattern", _("Long silence (%ss) then a fluent, list-like answer.",
                                              round(r.silence_ms / 1000)), response=r)

        self.risk = integrity.risk_level(self.flag_ids.filtered("is_signal").mapped("type"))

    def _compute_totals(self):
        for rec in self:
            weights = rec.template_id._weights()
            scores = {s.dimension: s.final_score for s in rec.score_ids}
            weight_sum = sum(w for d, w in weights.items() if d in scores)
            if not weight_sum:
                continue
            avg = sum(weights[d] * scores[d] for d in scores if d in weights) / weight_sum
            total = round(avg * 20, 1)
            rec.write({"total_score": total, "band": rec.template_id._band_for(total),
                       "red_flag_count": len(rec.score_ids.filtered("is_red_flag")),
                       "needs_review": any(rec.score_ids.mapped("needs_review"))})

    # ------------------------------------------------------------------
    # Activities
    # ------------------------------------------------------------------

    def _reviewers(self):
        recruiter_user = self.applicant_id.recruiter_id.user_id if self.applicant_id.recruiter_id else False
        users = self.reviewer_id or self.campaign_id.reviewer_ids[:1] or self.job_id.interviewer_ids[:1] \
            or recruiter_user or self.campaign_id.user_id or self.env.user
        return users[:1]

    def _schedule_review_activity(self):
        user = self._reviewers()
        if not user:
            return
        if not self.reviewer_id:
            self.reviewer_id = user
        note = _("Band %(band)s, total %(total)s/100, AI-assistance risk %(risk)s.",
                 band=dict(self._fields["band"].selection).get(self.band), total=round(self.total_score),
                 risk=dict(self._fields["risk"].selection).get(self.risk))
        if self.risk in ("medium", "high"):
            note += " " + _("Integrity signals need a re-check; plan a short live coding question in the "
                            "technical round.")
        self.activity_schedule("mail.mail_activity_data_todo", user_id=user.id,
                               summary=_("Review AI interview scorecard"), note=note)

    def _schedule_owner_activity(self, summary):
        recruiter_user = self.applicant_id.recruiter_id.user_id if self.applicant_id.recruiter_id else False
        user = self.campaign_id.user_id or recruiter_user
        if user:
            self.activity_schedule("mail.mail_activity_data_todo", user_id=user.id, summary=summary)
