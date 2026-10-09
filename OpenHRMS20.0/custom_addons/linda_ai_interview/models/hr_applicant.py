from odoo import api, fields, models
from odoo.exceptions import UserError

from .ai_session import BANDS, RISKS, SESSION_STATES

ACTIVE_STATES = ("invited", "in_progress", "submitted", "scored")


class HrApplicant(models.Model):
    _inherit = "hr.applicant"

    ai_session_ids = fields.One2many("ai.interview.session", "applicant_id", string="AI interviews")
    ai_session_count = fields.Integer(compute="_compute_ai_history", string="AI interview history")
    ai_latest_session_id = fields.Many2one("ai.interview.session", compute="_compute_ai_latest", store=True,
                                           string="Latest AI interview")
    ai_state = fields.Selection(SESSION_STATES, compute="_compute_ai_latest", store=True, string="AI interview status")
    ai_band = fields.Selection(BANDS, compute="_compute_ai_latest", store=True, string="AI band")
    ai_total_score = fields.Float(compute="_compute_ai_latest", store=True, string="AI score (/100)",
                                  aggregator="avg")
    ai_risk = fields.Selection(RISKS, compute="_compute_ai_latest", store=True, string="AI-assistance risk")
    ai_red_flag_count = fields.Integer(compute="_compute_ai_latest", store=True, string="AI red flags")
    ai_can_invite = fields.Boolean(compute="_compute_ai_can_invite")
    ai_score_ids = fields.One2many(related="ai_latest_session_id.score_ids", string="AI scores")
    ai_flag_ids = fields.One2many(related="ai_latest_session_id.flag_ids", string="AI integrity events")
    ai_live_recheck = fields.Boolean(related="ai_latest_session_id.live_recheck_required")

    @api.depends("ai_session_ids.state", "ai_session_ids.band", "ai_session_ids.total_score",
                 "ai_session_ids.risk", "ai_session_ids.red_flag_count")
    def _compute_ai_latest(self):
        for rec in self:
            latest = rec.ai_session_ids.filtered(lambda s: s.state != "cancelled").sorted("id", reverse=True)[:1]
            rec.ai_latest_session_id = latest
            rec.ai_state = latest.state
            rec.ai_band = latest.band
            rec.ai_total_score = latest.total_score
            rec.ai_risk = latest.risk
            rec.ai_red_flag_count = latest.red_flag_count

    @api.depends("ai_session_ids.state")
    def _compute_ai_can_invite(self):
        for rec in self:
            rec.ai_can_invite = not rec._ai_active_session()

    def _ai_history_domain(self):
        """Sessions of the same person across applications (Odoo 19 has no hr.candidate model,
        so we match the contact and the normalised e-mail)."""
        self.ensure_one()
        domain = [("applicant_id", "=", self.id)]
        if self.partner_id:
            domain = ["|", ("partner_id", "=", self.partner_id.id)] + domain
        if self.email_normalized:
            domain = ["|", ("candidate_email", "=", self.email_normalized)] + domain
        return domain

    def _compute_ai_history(self):
        Session = self.env["ai.interview.session"]
        for rec in self:
            rec.ai_session_count = Session.search_count(rec._ai_history_domain()) if rec.id else 0

    def _ai_active_session(self):
        self.ensure_one()
        return self.ai_session_ids.filtered(lambda s: s.state in ACTIVE_STATES)[:1]

    def _ai_send_interview(self, campaign=None):
        self.ensure_one()
        if self._ai_active_session():
            raise UserError(self.env._("%s already has an active AI interview.", self.partner_name or self.display_name))
        if not self.email_from:
            raise UserError(self.env._("The applicant needs an e-mail address to receive the interview link."))
        template = campaign.template_id if campaign else self.env["ai.interview.template"]._for_job(self.job_id)
        if not template:
            raise UserError(self.env._("No AI interview template is configured for the job position %s.",
                                       self.job_id.name or "-"))
        self._ai_check_pool(template)
        if not campaign:
            campaign = self.env["ai.interview.campaign"].search(
                [("job_id", "=", self.job_id.id), ("state", "=", "running"), ("template_id", "=", template.id)], limit=1)
        session = self.env["ai.interview.session"].create({
            "applicant_id": self.id, "template_id": template.id, "campaign_id": campaign.id if campaign else False,
            "partner_id": self.partner_id.id, "candidate_email": self.email_normalized,
        })
        if campaign and self not in campaign.applicant_ids:
            campaign.applicant_ids = [(4, self.id)]
        session.action_invite()
        return session

    def _ai_check_pool(self, template):
        Question = self.env["ai.interview.question"].sudo()
        for section in template._sections().filtered(lambda s: s.section_type in ("coding", "learn")):
            available = Question.search_count([("qtype", "=", section.section_type), ("state", "=", "approved")])
            if available < section.question_count:
                raise UserError(self.env._(
                    "The %(section)s question pool has only %(n)s approved question(s); the template needs "
                    "%(needed)s. Generate and approve questions first.",
                    section=section.display_name, n=available, needed=section.question_count))

    def action_send_ai_interview(self):
        sessions = self.env["ai.interview.session"]
        for rec in self:
            sessions |= rec._ai_send_interview()
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"type": "success", "title": self.env._("Linda"),
                           "message": self.env._("AI interview invite sent."),
                           "next": {"type": "ir.actions.act_window_close"}}}

    def action_view_ai_sessions(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("linda_ai_interview.action_ai_interview_session")
        action.update(domain=self._ai_history_domain(), context={"create": False})
        return action

    def action_open_ai_dashboard(self):
        self.ensure_one()
        if not self.ai_latest_session_id:
            raise UserError(self.env._("No AI interview yet."))
        return self.ai_latest_session_id.action_open_dashboard()

    def write(self, vals):
        if "stage_id" in vals and not self.env.context.get("linda_skip_review_check"):
            pending = self.filtered(lambda a: a.ai_latest_session_id.state == "scored")
            if pending:
                raise UserError(self.env._(
                    "A reviewer must confirm the AI interview band before %s moves stage.",
                    ", ".join(pending.mapped(lambda a: a.partner_name or a.display_name))))
        res = super().write(vals)
        if "stage_id" in vals:
            self._ai_auto_invite()
        return res

    def _ai_auto_invite(self):
        if not self.env["ir.config_parameter"].sudo().get_bool("linda_ai_interview.auto_invite"):
            return
        Template = self.env["ai.interview.template"]
        for rec in self:
            template = Template._for_job(rec.job_id)
            if template and template.auto_invite_stage_id == rec.stage_id and not rec._ai_active_session() \
                    and rec.email_from:
                try:
                    rec._ai_send_interview()
                except UserError as exc:
                    rec.message_post(body=self.env._("Automatic AI interview invite failed: %s", exc))
