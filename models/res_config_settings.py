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
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests

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
        """Test the connection to the UltraMsg API using the provided credentials
        and confirm the configuration if successful."""
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
                    raise UserError(_("Failed to connect to WhatsApp Instance. Please verify your Instance ID, "
                                      "Token, and ensure your instance is active."))
                
                if response.status_code == 200:
                    # If request is successful and no error in JSON, transition to confirmed
                    record.state = 'confirmed'
                else:
                    raise UserError(_("Failed to verify credentials. HTTP Status: %s. Response: %s")
                                    % (response.status_code, response.text))
            except requests.exceptions.RequestException as e:
                raise UserError(_("Connection Error while reaching UltraMsg API: %s") % str(e))

    @api.model
    def get_config(self):
        """Retrieves and returns the active UltraMsg WhatsApp gateway settings record."""
        return self.search([('is_active', '=', True)], limit=1)
