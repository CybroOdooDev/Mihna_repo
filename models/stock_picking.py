# -*- coding: utf-8 -*-
from odoo import models, fields


class StockPicking(models.Model):
    """
    Extend stock.picking model for delivery map
    Used For: Displaying source and destination location in delivery map.
    """
    _inherit = 'stock.picking'

    source_location = fields.Text(string='Source Location', compute='_compute_source_location')
    destination_location = fields.Text(string='Destination Location', compute='_compute_destination_location')

    # def _compute_source_location(self):
    #     """
    #     Compute source location from stock location
    #     """
    #     for rec in self:
    #         rec.source_location = (rec.location_id.full_address or '')

    def _compute_source_location(self):
        """ Compute source location from stock location state and country. """

        for rec in self:
            location = rec.location_id
            address = []
            if location.state_id:
                address.append(location.state_id.name)
            if location.country_id:
                address.append(location.country_id.name)
            rec.source_location = ', '.join(address)

    def _compute_destination_location(self):
        """
        Compute destination location from customer address
        """
        for rec in self:
            partner = rec.partner_id
            address = []
            if partner.city:
                address.append(partner.city)
            if partner.country_id:
                address.append(partner.country_id.name)
            rec.destination_location = ', '.join(address)

