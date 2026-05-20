<<<<<<< HEAD
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
=======
<<<<<<< HEAD
# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SubscriptionLine(models.Model):
    """Subscription Line model representing individual recurring service items on a subscription contract."""
=======
from odoo import models, fields, api

class SubscriptionLine(models.Model):
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
    _name = 'subscription.line'
    _description = 'Subscription Line'

    subscription_id = fields.Many2one('subscription.subscription', string='Subscription', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    name = fields.Text(string='Description', required=True)
    
    quantity = fields.Float(string='Quantity', default=1.0, required=True)
    price_unit = fields.Float(string='Unit Price', required=True, default=0.0)
    discount = fields.Float(string='Discount (%)', default=0.0)
<<<<<<< HEAD
    billing_type = fields.Selection([
        ('fixed', 'Fixed Fee'),
        ('seat', 'Seat-Based'),
        ('usage', 'Usage-Based')
    ], string='Billing Type', default='fixed', required=True)
=======
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
    
    currency_id = fields.Many2one(related='subscription_id.currency_id', store=True)
    price_subtotal = fields.Monetary(string='Subtotal', compute='_compute_price_subtotal', store=True)

<<<<<<< HEAD
    @api.depends('quantity', 'price_unit', 'discount', 'billing_type')
    def _compute_price_subtotal(self):
        """Compute the subtotal for this subscription line based on quantity, price, discount, and billing type."""
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            if line.billing_type == 'usage':
                line.price_subtotal = 0.0
            else:
                line.price_subtotal = line.quantity * price

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Update product unit price and description when product_id changes."""
=======
    @api.depends('quantity', 'price_unit', 'discount')
    def _compute_price_subtotal(self):
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            line.price_subtotal = line.quantity * price

    @api.onchange('product_id')
    def _onchange_product_id(self):
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
        if self.product_id:
            self.name = self.product_id.display_name
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
            self.price_unit = self.product_id.list_price
