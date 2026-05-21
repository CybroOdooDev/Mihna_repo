# -*- coding: utf-8 -*-
from odoo import models, fields

class AccountMove(models.Model):
    """Inherited Account Move model to link invoices with active subscription contracts."""
    _inherit = 'account.move'

    subscription_order_id = fields.Many2one('sale.order', string='Subscription', readonly=True, copy=False)
