# -*- coding: utf-8 -*-
from odoo import models, fields

class SubscriptionWhatsappTemplate(models.Model):
    _name = 'subscription.whatsapp.template'
    _description = 'WhatsApp Template'

    name = fields.Char(string='Name', required=True)
    body = fields.Html(
        string='Body', 
        required=True, 
        help="Custom text template for WhatsApp. Available placeholders: {customer_name}, {subscription_name}, {invoice_amount}, {invoice_currency}, {status_label}"
    )
