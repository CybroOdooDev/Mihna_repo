# -*- coding: utf-8 -*-
from odoo import models, fields

class LoyaltyProgram(models.Model):
    """Extension of the standard Odoo Loyalty/Coupon Program to support 
    recurring subscription discounts, limited invoice application, and
    first-time customer constraints."""
    _inherit = 'loyalty.program'

    recurring_type = fields.Selection([
        ('first', 'First Invoice Only'),
        ('limited', 'Limited Invoices'),
        ('forever', 'Forever')
    ], string='Recurring Application', default='first',
       help="Determine how this coupon applies to recurring subscription invoices.")
    
    recurring_invoices = fields.Integer(
        string='Number of Invoices', default=3,
        help="Number of invoices this coupon applies to, if Limited Invoices is selected."
    )
    
    plan_ids = fields.Many2many(
        'subscription.plan', string='Specific Plans',
        help="Leave empty to apply to all plans."
    )
    
    first_time_only = fields.Boolean(
        string='First-Time Customers Only', default=False,
        help="If true, this promotion will only apply if the customer has no previous active subscriptions."
    )
    
    max_uses_per_customer = fields.Integer(
        string='Max Uses Per Customer', default=1,
        help="Maximum number of times a single customer can use this program."
    )
