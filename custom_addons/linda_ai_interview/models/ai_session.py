import hmac
import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..services import tokens

from .ai_template import DIMENSION_SELECTION, LANGUAGE_SELECTION, SECTION_TYPES

_logger = logging.getLogger(__name__)

SESSION_STATES = [
    ("draft", "Draft"), ("invited", "Invited"), ("in_progress", "In progress"), ("submitted", "Submitted"),
    ("scored", "Scored"), ("reviewed", "Reviewed"), ("expired", "Expired"), ("cancelled", "Cancelled"),
]
BANDS = [("strong", "Strong"), ("borderline", "Borderline"), ("not_recommended", "Not recommended")]
RISKS = [("low", "Low"), ("medium", "Medium"), ("high", "High")]
DECISIONS = [("advance", "Advance to technical round"), ("hold", "Hold"), ("reject", "Reject")]


class AiInterviewSession(models.Model):
    _name = "ai.interview.session"
    _description = "Linda – candidate interview session"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _rec_name = "name"

    name = fields.Char(compute="_compute_name", store=True)
    applicant_id = fields.Many2one("hr.applicant", required=True, ondelete="cascade", index=True)
    partner_id = fields.Many2one("res.partner", "Candidate", index=True,
                                 help="Candidate contact; links interview history across applications.")
    candidate_email = fields.Char(index=True, help="Normalised candidate e-mail used to group history.")
    candidate_name = fields.Char(related="applicant_id.partner_name")
    job_id = fields.Many2one(related="applicant_id.job_id", store=True)
    campaign_id = fields.Many2one("ai.interview.campaign", index=True, ondelete="set null")
    template_id = fields.Many2one("ai.interview.template", required=True, ondelete="restrict")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    state = fields.Selection(SESSION_STATES, default="draft", required=True, tracking=True, index=True)

    # Access
    access_token = fields.Char(copy=False, index=True, groups="hr_recruitment.group_hr_recruitment_user")
    expires_at = fields.Datetime("Invite expires", copy=False)
    invited_at = fields.Datetime(copy=False)
    portal_url = fields.Char(compute="_compute_portal_url", groups="hr_recruitment.group_hr_recruitment_user")

    # Consent
    consent_at = fields.Datetime(copy=False, readonly=True)
    consent_notice_id = fields.Many2one("ai.interview.consent.notice", readonly=True, copy=False)
    consent_version = fields.Integer(related="consent_notice_id.version", string="Notice version")
    consent_ip = fields.Char(readonly=True, copy=False)
    consent_declined = fields.Boolean(readonly=True, copy=False)

    # Runtime (server is authoritative for time)
    started_at = fields.Datetime(copy=False, readonly=True)
    finished_at = fields.Datetime(copy=False, readonly=True)
    current_section = fields.Selection(SECTION_TYPES, copy=False)
    section_used = fields.Json(default=dict, copy=False, help="Seconds used per section.")
    section_done = fields.Json(default=list, copy=False)
    last_tick_at = fields.Datetime(copy=False)
    last_seen_at = fields.Datetime(copy=False)
    paused = fields.Boolean(copy=False)
    resume_count = fields.Integer(copy=False, readonly=True)
    duration_minutes = fields.Float(compute="_compute_duration", store=True)
    language = fields.Selection(LANGUAGE_SELECTION, "Language chosen", copy=False)

    response_ids = fields.One2many("ai.interview.response", "session_id")
    score_ids = fields.One2many("ai.interview.score", "session_id")
    flag_ids = fields.One2many("ai.interview.flag", "session_id")
    call_log_ids = fields.One2many("ai.interview.call.log", "session_id")

    # Results
    scoring_state = fields.Selection([("none", "Not queued"), ("queued", "Queued"), ("done", "Done"),
                                      ("failed", "Failed")], default="none", copy=False, index=True)
    scoring_attempts = fields.Integer(copy=False)
    scoring_next_at = fields.Datetime(copy=False)
    scoring_error = fields.Text(copy=False)
    total_score = fields.Float("Total (/100)", copy=False, aggregator="avg", tracking=True)
    band = fields.Selection(BANDS, copy=False, tracking=True, index=True)
    risk = fields.Selection(RISKS, "AI-assistance risk", copy=False, tracking=True)
    red_flag_count = fields.Integer("Red flags", copy=False)
    integrity_signal_count = fields.Integer(compute="_compute_flag_counts")
    needs_review = fields.Boolean("Needs human review", copy=False)
    score_coding = fields.Float(compute="_compute_dimension_scores", store=True, aggregator="avg")
    score_learning = fields.Float(compute="_compute_dimension_scores", store=True, aggregator="avg")
    score_attitude = fields.Float(compute="_compute_dimension_scores", store=True, aggregator="avg")
    score_oral_english = fields.Float(compute="_compute_dimension_scores", store=True, aggregator="avg")
    score_written_english = fields.Float(compute="_compute_dimension_scores", store=True, aggregator="avg")

    # Review
    reviewer_id = fields.Many2one("res.users", tracking=True)
    decision = fields.Selection(DECISIONS, tracking=True, copy=False)
    band_confirmed = fields.Boolean(copy=False, tracking=True)
    review_notes = fields.Html(copy=False)
    reviewed_at = fields.Datetime(copy=False, readonly=True)
    live_recheck_required = fields.Boolean(compute="_compute_live_recheck", store=True,
                                           help="Medium/High AI-assistance risk: give a short live coding "
                                                "question in the technical round.")

    # Cost
    cost_total = fields.Float(compute="_compute_cost", digits=(12, 4))
    tokens_total = fields.Integer(compute="_compute_cost")

    _token_uniq = models.Constraint("UNIQUE(access_token)", "Interview tokens must be unique.")

    @api.depends("applicant_id.partner_name", "applicant_id.display_name", "create_date")
    def _compute_name(self):
        for rec in self:
            who = rec.applicant_id.partner_name or rec.applicant_id.display_name or ""
            rec.name = f"{who} – {fields.Date.to_string((rec.create_date or fields.Datetime.now()).date())}"

    def _compute_portal_url(self):
        base = self.get_base_url()
        for rec in self:
            rec.portal_url = f"{base}/linda/i/{rec.access_token}" if rec.access_token else False

    @api.depends("section_used")
    def _compute_duration(self):
        for rec in self:
            rec.duration_minutes = round(sum((rec.section_used or {}).values()) / 60.0, 1)

    @api.depends("flag_ids.is_signal")
    def _compute_flag_counts(self):
        for rec in self:
            rec.integrity_signal_count = len(rec.flag_ids.filtered("is_signal"))

    @api.depends("score_ids.final_score", "score_ids.dimension")
    def _compute_dimension_scores(self):
        for rec in self:
            by_dim = {s.dimension: s.final_score for s in rec.score_ids}
            for dim, _label in DIMENSION_SELECTION:
                rec[f"score_{dim}"] = by_dim.get(dim, 0.0)

    @api.depends("risk")
    def _compute_live_recheck(self):
        for rec in self:
            rec.live_recheck_required = rec.risk in ("medium", "high")

    def _token_usage(self):
        """AI token usage and cost per section, split into the interview itself and scoring."""
        self.ensure_one()
        groups = self.env["ai.interview.call.log"].sudo()._read_group(
            [("session_id", "=", self.id)], ["section", "phase"],
            ["input_tokens:sum", "output_tokens:sum", "cost:sum", "__count"])
        labels = dict(self.env["ai.interview.call.log"]._fields["section"].selection)
        order = list(labels)
        rows = {}
        for section, phase, tin, tout, cost, count in groups:
            section = section or "general"
            row = rows.setdefault(section, {"section": section, "label": labels[section], "interview": 0,
                                            "scoring": 0, "input": 0, "output": 0, "cost": 0.0, "calls": 0})
            row[phase or "interview"] += tin + tout
            row["input"] += tin
            row["output"] += tout
            row["cost"] += cost
            row["calls"] += count
        result = sorted((r for r in rows.values() if r["input"] or r["output"]),
                        key=lambda r: order.index(r["section"]))
        for row in result:
            row["total"] = row["input"] + row["output"]
            row["cost"] = round(row["cost"], 4)
        return result

    def _compute_cost(self):
        data = self.env["ai.interview.call.log"].sudo()._read_group(
            [("session_id", "in", self.ids)], ["session_id"], ["cost:sum", "input_tokens:sum", "output_tokens:sum"])
        by_id = {s.id: (c, i, o) for s, c, i, o in data}
        for rec in self:
            cost, tin, tout = by_id.get(rec.id, (0.0, 0, 0))
            rec.cost_total, rec.tokens_total = cost, tin + tout

    # ------------------------------------------------------------------
    # Invite / lifecycle
    # ------------------------------------------------------------------

    def _secret(self):
        return self.env["ir.config_parameter"].sudo().get_str("database.secret")

    def action_invite(self):
        template = self.env.ref("linda_ai_interview.mail_template_invite", raise_if_not_found=False)
        for rec in self:
            if rec.state not in ("draft", "expired"):
                raise UserError(self.env._("Only draft or expired sessions can be (re)invited."))
            expires = fields.Datetime.now() + timedelta(hours=rec.template_id.invite_hours or 72)
            rec.sudo().write({
                "access_token": tokens.make_token(rec._secret(), rec.id, expires.timestamp()),
                "expires_at": expires, "invited_at": fields.Datetime.now(), "state": "invited",
            })
            if template:
                template.sudo().send_mail(rec.id, force_send=False)
            rec.applicant_id.message_post(body=self.env._(
                "AI interview (Linda) invite sent. The link is valid until %s (UTC).",
                fields.Datetime.to_string(expires)))
        return True

    def action_send_reminder(self):
        template = self.env.ref("linda_ai_interview.mail_template_reminder", raise_if_not_found=False)
        sessions = self.filtered(lambda s: s.state == "invited")
        for rec in sessions:
            if template:
                template.sudo().send_mail(rec.id, force_send=False)
            rec.message_post(body=self.env._("Reminder sent to the candidate."))
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"type": "success", "message": self.env._("%s reminder(s) sent.", len(sessions))}}

    def action_cancel(self):
        for rec in self:
            if rec.state in ("scored", "reviewed"):
                raise UserError(self.env._("Scored interviews cannot be cancelled."))
        self.write({"state": "cancelled"})

    def action_reset_to_draft(self):
        self.filtered(lambda s: s.state in ("cancelled", "expired")).write({"state": "draft"})

    def _check_token(self, token):
        """Constant-time check of the URL token for public routes."""
        self.ensure_one()
        rec = self.sudo()
        if not rec.access_token or not rec.expires_at:
            return False
        if not hmac.compare_digest(rec.access_token, token or ""):
            return False
        if not tokens.verify_signature(rec._secret(), token, rec.id, rec.expires_at.timestamp()):
            return False
        # An interview already running may finish past the invite window.
        return rec.state == "in_progress" or fields.Datetime.now() <= rec.expires_at

    @api.model
    def _cron_expire_invites(self):
        expired = self.sudo().search([("state", "=", "invited"), ("expires_at", "<", fields.Datetime.now())])
        for rec in expired:
            rec.state = "expired"
            rec.applicant_id.message_post(body=self.env._("The AI interview invite expired without being started."))
        # Abandoned sessions: in progress but silent for over 12 hours -> auto-submit what we have.
        stale = self.sudo().search([("state", "=", "in_progress"),
                                    ("last_seen_at", "<", fields.Datetime.now() - timedelta(hours=12))])
        for rec in stale:
            rec._flag("abandoned", "Session abandoned; auto-submitted after 12 hours of inactivity.")
            rec._submit(auto=True)

    # ------------------------------------------------------------------
    # Review
    # ------------------------------------------------------------------

    def action_confirm_review(self):
        for rec in self:
            if rec.state != "scored":
                raise UserError(self.env._("Only scored interviews can be reviewed."))
            if not rec.decision:
                raise UserError(self.env._("Record the decision before confirming the review."))
            if rec.risk in ("medium", "high") and not rec.review_notes:
                raise UserError(self.env._("Medium/High AI-assistance risk: add review notes on the integrity "
                                           "signals you checked."))
            rec.write({"state": "reviewed", "band_confirmed": True, "reviewer_id": rec.reviewer_id.id or self.env.uid,
                       "reviewed_at": fields.Datetime.now()})
            decision = dict(DECISIONS)[rec.decision]
            body = self.env._("AI interview reviewed by %(user)s: band %(band)s confirmed, decision: %(decision)s.",
                              user=self.env.user.name, band=dict(BANDS).get(rec.band, "-"), decision=decision)
            rec.message_post(body=body)
            rec.applicant_id.message_post(body=body)
            rec.activity_feedback(["mail.mail_activity_data_todo"])
        return True

    def action_reopen_review(self):
        self.filtered(lambda s: s.state == "reviewed").write({"state": "scored", "band_confirmed": False})

    def action_move_next_stage(self):
        """Bulk: move applicants of reviewed 'advance' sessions to the next pipeline stage."""
        moved = 0
        for rec in self.filtered(lambda s: s.state == "reviewed" and s.decision == "advance"):
            applicant = rec.applicant_id
            stages = self.env["hr.recruitment.stage"].search(
                ["|", ("job_ids", "=", False), ("job_ids", "=", applicant.job_id.id)], order="sequence, id")
            later = stages.filtered(lambda s: (s.sequence, s.id) > (applicant.stage_id.sequence, applicant.stage_id.id))
            if later:
                applicant.stage_id = later[0]
                moved += 1
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"type": "success", "message": self.env._("%s applicant(s) moved.", moved)}}

    def action_print_scorecard(self):
        return self.env.ref("linda_ai_interview.action_report_scorecard").report_action(self)

    def action_open_dashboard(self):
        self.ensure_one()
        return {"type": "ir.actions.client", "tag": "linda_candidate_dashboard", "name": self.name,
                "params": {"session_id": self.id}}

    def action_rescore(self):
        for rec in self.filtered(lambda s: s.state in ("submitted", "scored")):
            rec.write({"scoring_state": "queued", "scoring_attempts": 0, "scoring_next_at": fields.Datetime.now()})
        self.env.ref("linda_ai_interview.ir_cron_process_scoring")._trigger()

    # ------------------------------------------------------------------
    # Privacy: withdrawal, retention
    # ------------------------------------------------------------------

    def action_withdraw_consent(self):
        """Withdrawal stops processing and deletes interview data (FRD §10)."""
        for rec in self.sudo():
            rec._purge_data(("audio", "transcript", "keystrokes", "answers", "scores"))
            rec.write({"state": "cancelled", "scoring_state": "none", "consent_at": False})
            rec.applicant_id.message_post(body=self.env._(
                "The candidate withdrew consent for the AI interview. Interview data was deleted."))
        return True

    def _purge_data(self, kinds):
        self.ensure_one()
        responses = self.response_ids.sudo()
        if "audio" in kinds:
            responses.mapped("audio_attachment_ids").unlink()
            self.env["ir.attachment"].sudo().search([("res_model", "=", "ai.interview.response"),
                                                     ("res_id", "in", responses.ids)]).unlink()
        if "transcript" in kinds:
            responses.write({"transcript": False, "transcript_final": False})
            for resp in responses.filtered(lambda r: r.section == "voice"):
                resp.followups = [dict(f, a="", a_final="") for f in (resp.followups or [])]
        if "keystrokes" in kinds:
            responses.write({"keystroke_log": False})
        if "answers" in kinds:
            responses.unlink()
            self.flag_ids.sudo().unlink()
            self.call_log_ids.sudo().unlink()
        if "scores" in kinds:
            self.score_ids.sudo().unlink()

    @api.model
    def _cron_purge_retention(self):
        params = self.env["ir.config_parameter"].sudo()
        now = fields.Datetime.now()
        for kind in ("audio", "transcript", "keystrokes", "scores"):
            days = params.get_int(f"linda_ai_interview.retention_{kind}_days", 180 if kind != "scores" else 0)
            if days <= 0:
                continue
            cutoff = now - timedelta(days=days)
            sessions = self.sudo().search([
                "|", "&", ("state", "=", "reviewed"), ("reviewed_at", "<", cutoff),
                "&", ("state", "in", ("expired", "cancelled")), ("write_date", "<", cutoff)])
            for rec in sessions:
                rec._purge_data((kind,))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _flag(self, ftype, detail="", response=None, evidence=None):
        self.ensure_one()
        return self.env["ai.interview.flag"].sudo().create({
            "session_id": self.id, "type": ftype, "detail": detail,
            "response_id": response.id if response else False, "evidence": evidence or False,
        })

    @api.constrains("decision", "state")
    def _check_decision(self):
        for rec in self:
            if rec.state == "reviewed" and not rec.decision:
                raise ValidationError(self.env._("A reviewed interview needs a decision."))
