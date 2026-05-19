from odoo import models, fields, api

class SaleOrderTemplate(models.Model):
    _inherit = 'sale.order.template'

    plan_id = fields.Many2one('subscription.plan', string='Recurring Plan', help="Select the default recurring billing plan for orders created with this template.")
    is_forever = fields.Boolean(string='Last Forever', default=True, help="If checked, this subscription has no pre-defined end date.")
    duration_value = fields.Integer(string='End After Value', default=6)
    duration_unit = fields.Selection([
        ('days', 'Days'),
        ('weeks', 'Weeks'),
        ('months', 'Months'),
        ('years', 'Years'),
    ], string='End After Unit', default='years')
    template_type = fields.Selection([
        ('quotation', 'Quotation'),
    ], string='Type', default='quotation')
    quote_calculator = fields.Char(string='Quote calculator')
    is_shared = fields.Boolean(string='Share', default=True)
    sales_team_id = fields.Many2one('crm.team', string='Sales Team')
