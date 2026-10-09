from odoo import fields, models

from .ai_template import DIMENSION_SELECTION


class AiInterviewCriterion(models.Model):
    _name = "ai.interview.criterion"
    _description = "Linda – rubric criterion"
    _order = "dimension, sequence, id"

    dimension = fields.Selection(DIMENSION_SELECTION, required=True, index=True)
    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(help="What the criterion observes.")
    descriptor_1 = fields.Text("1 – Insufficient", required=True)
    descriptor_2 = fields.Text("2 – Weak", required=True)
    descriptor_3 = fields.Text("3 – Adequate", required=True)
    descriptor_4 = fields.Text("4 – Good", required=True)
    descriptor_5 = fields.Text("5 – Strong", required=True)

    def _rubric(self):
        return [{"name": c.name + (f" ({c.description})" if c.description else ""),
                 "descriptors": {i: c[f"descriptor_{i}"] for i in range(1, 6)}} for c in self]


class AiInterviewConsentNotice(models.Model):
    _name = "ai.interview.consent.notice"
    _description = "Linda – consent notice version"
    _order = "version desc"

    name = fields.Char(required=True, default="Candidate privacy notice")
    version = fields.Integer(required=True, default=1)
    active = fields.Boolean(default=True)
    body = fields.Html(required=True, sanitize=True)
    date_published = fields.Date(default=fields.Date.context_today)

    _version_uniq = models.Constraint("UNIQUE(version)", "Notice versions must be unique.")

    def write(self, vals):
        # Published wording is immutable: edits create a new version so each consent stays traceable.
        if "body" in vals and self.env["ai.interview.session"].sudo().search_count(
                [("consent_notice_id", "in", self.ids)], limit=1):
            new = self.copy({"body": vals.pop("body"), "version": max(self.search([]).mapped("version")) + 1})
            self.active = False
            return super().write(vals) if vals else bool(new)
        return super().write(vals)

    def _current(self):
        return self.search([], order="version desc", limit=1)
