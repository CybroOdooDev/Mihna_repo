# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class SubscriptionDunningPlan(models.Model):
    _name = 'subscription.dunning.plan'
    _description = 'Subscription Dunning Plan'
    _order = 'name'

    name = fields.Char(string='Plan Name', required=True, translate=True)
    active = fields.Boolean(default=True)
    line_ids = fields.One2many(
        'subscription.dunning.plan.line', 'plan_id', string='Dunning Stages',
        copy=True
    )
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

class SubscriptionDunningPlanLine(models.Model):
    _name = 'subscription.dunning.plan.line'
    _description = 'Dunning Plan Stage'
    _order = 'delay_days asc'

    plan_id = fields.Many2one(
        'subscription.dunning.plan', string='Dunning Plan',
        required=True, ondelete='cascade'
    )
    delay_days = fields.Integer(
        string='Delay (Days)', required=True,
        help="Number of days after the invoice due date to trigger this stage."
    )
    mail_template_id = fields.Many2one(
        'mail.template', string='Email Template',
        help="Email to send to the customer at this stage."
    )
    action_type = fields.Selection([
        ('none', 'No Action'),
        ('pause', 'Pause Subscription'),
        ('close', 'Cancel Subscription')
    ], string='Subscription Action', default='none', required=True)

    @api.constrains('delay_days')
    def _check_delay_days(self):
        for line in self:
            if line.delay_days < 0:
                raise ValidationError(_("Delay days cannot be negative."))
