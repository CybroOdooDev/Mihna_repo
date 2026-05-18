from odoo import models, fields, api

class SubscriptionLine(models.Model):
    _name = 'subscription.line'
    _description = 'Subscription Line'

    subscription_id = fields.Many2one('subscription.subscription', string='Subscription', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    name = fields.Text(string='Description', required=True)
    
    quantity = fields.Float(string='Quantity', default=1.0, required=True)
    price_unit = fields.Float(string='Unit Price', required=True, default=0.0)
    discount = fields.Float(string='Discount (%)', default=0.0)
    
    currency_id = fields.Many2one(related='subscription_id.currency_id', store=True)
    price_subtotal = fields.Monetary(string='Subtotal', compute='_compute_price_subtotal', store=True)

    @api.depends('quantity', 'price_unit', 'discount')
    def _compute_price_subtotal(self):
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            line.price_subtotal = line.quantity * price

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name
            self.price_unit = self.product_id.list_price
