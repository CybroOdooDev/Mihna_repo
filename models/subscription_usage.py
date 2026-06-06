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
from odoo import models, fields, api

class SubscriptionUsage(models.Model):
    """Subscription Usage model tracking metered customer consumption units for usage-based invoicing."""
    _name = 'subscription.usage'
    _description = 'Metered Usage Consumption'
    _order = 'date desc, id desc'

    subscription_order_id = fields.Many2one('sale.order', string='Subscription', required=True,
                                            ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Metered Product', required=True)
    quantity = fields.Float(string='Usage Quantity', default=0.0, required=True)
    date = fields.Date(string='Consumption Date', default=fields.Date.context_today, required=True)
    billed = fields.Boolean(string='Billed', default=False, readonly=True)
    description = fields.Char(string='Remarks')
