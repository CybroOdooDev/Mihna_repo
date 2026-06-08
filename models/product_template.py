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
from odoo import models, fields, _
from markupsafe import Markup


class ProductTemplate(models.Model):
    """Inherited Product Template model to define if a product represents a recurring subscription plan."""
    _inherit = 'product.template'
    _description = 'Product Template'

    recurring_ok = fields.Boolean(
        string='Subscription Product', default=False,
        help='Check if this product is a recurring subscription plan.'
    )
    subscription_pricing_ids = fields.One2many(
        'subscription.plan.pricing', 'product_template_id',
        string='Recurring Prices'
    )
    accept_one_time = fields.Boolean(
        string='Accept One-Time',
        help='Allow customers to bypass subscription and buy this product as a one-time purchase.'
    )
    prorated_price = fields.Boolean(
        string='Prorated Price', default=True,
        help='If checked, the first invoice will be prorated based on the billing cycle date.'
    )
