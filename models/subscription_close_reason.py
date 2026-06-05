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

class SubscriptionCloseReason(models.Model):
    """Subscription Close Reason model to log retention details, portal cancellation triggers, and survey messages."""
    _name = 'subscription.close.reason'
    _description = 'Subscription Close Reason'
    _order = 'sequence, id'

    name = fields.Char(string='Reason', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    visible_in_portal = fields.Boolean(string='Selectable in Portal', default=True)
    retention_message = fields.Text(string='Message', help="This message will be displayed to convince the customer to stay (e.g., We don't want you to leave, can we offer to schedule a meeting with your account manager?)")
    retention_button_text = fields.Char(string='Button Text', help="The text to display on the call to action")
    retention_button_link = fields.Char(string='Button Link', help="The redirect link of the call to action")
