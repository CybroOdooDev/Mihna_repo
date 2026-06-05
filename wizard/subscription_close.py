# -*- coding: utf-8 -*-
# ############################################################################
# #
# #    Cybrosys Technologies Pvt. Ltd.
# #
# #    Copyright (C) 2026-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
# #    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
# #
# #    You can modify it under the terms of the GNU LESSER
# #    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
# #
# ############################################################################

from odoo import models, fields

class SubscriptionClose(models.TransientModel):
    """Wizard allowing users to select a close reason before terminating a subscription."""

    _name = 'subscription.close'
    _description = 'Close Subscription Action'

    sale_order_id = fields.Many2one(
        'sale.order', string='Subscription (Sale Order)', required=True
    )
    close_reason_id = fields.Many2one(
        'subscription.close.reason', string='Close Reason', required=True
    )
    notes = fields.Text(string='Notes')

    def action_close(self):
        """Apply the selected close reason and permanently close the subscription."""
        self.ensure_one()
        self.sale_order_id._action_close_confirm(
            close_reason_id=self.close_reason_id.id if self.close_reason_id else None,
            notes=self.notes,
        )
        return {'type': 'ir.actions.act_window_close'}
