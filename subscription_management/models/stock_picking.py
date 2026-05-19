from odoo import models, fields

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    subscription_id = fields.Many2one('subscription.subscription', string='Subscription', readonly=True, copy=False)
