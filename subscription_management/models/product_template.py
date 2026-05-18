from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    recurring_ok = fields.Boolean(string='Subscription Product', default=False, help='Check if this product is a recurring subscription plan.')
    subscription_plan_id = fields.Many2one('subscription.plan', string='Subscription Plan', help='Plan used when selling this product.')
