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

from odoo import models, fields, _
from markupsafe import Markup

class SubscriptionChangePlan(models.TransientModel):
    """Wizard for changing the subscription plan on an active contract."""

    _name = 'subscription.change.plan'
    _description = 'Change Subscription Plan Action'

    sale_order_id = fields.Many2one(
        'sale.order', string='Subscription (Sale Order)', required=True
    )
    plan_id = fields.Many2one(
        'subscription.plan', string='New Plan', required=True
    )

    def action_change_plan(self):
        """Update the subscription's plan and post a chatter message with the change."""
        self.ensure_one()
        self.sale_order_id.write({'plan_id': self.plan_id.id})
        self.sale_order_id.message_post(
            body=Markup(_('Subscription plan changed to <b>%s</b>.')) % self.plan_id.name
        )
        return {'type': 'ir.actions.act_window_close'}
