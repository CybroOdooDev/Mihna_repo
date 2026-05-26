# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class SubscriptionDunningPlan(models.Model):
    """Model representing subscription payment retry and dunning plan configurations.
    Coordinates multiple staged actions to take place sequentially when invoices remain unpaid."""
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
    """Model representing a single stage or trigger level within a Dunning Plan.
    Enforces subscription state actions and fires customized WhatsApp notifications."""
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
        ('close', 'Cancel Subscription'),
        ('block', 'Block Subscription')
    ], string='Subscription Action', default='none', required=True)
    send_whatsapp = fields.Boolean(
        string='Send WhatsApp', default=False,
        help="Enable/Disable automated WhatsApp message sending at this stage."
    )
    whatsapp_template_id = fields.Many2one(
        'subscription.whatsapp.template',
        string='WhatsApp Template',
        help="Custom text template for WhatsApp. Available placeholders: {customer_name}, {subscription_name}, {invoice_amount}, {invoice_currency}, {status_label}"
    )

    def _compute_display_name(self):
        """Computes and assigns a user-friendly display name for the dunning line based on delay and action type."""
        for line in self:
            action_labels = dict(self._fields['action_type'].selection)
            action_label = action_labels.get(line.action_type, 'No Action')
            line.display_name = _("Day %s: %s") % (line.delay_days, action_label)

    @api.constrains('delay_days')
    def _check_delay_days(self):
        """Validates that the delay days input is a non-negative integer value."""
        for line in self:
            if line.delay_days < 0:
                raise ValidationError(_("Delay days cannot be negative."))
