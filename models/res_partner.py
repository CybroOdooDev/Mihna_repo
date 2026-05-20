# -*- coding: utf-8 -*-
from odoo import models, fields

class ResPartner(models.Model):
    """Inherited Res Partner model to link and calculate customer subscription contracts."""
    _inherit = 'res.partner'

    subscription_ids = fields.One2many('subscription.subscription', 'partner_id', string='Subscriptions')
    subscription_count = fields.Integer(string='Subscription Count', compute='_compute_subscription_count')

    def _compute_subscription_count(self):
        """Compute the total count of active subscription contracts for this customer."""
        for partner in self:
            partner.subscription_count = len(partner.subscription_ids)
