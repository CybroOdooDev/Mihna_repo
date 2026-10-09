"""Candidate-side interview runtime (called by the public controller with sudo).

The server is authoritative for time: each heartbeat/save adds the elapsed time
(capped, so a disconnect does not burn the clock) to the current section. A
section closes when its maximum time is used, and the interview submits itself
when the template's total cap is reached (FRD §3).
"""
import hashlib
import logging
import random
import secrets
from datetime import timedelta

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..services import prompts
from ..services.llm import LLMError
from ..services.sandbox import LANGUAGES, SandboxError

from .ai_template import SECTION_TYPES

_logger = logging.getLogger(__name__)

TICK_CAP_SECONDS = 20       # max time credited per heartbeat (disconnects don't consume time)
# Only the heartbeat, state and section routes write the session row (time keeping). Answer routes
# write only their response row, so a slow AI call never conflicts with the heartbeat; a conflict
# would make Odoo retry the whole request and repeat the (billed) AI call.
ACTIVE_WINDOW_SECONDS = 90  # a session is "active" for the concurrency queue if seen recently
MAX_TEXT = 20000
MAX_CODE = 50000


class AiInterviewSessionFlow(models.Model):
    _inherit = "ai.interview.session"

    # ------------------------------------------------------------------
    # State for the candidate app
    # ------------------------------------------------------------------

    def _portal_state(self, fresh_load=False):
        self.ensure_one()
        if self.state == "in_progress":
            if fresh_load:
                self._register_resume()
            if self.state == "in_progress":
                self._tick()
        template = self.template_id
        sections = template._sections()
        used = self.section_used or {}
        notice = self.env["ai.interview.consent.notice"].sudo()._current()
        data = {
            "state": self.state,
            "persona": prompts.PERSONA,
            "candidate": (self.applicant_id.partner_name or "").split(" ")[0],
            "job": self.job_id.name or "",
            "company": self.company_id.name or "",
            "consented": bool(self.consent_at),
            "notice": {"html": str(notice.body or ""), "version": notice.version} if notice else None,
            "total_minutes": template.total_minutes,
            "total_remaining": max(0, template.total_minutes * 60 - sum(used.values())),
            "sections": [{
                "type": s.section_type, "label": dict(SECTION_TYPES)[s.section_type],
                "max_seconds": s.max_minutes * 60, "min_seconds": s.min_minutes * 60,
                "done": s.section_type in (self.section_done or []),
            } for s in sections],
            "current_section": self.current_section or False,
            "remaining": self._section_remaining() if self.current_section else 0,
            "paused": self.paused,
            "resume_count": self.resume_count,
            "max_resumes": template.max_resumes,
            "languages": [{"code": c, "label": LANGUAGES[c]["label"]} for c in template._languages()],
            "language": self.language or False,
            "items": [],
            "waiting": False,
            "retention_days": self.env["ir.config_parameter"].sudo().get_int(
                "linda_ai_interview.retention_audio_days", 180),
        }
        if self.state == "in_progress" and self.current_section:
            responses = self.response_ids.filtered(lambda r: r.section == self.current_section)
            data["items"] = [r._portal_item() for r in responses]
            section = self._section_rec(self.current_section)
            data["followup_count"] = section.followup_count if section else 0
        if self.state == "invited" and self.consent_at:
            data["waiting"] = not self._slot_available()
        return data

    def _section_rec(self, section_type):
        return self.template_id._sections().filtered(lambda s: s.section_type == section_type)[:1]

    def _section_remaining(self):
        section = self._section_rec(self.current_section)
        if not section:
            return 0
        used = (self.section_used or {}).get(self.current_section, 0)
        total_left = self.template_id.total_minutes * 60 - sum((self.section_used or {}).values())
        return int(max(0, min(section.max_minutes * 60 - used, total_left)))

    # ------------------------------------------------------------------
    # Consent, queue, start
    # ------------------------------------------------------------------

    def _portal_consent(self, accept, ip=None):
        self.ensure_one()
        if self.state != "invited":
            raise UserError(_("This interview cannot be started."))
        if not accept:
            self.write({"consent_declined": True})
            self._flag("consent_declined", "The candidate declined consent.")
            self.applicant_id.message_post(body=_("The candidate declined consent for the AI interview."))
            responsible = (self.applicant_id.recruiter_id.user_id if self.applicant_id.recruiter_id else False) or self.campaign_id.user_id
            if responsible:
                self.activity_schedule("mail.mail_activity_data_todo", user_id=responsible.id,
                                       summary=_("Candidate declined AI interview consent"))
            return
        notice = self.env["ai.interview.consent.notice"].sudo()._current()
        self.write({"consent_at": fields.Datetime.now(), "consent_notice_id": notice.id, "consent_ip": ip,
                    "consent_declined": False})

    def _slot_available(self):
        """Concurrency queue: at launch only N (default 1) sessions run at a time (FRD §11)."""
        limit = self.env["ir.config_parameter"].sudo().get_int("linda_ai_interview.max_concurrent", 1)
        if limit <= 0:
            return True
        cutoff = fields.Datetime.now() - timedelta(seconds=ACTIVE_WINDOW_SECONDS)
        active = self.sudo().search_count([("state", "=", "in_progress"), ("last_seen_at", ">=", cutoff),
                                           ("id", "!=", self.id)])
        return active < limit

    def _portal_start(self):
        self.ensure_one()
        if self.state == "in_progress":
            return True
        if self.state != "invited" or not self.consent_at:
            raise UserError(_("Consent is required before the interview can start."))
        if not self._slot_available():
            return False
        now = fields.Datetime.now()
        first = self.template_id._sections()[:1]
        if not first:
            raise UserError(_("This interview template has no sections."))
        self.write({"state": "in_progress", "started_at": now, "last_tick_at": now, "last_seen_at": now,
                    "section_used": {}, "section_done": [], "current_section": first.section_type})
        self._prepare_section(first)
        self.applicant_id.message_post(body=_("The candidate started the AI interview."))
        return True

    def _register_resume(self):
        self.ensure_one()
        self.resume_count += 1
        self._flag("resume", _("Session resumed (%s of %s).", self.resume_count, self.template_id.max_resumes))
        # Time spent disconnected is not counted.
        self.last_tick_at = fields.Datetime.now()
        if self.resume_count > self.template_id.max_resumes:
            self._flag("resume_limit", _("Resume limit exceeded; interview submitted automatically."))
            self._submit(auto=True)

    # ------------------------------------------------------------------
    # Time keeping
    # ------------------------------------------------------------------

    def _tick(self, paused=None):
        """Credit elapsed time to the current section; close it when the time is up."""
        self.ensure_one()
        if self.state != "in_progress" or not self.current_section:
            return
        now = fields.Datetime.now()
        used = dict(self.section_used or {})
        if self.last_tick_at and not self.paused:
            delta = min((now - self.last_tick_at).total_seconds(), TICK_CAP_SECONDS)
            used[self.current_section] = used.get(self.current_section, 0) + max(0, int(delta))
        vals = {"section_used": used, "last_tick_at": now, "last_seen_at": now}
        if paused is not None:
            vals["paused"] = bool(paused)
        self.write(vals)
        if sum(used.values()) >= self.template_id.total_minutes * 60:
            self._flag("time_up", _("Total time cap reached."))
            self._submit(auto=True)
        elif self._section_remaining() <= 0:
            self._flag("time_up", _("Time up for section %s.", dict(SECTION_TYPES)[self.current_section]))
            self._finish_section()

    # ------------------------------------------------------------------
    # Section preparation (questions per candidate)
    # ------------------------------------------------------------------

    def _seed(self, salt=""):
        return int(hashlib.sha256(f"{self.id}:{self.create_date}:{salt}".encode()).hexdigest()[:8], 16)

    def _pool_pick(self, qtype, section, count, exclude=()):
        """Pick approved pool questions, preferring the target difficulty and least-used in the campaign."""
        Question = self.env["ai.interview.question"].sudo()
        mandatory = section.mandatory_question_ids.filtered(lambda q: q.qtype == qtype and q.state == "approved")
        picked = mandatory[:count]
        if len(picked) >= count:
            return picked
        domain = [("qtype", "=", qtype), ("state", "=", "approved"), ("id", "not in", picked.ids + list(exclude))]
        candidates = Question.search(domain + [("difficulty", "=", section.difficulty)]) or Question.search(domain)
        used_ids = set()
        if self.campaign_id:
            used_ids = set(self.env["ai.interview.response"].sudo().search(
                [("session_id.campaign_id", "=", self.campaign_id.id), ("question_id", "in", candidates.ids)]
            ).mapped("question_id").ids)
        rng = random.Random(self._seed(qtype))
        fresh = [q for q in candidates if q.id not in used_ids]
        rest = [q for q in candidates if q.id in used_ids]
        rng.shuffle(fresh)
        rng.shuffle(rest)
        for q in fresh + rest:
            if len(picked) >= count:
                break
            picked |= q
        return picked

    def _generated_prompts(self, section, count, kind_hint=""):
        """AI-generated, per-candidate variants steered by the admin guidance (FRD §4.6)."""
        examples = section.example_question_ids | self.env["ai.interview.question"].sudo().search(
            [("qtype", "=", section.section_type), ("state", "=", "approved")], limit=5)
        system, messages = prompts.generate_questions(
            section.section_type, (section.guidance or "") + kind_hint, section.difficulty, count,
            "\n".join(f"- {q.prompt}" for q in examples), self.template_id.tone, section.avoid)
        try:
            res = self.env["ai.interview.engine"]._llm_call("llm_interviewer", "generate_questions", system,
                                                            messages, schema=prompts.QUESTION_LIST_SCHEMA,
                                                            session=self, max_tokens=1500)
            return [q["prompt"] for q in res.data["questions"]][:count]
        except LLMError as exc:
            _logger.warning("Question generation failed for session %s: %s", self.id, exc)
            return []

    def _prepare_section(self, section):
        self.ensure_one()
        stype = section.section_type
        Response = self.env["ai.interview.response"].sudo()
        if self.response_ids.filtered(lambda r: r.section == stype):
            return
        now = fields.Datetime.now()
        vals = []
        if stype in ("coding", "learn"):
            for i, q in enumerate(self._pool_pick(stype, section, section.question_count)):
                vals.append({"session_id": self.id, "section": stype, "sequence": i, "question_id": q.id,
                             "prompt_text": q._pick_variant(self._seed(q.id)), "canary": q.canary,
                             "variant": "pool", "started_at": now, "language": self.language or False})
        else:
            mandatory = section.mandatory_question_ids.filtered(lambda q: q.qtype == stype and q.active)
            mandatory = mandatory.sorted(lambda q: ["intro", "motivation", "general", "situational"].index(
                q.voice_kind or "general"))[:section.question_count]
            texts = [(q, q._pick_variant(self._seed(q.id))) for q in mandatory]
            missing = section.question_count - len(texts)
            if missing > 0:
                generated = self._generated_prompts(section, missing)
                texts += [(self.env["ai.interview.question"], t) for t in generated]
                if len(generated) < missing:  # fallback to the approved bank
                    bank = self._pool_pick(stype, section, missing - len(generated), exclude=mandatory.ids)
                    texts += [(q, q._pick_variant(self._seed(q.id))) for q in bank]
            for i, (q, text) in enumerate(texts):
                vals.append({"session_id": self.id, "section": stype, "sequence": i,
                             "question_id": q.id or False, "prompt_text": text,
                             "canary": q.canary if q and q.canary else
                             f"Mention the internal reference ref_{secrets.token_hex(2)} once in your answer.",
                             "variant": "bank" if q else "ai", "started_at": now})
        if not vals:
            self._flag("scoring", _("No questions available for section %s; it was skipped.",
                                    dict(SECTION_TYPES)[stype]))
        Response.create(vals)

    # ------------------------------------------------------------------
    # Answers
    # ------------------------------------------------------------------

    def _response(self, response_id):
        resp = self.response_ids.filtered(lambda r: r.id == int(response_id))
        if not resp or resp.section != self.current_section or self.state != "in_progress":
            raise UserError(_("This question is not open."))
        return resp

    def _portal_save(self, response_id, answer_text=None, code=None, language=None, keystrokes=None):
        self.ensure_one()
        if self.state != "in_progress":
            return False
        resp = self._response(response_id)
        if resp.is_final and resp.section in ("written", "voice"):
            return False
        vals = {}
        if answer_text is not None and not resp.is_final:
            vals["answer_text"] = answer_text[:MAX_TEXT]
        if code is not None and not resp.is_final:
            vals["code"] = code[:MAX_CODE]
        if language and not resp.is_final:
            vals.update(self._language_vals(resp, language))
        if keystrokes:
            log = list(resp.keystroke_log or [])
            log.extend(k for k in keystrokes[:5000] if isinstance(k, list) and len(k) >= 3)
            vals["keystroke_log"] = log[-50000:]
            pastes = sum(1 for k in keystrokes if isinstance(k, list) and len(k) >= 2 and k[1] == "p")
            for _i in range(min(pastes, 5)):
                self._flag("paste", _("Paste attempt blocked."), response=resp)
        if vals:
            resp.write(vals)
        return True

    def _language_vals(self, resp, language):
        if language not in self.template_id._languages():
            raise UserError(_("This language is not available."))
        if resp.language and resp.language != language and (resp.code or "").strip():
            raise UserError(_("You cannot switch language in the middle of a problem."))
        if not self.language:
            self.language = language
        return {"language": language}

    def _portal_event(self, etype, detail=""):
        self.ensure_one()
        if etype not in ("blur", "tab_switch", "fullscreen_exit", "paste"):
            return False
        self._flag(etype, (detail or "")[:500])
        if etype == "fullscreen_exit":
            self._tick(paused=True)
        return True

    def _portal_submit_answer(self, response_id, answer_text):
        """Written section: lock an answer."""
        self.ensure_one()
        self._portal_save(response_id, answer_text=answer_text)
        resp = self._response(response_id)
        resp.write({"is_final": True, "submitted_at": fields.Datetime.now()})
        return resp._portal_item()

    def _portal_run_code(self, response_id, code, language):
        """Run only the visible examples while working; hidden tests run at scoring."""
        self.ensure_one()
        self._portal_save(response_id, code=code, language=language)
        resp = self._response(response_id)
        tests = [{"stdin": t.stdin or "", "stdout": t.stdout or "", "hidden": False}
                 for t in resp.question_id.test_case_ids.filtered(lambda t: not t.hidden)]
        if not tests:
            return {"results": [], "message": _("No example tests for this problem.")}
        try:
            results = self.env["ai.interview.engine"]._run_code(resp.language or language, code, tests, session=self)
        except SandboxError as exc:
            return {"results": [], "message": _("The code runner is busy, please try again. (%s)", exc)}
        passed = sum(r["passed"] for r in results)
        resp.run_log = list(resp.run_log or []) + [{
            "t": fields.Datetime.to_string(fields.Datetime.now()), "passed": passed, "total": len(results),
            "status": ",".join(sorted({r["status"] for r in results}))}]
        return {"results": [{"stdin": t["stdin"], "expected": t["stdout"], "stdout": r["stdout"],
                             "stderr": r["stderr"], "status": r["status"], "passed": r["passed"]}
                            for t, r in zip(tests, results)]}

    def _portal_submit_code(self, response_id, code, language):
        """Lock the code; coding problems then get 2-3 AI follow-ups on the candidate's own code."""
        self.ensure_one()
        self._portal_save(response_id, code=code, language=language)
        resp = self._response(response_id)
        if not resp.language:
            raise UserError(_("Choose a programming language first."))
        vals = {"is_final": True, "submitted_at": fields.Datetime.now()}
        if resp.section == "coding":
            section = self._section_rec("coding")
            count = max(2, min(3, section.followup_count or 2))
            system, messages = prompts.code_followups(resp.prompt_text, code, resp.language, count,
                                                      self.template_id.tone)
            try:
                res = self.env["ai.interview.engine"]._llm_call(
                    "llm_interviewer", "code_followups", system, messages, schema=prompts.QUESTION_LIST_SCHEMA,
                    session=self, max_tokens=800)
                questions = [q["prompt"] for q in res.data["questions"]][:count]
            except LLMError:
                questions = [_("Walk me through how your code works, step by step."),
                             _("What happens with an empty or minimal input?")]
            vals["followups"] = [{"q": q, "a": "", "t": None} for q in questions]
        resp.write(vals)
        return resp._portal_item()

    def _portal_followup_answer(self, response_id, index, text):
        self.ensure_one()
        resp = self._response(response_id)
        followups = list(resp.followups or [])
        index = int(index)
        if not 0 <= index < len(followups) or followups[index].get("a"):
            raise UserError(_("This follow-up is not open."))
        followups[index] = dict(followups[index], a=(text or "")[:MAX_TEXT],
                                t=fields.Datetime.to_string(fields.Datetime.now()))
        resp.followups = followups
        return resp._portal_item()

    def _portal_ask_doc(self, response_id, question):
        """Learn-and-apply: candidate queries the doc through the AI; questions are logged."""
        self.ensure_one()
        resp = self._response(response_id)
        if len(resp.doc_questions or []) >= 15:
            return {"answer": _("You have reached the question limit for this task.")}
        system, messages = prompts.ask_doc(resp.question_id.reference_doc or "", (question or "")[:1000])
        try:
            res = self.env["ai.interview.engine"]._llm_call("llm_interviewer", "ask_doc", system, messages,
                                                            schema=prompts.ANSWER_SCHEMA, session=self,
                                                            max_tokens=500)
            answer, oos = res.data["answer"], res.data["out_of_scope"]
        except LLMError:
            answer, oos = _("Sorry, I can't answer right now. Please re-read the document."), True
        resp.doc_questions = list(resp.doc_questions or []) + [{
            "q": question[:1000], "a": answer, "out_of_scope": oos,
            "t": fields.Datetime.to_string(fields.Datetime.now())}]
        return {"answer": answer}

    # ------------------------------------------------------------------
    # Voice (turn-based)
    # ------------------------------------------------------------------

    def _store_audio(self, resp, audio, mimetype, label):
        ext = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/wav": "wav", "audio/mp4": "m4a"}.get(
            (mimetype or "").split(";")[0], "webm")
        att = self.env["ir.attachment"].sudo().create({
            "name": f"{label}.{ext}", "raw": audio, "mimetype": (mimetype or "audio/webm").split(";")[0],
            "res_model": "ai.interview.response", "res_id": resp.id,
        })
        resp.audio_attachment_ids = [(4, att.id)]
        return att

    def _portal_audio_answer(self, response_id, audio, mimetype, followup_index=-1, silence_ms=0):
        """Store the recorded answer, transcribe it (fast model) and decide the next interviewer turn."""
        self.ensure_one()
        resp = self._response(response_id)
        if len(audio or b"") > 15 * 1024 * 1024:
            raise UserError(_("The recording is too long."))
        followup_index = int(followup_index)
        label = f"answer_{resp.id}_{'main' if followup_index < 0 else followup_index}"
        att = self._store_audio(resp, audio, mimetype, label)
        try:
            text = self.env["ai.interview.engine"]._stt(audio, "stt_fast", att.name, att.mimetype,
                                                        session=self)["text"]
        except Exception as exc:
            _logger.warning("Fast transcription failed: %s", exc)
            text = ""
        now = fields.Datetime.to_string(fields.Datetime.now())
        if followup_index < 0:
            if resp.is_final:
                raise UserError(_("This question was already answered."))
            resp.write({"transcript": text, "silence_ms": int(silence_ms or 0), "answer_text": text})
        else:
            followups = list(resp.followups or [])
            if not 0 <= followup_index < len(followups) or followups[followup_index].get("a"):
                raise UserError(_("This follow-up is not open."))
            followups[followup_index] = dict(followups[followup_index], a=text or "(no speech detected)", t=now,
                                             audio_id=att.id, silence_ms=int(silence_ms or 0))
            resp.followups = followups
        if resp.section == "voice":
            self._voice_next_turn(resp)
        return resp._portal_item()

    def _portal_voice_text_answer(self, response_id, text, followup_index=-1):
        """Fallback when the microphone fails: typed answer, flagged for the reviewer."""
        self.ensure_one()
        resp = self._response(response_id)
        followup_index = int(followup_index)
        if followup_index < 0:
            resp.write({"transcript": (text or "")[:MAX_TEXT], "answer_text": (text or "")[:MAX_TEXT]})
            self._flag("scoring", _("Voice answer typed instead of spoken."), response=resp)
            if resp.section == "voice":
                self._voice_next_turn(resp)
            return resp._portal_item()
        return self._portal_followup_answer(response_id, followup_index, text)

    def _voice_next_turn(self, resp):
        section = self._section_rec("voice")
        followups = list(resp.followups or [])
        left = max(0, (section.followup_count if section else 1) - len(followups))
        if left == 0 or self._section_remaining() < 45:
            resp.write({"is_final": True, "submitted_at": fields.Datetime.now()})
            return
        transcript = resp._qa_text() if followups else f"Q: {resp.prompt_text}\nA: {resp.transcript or ''}"
        last_answer = followups[-1].get("a") if followups else (resp.transcript or "")
        system, messages = prompts.interviewer_turn(
            "voice", section.guidance, self.template_id.tone, transcript, f"Main question: {resp.prompt_text}",
            self._section_remaining(), left, last_answer)
        try:
            res = self.env["ai.interview.engine"]._llm_call("llm_interviewer", "interviewer_turn", system,
                                                            messages, schema=prompts.TURN_SCHEMA, session=self,
                                                            max_tokens=300)
            say, done = res.data["say"], res.data["done"]
        except LLMError:
            say, done = "", True
        if done or not say.strip():
            resp.write({"is_final": True, "submitted_at": fields.Datetime.now()})
        else:
            resp.followups = followups + [{"q": say, "a": "", "t": None}]

    def _portal_tts(self, response_id, index=-1):
        self.ensure_one()
        resp = self.response_ids.filtered(lambda r: r.id == int(response_id))
        if not resp:
            raise UserError(_("Unknown question."))
        index = int(index)
        text = resp.prompt_text if index < 0 else (resp.followups or [])[index]["q"]
        return self.env["ai.interview.engine"]._tts(text, session=self)

    # ------------------------------------------------------------------
    # Section / interview submission
    # ------------------------------------------------------------------

    def _portal_submit_section(self):
        self.ensure_one()
        self._tick()
        if self.state != "in_progress":
            return False
        self._finish_section()
        return True

    def _finish_section(self):
        """Close the current section (answers are locked as they are) and open the next one."""
        self.ensure_one()
        current = self.current_section
        now = fields.Datetime.now()
        for resp in self.response_ids.filtered(lambda r: r.section == current and not r.is_final):
            resp.write({"is_final": True, "submitted_at": now})
        for resp in self.response_ids.filtered(lambda r: r.section == current):
            resp.time_spent = (self.section_used or {}).get(current, 0)
        done = list(self.section_done or []) + [current]
        remaining = [s for s in self.template_id._sections() if s.section_type not in done]
        self.write({"section_done": done, "current_section": remaining[0].section_type if remaining else False,
                    "paused": False, "last_tick_at": now})
        if remaining:
            self._prepare_section(remaining[0])
        else:
            self._submit()

    def _submit(self, auto=False):
        self.ensure_one()
        if self.state != "in_progress":
            return
        now = fields.Datetime.now()
        self.response_ids.filtered(lambda r: not r.is_final).write({"is_final": True, "submitted_at": now})
        self.write({"state": "submitted", "finished_at": now, "current_section": False,
                    "scoring_state": "queued", "scoring_next_at": now, "scoring_attempts": 0})
        self.applicant_id.message_post(body=_("The candidate submitted the AI interview%s. Scoring has started.",
                                              _(" (automatically)") if auto else ""))
        self.message_post(body=_("Interview submitted%s.", _(" automatically") if auto else ""))
        cron = self.env.ref("linda_ai_interview.ir_cron_process_scoring", raise_if_not_found=False)
        if cron:
            cron._trigger()

    def _portal_withdraw(self):
        self.ensure_one()
        self.action_withdraw_consent()
        return True


class AiInterviewResponsePortal(models.Model):
    _inherit = "ai.interview.response"

    def _portal_item(self):
        """What the candidate app may see: never hidden tests, scores or rubric."""
        self.ensure_one()
        q = self.question_id
        item = {
            "id": self.id, "section": self.section, "prompt": self.prompt_text or "", "canary": self.canary or "",
            "answer_text": self.answer_text or "", "code": self.code or "", "language": self.language or False,
            "final": self.is_final,
            "followups": [{"q": f.get("q", ""), "a": f.get("a", ""), "index": i}
                          for i, f in enumerate(self.followups or [])],
            "title": q.name if q and self.section in ("coding", "learn") else "",
        }
        if self.section in ("coding", "learn") and q:
            item.update(input_spec=q.input_spec or "", output_spec=q.output_spec or "",
                        doc=(q.reference_doc or "") if self.section == "learn" else "",
                        examples=[{"stdin": t.stdin, "stdout": t.stdout}
                                  for t in q.test_case_ids.filtered(lambda t: not t.hidden)],
                        doc_questions=[{"q": d["q"], "a": d["a"]} for d in (self.doc_questions or [])])
        if self.section == "voice":
            item["transcript"] = self.transcript or ""
            item["answered"] = bool(self.transcript or self.answer_text)
        return item
