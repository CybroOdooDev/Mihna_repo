# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SubscriptionLine(models.Model):
    """Subscription Line model representing individual products or services within a subscription contract."""
    _name = 'subscription_line'
    _description = 'Subscription Line'
    _order = 'id'

    subscription_id = fields.Many2one(
        'subscription.subscription', string='Subscription',
        ondelete='cascade', required=True, index=True
    )
    product_id = fields.Many2one(
        'product.product', string='Product', required=True
    )
    name = fields.Text(string='Description')
    quantity = fields.Float(string='Quantity', default=1.0, digits='Product Unit of Measure')
    uom_id = fields.Many2one(
        'uom.uom', string='Unit of Measure',
        related='product_id.uom_id', readonly=True
    )
    price_unit = fields.Float(string='Unit Price', digits='Product Price')
    discount = fields.Float(string='Discount (%)', digits='Discount', default=0.0)
    price_subtotal = fields.Float(
        string='Subtotal', compute='_compute_price_subtotal', store=True
    )

    @api.depends('quantity', 'price_unit', 'discount')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = (
                line.quantity * line.price_unit * (1.0 - line.discount / 100.0)
            )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            if hasattr(self.product_id, 'get_product_multiline_description_sale'):
                self.name = self.product_id.get_product_multiline_description_sale()
            else:
                self.name = self.product_id.name
            self.price_unit = self.product_id.list_price
