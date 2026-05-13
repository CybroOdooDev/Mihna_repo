# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.exceptions import UserError
import requests


class DeliveryMapController(http.Controller):
    """
    Controller for fetching map coordinates
    """
    @http.route('/delivery_map/get_coordinates', type='json', auth='user')
    def get_coordinates(self, location,):
        """
        Fetch latitude and longitude from OpenStreetMap API.
        """
        url = request.env['ir.config_parameter'].sudo().get_param('delivery_map.map_api_url')
        if not url: raise UserError(
            _("Map API URL is not configured.\n\n" "Please configure it in:\n" "Settings → Delivery Map"))
        params = {
            'q': location,
            'format': 'json',
            'limit': 1,
        }
        headers = {'User-Agent': 'Odoo Delivery Map'}
        response = requests.get(url, params=params, headers=headers)
        data = response.json()
        if data:
            return {
                'lat': data[0]['lat'],
                'lon': data[0]['lon'],
            }
        return False