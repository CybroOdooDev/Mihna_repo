<<<<<<< HEAD
# -*- coding: utf-8 -*-
from odoo import models, fields

class ResPartner(models.Model):
    """Inherited Res Partner model to link and calculate customer subscription contracts."""
=======
from odoo import models, fields

class ResPartner(models.Model):
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
    _inherit = 'res.partner'

    subscription_ids = fields.One2many('subscription.subscription', 'partner_id', string='Subscriptions')
    subscription_count = fields.Integer(string='Subscription Count', compute='_compute_subscription_count')

    def _compute_subscription_count(self):
<<<<<<< HEAD
        """Compute the total count of active subscription contracts for this customer."""
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
        for partner in self:
            partner.subscription_count = len(partner.subscription_ids)
