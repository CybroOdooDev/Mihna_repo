# -*- coding: utf-8 -*-
from odoo import models, fields

class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    subscription_pricing_ids = fields.One2many(
        'subscription.plan.pricing', 'pricelist_id',
        string='Recurring Prices'
    )
