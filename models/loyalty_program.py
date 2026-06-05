# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2026-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import models, fields

class LoyaltyProgram(models.Model):
    """Extension of the standard Odoo Loyalty/Coupon Program to support 
    recurring subscription discounts, limited invoice application, and
    first-time customer constraints."""
    _inherit = 'loyalty.program'
    _description = 'Loyalty Program'

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
    
    is_first_time_only = fields.Boolean(
        string='First-Time Customers Only', default=False,
        help="If true, this promotion will only apply if the customer has no previous active subscriptions."
    )
    
