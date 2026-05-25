# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SubscriptionWhatsAppConfig(models.Model):
    """Model storing WhatsApp integration settings for the UltraMsg gateway api.
    Holds the required Instance ID and Secret Token parameters and controls active state."""
    _name = 'subscription.whatsapp.config'
    _description = 'WhatsApp UltraMsg Configuration'

    name = fields.Char(string='Name', default='UltraMsg Configuration', required=True)
    instance_id = fields.Char(string='Instance ID', required=True, help="Your UltraMsg Instance ID (e.g., instance115242)")
    token = fields.Char(string='Token', required=True, help="Your UltraMsg Token")
    is_active = fields.Boolean(string='Active', default=True)

    @api.model
    def get_config(self):
        """Retrieves and returns the active UltraMsg WhatsApp gateway settings record."""
        return self.search([('is_active', '=', True)], limit=1)
