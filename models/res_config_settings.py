from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    """
    Extend res.config.settings for delivery map configuration.
    """
    _inherit = 'res.config.settings'

    map_api_url = fields.Char(string='Map API URL',config_parameter='delivery_map.map_api_url')