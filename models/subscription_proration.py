# -*- coding: utf-8 -*-
from odoo import models, fields

class SubscriptionProration(models.Model):
    """Tracks prorated charges for mid-cycle subscription changes."""
    _name = 'subscription.proration'
    _description = 'Subscription Proration'
    _order = 'date desc, id desc'

    subscription_order_id = fields.Many2one('sale.order', string='Subscription', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    description = fields.Char(string='Description', required=True)
    quantity = fields.Float(string='Quantity', default=1.0)
    amount = fields.Float(string='Total Prorated Amount', required=True)
    date = fields.Date(string='Date', default=fields.Date.context_today, required=True)
    invoiced = fields.Boolean(string='Invoiced', default=False, readonly=True)
