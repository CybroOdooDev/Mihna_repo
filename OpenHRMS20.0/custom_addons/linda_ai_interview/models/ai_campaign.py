from odoo import api, fields, models
from odoo.exceptions import UserError


class AiInterviewCampaign(models.Model):
    _name = "ai.interview.campaign"
    _description = "Linda – hiring campaign"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc, id desc"

    name = fields.Char(required=True, tracking=True)
    job_id = fields.Many2one("hr.job", required=True, tracking=True)
    template_id = fields.Many2one("ai.interview.template", required=True, tracking=True,
                                  domain="[('active', '=', True)]")
    date_start = fields.Date(default=fields.Date.context_today, required=True)
    date_end = fields.Date()
    applicant_ids = fields.Many2many("hr.applicant", string="Applicants",
                                     domain="[('job_id', '=', job_id)]")
    session_ids = fields.One2many("ai.interview.session", "campaign_id")
    user_id = fields.Many2one("res.users", "Owner", default=lambda self: self.env.user, tracking=True)
    reviewer_ids = fields.Many2many("res.users", string="Reviewers",
                                    help="Tech leads / interviewers who review this campaign's scorecards.")
    state = fields.Selection([("draft", "Draft"), ("running", "Running"), ("closed", "Closed")],
                             default="draft", required=True, tracking=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    invited_count = fields.Integer(compute="_compute_stats")
    started_count = fields.Integer(compute="_compute_stats")
    submitted_count = fields.Integer(compute="_compute_stats")
    expired_count = fields.Integer(compute="_compute_stats")
    review_pending_count = fields.Integer(compute="_compute_stats")
    completion_rate = fields.Float(compute="_compute_stats")
    average_score = fields.Float(compute="_compute_stats")

    @api.onchange("job_id")
    def _onchange_job_id(self):
        if self.job_id and not self.template_id:
            self.template_id = self.env["ai.interview.template"]._for_job(self.job_id)

    @api.depends("session_ids.state", "session_ids.total_score")
    def _compute_stats(self):
        for rec in self:
            sessions = rec.session_ids.filtered(lambda s: s.state != "cancelled")
            invited = sessions.filtered(lambda s: s.state != "draft")
            started = invited.filtered("started_at")
            submitted = invited.filtered(lambda s: s.state in ("submitted", "scored", "reviewed"))
            scored = invited.filtered(lambda s: s.state in ("scored", "reviewed"))
            rec.invited_count = len(invited)
            rec.started_count = len(started)
            rec.submitted_count = len(submitted)
            rec.expired_count = len(invited.filtered(lambda s: s.state == "expired"))
            rec.review_pending_count = len(invited.filtered(lambda s: s.state == "scored"))
            rec.completion_rate = 100.0 * len(submitted) / len(invited) if invited else 0.0
            rec.average_score = sum(scored.mapped("total_score")) / len(scored) if scored else 0.0

    def action_start(self):
        self.write({"state": "running"})

    def action_close(self):
        self.write({"state": "closed"})

    def action_reset(self):
        self.write({"state": "draft"})

    def action_invite_applicants(self):
        """Send invites to every campaign applicant without an active session."""
        self.ensure_one()
        if self.state != "running":
            raise UserError(self.env._("Start the campaign before sending invites."))
        sent = 0
        for applicant in self.applicant_ids:
            if not applicant._ai_active_session():
                applicant._ai_send_interview(campaign=self)
                sent += 1
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": self.env._("Invites sent"), "type": "success",
                           "message": self.env._("%s interview invite(s) sent.", sent)}}

    def action_open_dashboard(self):
        self.ensure_one()
        return {"type": "ir.actions.client", "tag": "linda_campaign_dashboard", "name": self.name,
                "params": {"campaign_id": self.id}, "context": {"active_id": self.id}}

    def action_view_sessions(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("linda_ai_interview.action_ai_interview_session")
        action.update(domain=[("campaign_id", "=", self.id)], context={"default_campaign_id": self.id})
        return action
