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

class SaleOrderTemplate(models.Model):
    """Inherited Sale Order Template model to embed subscription recurring billing structures into default quote presets."""
    _inherit = 'sale.order.template'
    _description = 'Sale Order Template'

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
    quote_calculator = fields.Char(string='Quote Calculator')
    is_shared = fields.Boolean(string='Share', default=True)
    sales_team_id = fields.Many2one('crm.team', string='Sales Team')
