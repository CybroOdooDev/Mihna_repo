<<<<<<< HEAD
# -*- coding: utf-8 -*-
from odoo import models, fields

class StockPicking(models.Model):
    """Inherited Stock Picking model to link physical fulfillment delivery orders with active subscription contracts."""
=======
from odoo import models, fields

class StockPicking(models.Model):
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
    _inherit = 'stock.picking'

    subscription_id = fields.Many2one('subscription.subscription', string='Subscription', readonly=True, copy=False)
