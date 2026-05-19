# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SubscriptionCoupon(models.Model):
    """Subscription Promo Coupon model to define discounts applied during subscription checkouts."""
    _name = 'subscription.coupon'
    _description = 'Subscription Promo Coupon'

    name = fields.Char(string='Coupon Name', required=True)
    code = fields.Char(string='Coupon Code', required=True, copy=False)
    discount_type = fields.Selection([
        ('percentage', 'Percentage (%)'),
        ('fixed', 'Fixed Amount')
    ], string='Discount Type', required=True, default='percentage')
    discount_value = fields.Float(string='Discount Value', required=True, default=0.0)
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The coupon code must be unique!')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Override creation to automatically sanitize and uppercase coupon codes."""
        for vals in vals_list:
            if 'code' in vals and vals['code']:
                vals['code'] = vals['code'].strip().upper()
        return super().create(vals_list)

    def write(self, vals):
        """Override write to automatically sanitize and uppercase coupon codes."""
        if 'code' in vals and vals['code']:
            vals['code'] = vals['code'].strip().upper()
        return super().write(vals)
