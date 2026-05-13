# -*- coding: utf-8 -*-
from odoo import models, fields


class StockLocation(models.Model):
    """
    Extend stock.location
    """
    _inherit = 'stock.location'

    state_id = fields.Many2one('res.country.state', string='State')
    country_id = fields.Many2one('res.country', string='Country')