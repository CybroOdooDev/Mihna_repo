<<<<<<< HEAD
=======
<<<<<<< HEAD
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
# -*- coding: utf-8 -*-
from odoo import models, fields

class ResPartner(models.Model):
    """Inherited Res Partner model to link and calculate customer subscription contracts."""
<<<<<<< HEAD
=======
=======
from odoo import models, fields

class ResPartner(models.Model):
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
    _inherit = 'res.partner'

    subscription_ids = fields.One2many('subscription.subscription', 'partner_id', string='Subscriptions')
    subscription_count = fields.Integer(string='Subscription Count', compute='_compute_subscription_count')

    def _compute_subscription_count(self):
<<<<<<< HEAD
        """Compute the total count of active subscription contracts for this customer."""
=======
<<<<<<< HEAD
        """Compute the total count of active subscription contracts for this customer."""
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
        for partner in self:
            partner.subscription_count = len(partner.subscription_ids)
