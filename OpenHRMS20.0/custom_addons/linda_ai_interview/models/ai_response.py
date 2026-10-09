from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..services.integrity import SIGNAL_WEIGHTS
from .ai_template import DIMENSION_SELECTION, LANGUAGE_SELECTION, SECTION_TYPES


class AiInterviewResponse(models.Model):
    _name = "ai.interview.response"
    _description = "Linda – candidate answer"
    _order = "session_id, sequence, id"

    session_id = fields.Many2one("ai.interview.session", required=True, ondelete="cascade", index=True)
    section = fields.Selection(SECTION_TYPES, required=True)
    sequence = fields.Integer(default=10)
    question_id = fields.Many2one("ai.interview.question", ondelete="set null")
    variant = fields.Char(help="Which variant / generated phrasing was shown.")
    prompt_text = fields.Text("Question shown")
    canary = fields.Char()
    answer_text = fields.Text()
    code = fields.Text()
    language = fields.Selection(LANGUAGE_SELECTION)
    keystroke_log = fields.Json(help="[[t_ms, kind, n], ...] with kind i=insert, d=delete, p=paste attempt.")
    audio_attachment_ids = fields.Many2many("ir.attachment", string="Audio")
    transcript = fields.Text("Transcript (fast)")
    transcript_final = fields.Text("Transcript (accurate)")
    silence_ms = fields.Integer("Silence before answer (ms)")
    followups = fields.Json(default=list, help="[{q, a, a_final, t, audio_id, silence_ms}]")
    doc_questions = fields.Json(default=list, help="Learn-and-apply questions asked about the doc.")
    run_log = fields.Json(default=list, help="Code runs during the section: [{t, passed, total, status}].")
    test_results = fields.Json(help="Hidden test results computed at scoring time.")
    tests_passed = fields.Integer()
    tests_total = fields.Integer()
    started_at = fields.Datetime()
    submitted_at = fields.Datetime()
    time_spent = fields.Integer("Seconds spent")
    is_final = fields.Boolean("Submitted")

    def _final_transcript(self):
        self.ensure_one()
        return self.transcript_final or self.transcript or ""

    def _qa_text(self):
        """Main answer + follow-ups as readable text for scoring and the scorecard."""
        self.ensure_one()
        lines = []
        if self.section == "voice":
            lines.append(f"Q: {self.prompt_text}\nA: {self._final_transcript()}")
        for f in self.followups or []:
            lines.append(f"Q: {f.get('q', '')}\nA: {f.get('a_final') or f.get('a', '')}")
        return "\n".join(lines)


class AiInterviewScore(models.Model):
    _name = "ai.interview.score"
    _description = "Linda – dimension score"
    _order = "session_id, sequence"

    session_id = fields.Many2one("ai.interview.session", required=True, ondelete="cascade", index=True)
    dimension = fields.Selection(DIMENSION_SELECTION, required=True)
    sequence = fields.Integer(compute="_compute_sequence", store=True)
    ai_score = fields.Integer("AI score")
    ai_score_run1 = fields.Integer("AI run 1")
    ai_score_run2 = fields.Integer("AI run 2")
    human_score = fields.Integer("Reviewer score", help="0 = no override.")
    override_reason = fields.Text()
    overridden_by = fields.Many2one("res.users", readonly=True)
    overridden_at = fields.Datetime(readonly=True)
    final_score = fields.Integer(compute="_compute_final_score", store=True)
    evidence = fields.Json(help="[{quote, section}]")
    criteria = fields.Json(help="[{name, score, evidence, rationale}]")
    rationale = fields.Text()
    needs_review = fields.Boolean("Needs human review", help="The two AI runs differed by more than 1 point.")
    is_red_flag = fields.Boolean(compute="_compute_final_score", store=True)
    weight = fields.Integer(compute="_compute_weight")

    _dimension_uniq = models.Constraint("UNIQUE(session_id, dimension)", "One score per dimension.")

    @api.depends("dimension")
    def _compute_sequence(self):
        order = [d for d, _l in DIMENSION_SELECTION]
        for rec in self:
            rec.sequence = order.index(rec.dimension) if rec.dimension in order else 99

    @api.depends("ai_score", "human_score")
    def _compute_final_score(self):
        for rec in self:
            rec.final_score = rec.human_score or rec.ai_score
            rec.is_red_flag = 0 < rec.final_score <= 2

    def _compute_weight(self):
        for rec in self:
            rec.weight = rec.session_id.template_id._weights().get(rec.dimension, 0) if rec.session_id.template_id else 0

    @api.constrains("human_score", "override_reason")
    def _check_override(self):
        for rec in self:
            if rec.human_score and not (1 <= rec.human_score <= 5):
                raise ValidationError(self.env._("Scores are between 1 and 5."))
            if rec.human_score and not (rec.override_reason or "").strip():
                raise ValidationError(self.env._("An override needs a reason."))

    def write(self, vals):
        if "human_score" in vals:
            vals.update(overridden_by=self.env.uid if vals["human_score"] else False,
                        overridden_at=fields.Datetime.now() if vals["human_score"] else False)
        res = super().write(vals)
        if "human_score" in vals:
            for session in self.mapped("session_id"):
                session._compute_totals()
                for rec in self.filtered(lambda s: s.session_id == session):
                    session.message_post(body=self.env._(
                        "%(dim)s score overridden: AI %(ai)s → reviewer %(human)s. Reason: %(reason)s",
                        dim=dict(DIMENSION_SELECTION)[rec.dimension], ai=rec.ai_score,
                        human=rec.human_score or "-", reason=rec.override_reason or ""))
        return res


FLAG_TYPES = [
    # integrity signals (FRD §9)
    ("canary", "Canary text in answer"),
    ("explanation_gap", "Explanation gap"),
    ("typing_replay", "Typing replay pattern"),
    ("reference_ai_match", "Match with reference AI answer"),
    ("peer_match", "Match with another candidate"),
    ("written_spoken_gap", "Written vs spoken gap"),
    ("focus_paste", "Focus / paste events"),
    ("ai_style", "AI-style writing (note)"),
    ("voice_pattern", "Voice answer pattern (note)"),
    # raw events
    ("paste", "Paste attempt"),
    ("blur", "Window lost focus"),
    ("tab_switch", "Tab switch"),
    ("fullscreen_exit", "Left full-screen"),
    ("resume", "Session resumed"),
    ("resume_limit", "Resume limit reached"),
    ("abandoned", "Session abandoned"),
    ("time_up", "Time limit reached"),
    ("consent_declined", "Consent declined"),
    ("scoring", "Scoring note"),
]


class AiInterviewFlag(models.Model):
    _name = "ai.interview.flag"
    _description = "Linda – integrity event / flag"
    _order = "timestamp, id"

    session_id = fields.Many2one("ai.interview.session", required=True, ondelete="cascade", index=True)
    response_id = fields.Many2one("ai.interview.response", ondelete="set null")
    type = fields.Selection(FLAG_TYPES, required=True)
    timestamp = fields.Datetime(default=fields.Datetime.now, required=True)
    detail = fields.Text()
    evidence = fields.Json()
    is_signal = fields.Boolean(compute="_compute_signal", store=True)
    weight = fields.Selection([("high", "High"), ("medium", "Medium"), ("low", "Low (note only)"),
                               ("event", "Event")], compute="_compute_signal", store=True)

    @api.depends("type")
    def _compute_signal(self):
        for rec in self:
            rec.is_signal = rec.type in SIGNAL_WEIGHTS
            rec.weight = SIGNAL_WEIGHTS.get(rec.type, "event")
