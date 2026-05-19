# -*- coding: utf-8 -*-
from odoo import models, fields

class StockPicking(models.Model):
    """Inherited Stock Picking model to link physical fulfillment delivery orders with active subscription contracts."""
    _inherit = 'stock.picking'

    subscription_id = fields.Many2one('subscription.subscription', string='Subscription', readonly=True, copy=False)
