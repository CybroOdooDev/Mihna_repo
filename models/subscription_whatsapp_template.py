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

class SubscriptionWhatsappTemplate(models.Model):
    """Model to store custom WhatsApp message templates for subscription notifications."""
    _name = 'subscription.whatsapp.template'
    _description = 'WhatsApp Template'

    name = fields.Char(string='Name', required=True)
    body = fields.Html(
        string='Body', 
        required=True, 
        help="Custom text template for WhatsApp."
             " Available placeholders:"
             " {customer_name}, {subscription_name}, {invoice_amount}, {invoice_currency}, {status_label}"
    )
