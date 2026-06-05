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

class ResPartner(models.Model):
    """Inherited Res Partner model to link and calculate customer subscription contracts."""
    _inherit = 'res.partner'
    _description = 'Res Partner'

    subscription_ids = fields.One2many('sale.order', 'partner_id', string='Subscriptions',
                                       domain=[('subscription_state', 'in', ['1_draft', '2_renewal', '3_progress', '4_paused', '5_renewed', '6_churn', '7_upsell', '8_blocked'])])
    subscription_count = fields.Integer(string='Subscription Count', compute='_compute_subscription_count')

    def _compute_subscription_count(self):
        """Compute the total count of active subscription contracts for this customer."""
        for partner in self:
            partner.subscription_count = self.env['sale.order'].search_count([
                ('partner_id', '=', partner.id),
                ('subscription_state', 'in', ['3_progress', '4_paused', '1_draft', '2_renewal', '8_blocked']),
            ])

