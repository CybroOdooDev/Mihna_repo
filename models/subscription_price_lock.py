# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SubscriptionPriceChangeLog(models.Model):
    """Audit log tracking every product price change that impacts active subscription lines.

    When a product's ``list_price`` is updated by an admin, this engine fires and
    records one entry per affected subscription line, marking whether the
    subscription was *grandfathered* (price-locked) or received the new price.
    """

    _name = 'subscription.price.change.log'
    _description = 'Subscription Price Change Log'
    _order = 'change_date desc'
    _rec_name = 'product_id'

    sale_order_id = fields.Many2one(
        'sale.order', string='Subscription (Sale Order)',
        required=True, ondelete='cascade', index=True
    )
    product_id = fields.Many2one(
        'product.product', string='Product', required=True, readonly=True
    )
    old_price = fields.Float(
        string='Old Price', digits='Product Price', readonly=True
    )
    new_price = fields.Float(
        string='New Price', digits='Product Price', readonly=True
    )
    price_diff = fields.Float(
        string='Change (Δ)', compute='_compute_price_diff',
        store=True, digits='Product Price'
    )
    change_date = fields.Datetime(
        string='Changed On', default=fields.Datetime.now, readonly=True
    )
    changed_by = fields.Many2one(
        'res.users', string='Changed By',
        default=lambda self: self.env.user, readonly=True
    )
    is_protected = fields.Boolean(
        string='Grandfathered',
        help="True = subscription was price-locked; old price was retained.\n"
             "False = new price was applied to the subscription line."
    )
    notes = fields.Char(string='Notes', readonly=True)

    @api.depends('old_price', 'new_price')
    def _compute_price_diff(self):
        """Compute the absolute price difference between old and new prices."""
        for rec in self:
            rec.price_diff = rec.new_price - rec.old_price
