# -*- coding: utf-8 -*-
from odoo import models, fields

class StockPicking(models.Model):
    """Inherited Stock Picking model to link physical fulfillment delivery orders with active subscription contracts."""
    _inherit = 'stock.picking'

    subscription_order_id = fields.Many2one('sale.order', string='Subscription', readonly=True, copy=False)
