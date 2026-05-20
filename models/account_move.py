# -*- coding: utf-8 -*-
from odoo import models, fields

class AccountMove(models.Model):
    """Inherited Account Move model to link invoices with active subscription contracts."""
    _inherit = 'account.move'

    subscription_id = fields.Many2one('subscription.subscription', string='Subscription', readonly=True, copy=False)
