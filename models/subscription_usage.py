# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SubscriptionUsage(models.Model):
    """Subscription Usage model tracking metered customer consumption units for usage-based invoicing."""
    _name = 'subscription.usage'
    _description = 'Metered Usage Consumption'
    _order = 'date desc, id desc'

    subscription_order_id = fields.Many2one('sale.order', string='Subscription', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Metered Product', required=True)
    quantity = fields.Float(string='Usage Quantity', default=0.0, required=True)
    date = fields.Date(string='Consumption Date', default=fields.Date.context_today, required=True)
    billed = fields.Boolean(string='Billed', default=False, readonly=True)
    description = fields.Char(string='Remarks')

