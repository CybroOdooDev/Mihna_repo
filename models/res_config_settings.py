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
    is_active = fields.Boolean(string='Active', default=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed')
    ], string='Status', default='draft')

    def action_test_and_confirm(self):
        import requests
        from odoo.exceptions import UserError
        from odoo import _
        for record in self:
            if not record.instance_id or not record.token:
                raise UserError(_("Please provide both Instance ID and Token before confirming."))
            
            url = f"https://api.ultramsg.com/{record.instance_id}/instance/status?token={record.token}"
            try:
                response = requests.get(url, timeout=10)
                
                # Try to parse JSON response regardless of status code to catch explicit API errors
                try:
                    data = response.json()
                except ValueError:
                    data = {}
                    
                if isinstance(data, dict) and data.get('error'):
                    raise UserError(_("Failed to connect to WhatsApp Instance. Please verify your Instance ID, Token, and ensure your instance is active."))
                
                if response.status_code == 200:
                    # If request is successful and no error in JSON, transition to confirmed
                    record.state = 'confirmed'
                else:
                    raise UserError(_("Failed to verify credentials. HTTP Status: %s. Response: %s") % (response.status_code, response.text))
            except requests.exceptions.RequestException as e:
                raise UserError(_("Connection Error while reaching UltraMsg API: %s") % str(e))

    @api.model
    def get_config(self):
        """Retrieves and returns the active UltraMsg WhatsApp gateway settings record."""
        return self.search([('is_active', '=', True)], limit=1)
