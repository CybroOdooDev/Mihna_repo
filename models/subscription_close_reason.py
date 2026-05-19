<<<<<<< HEAD
# -*- coding: utf-8 -*-
from odoo import models, fields

class SubscriptionCloseReason(models.Model):
    """Subscription Close Reason model to log retention details, portal cancellation triggers, and survey messages."""
=======
from odoo import models, fields

class SubscriptionCloseReason(models.Model):
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
    _name = 'subscription.close.reason'
    _description = 'Subscription Close Reason'
    _order = 'sequence, id'

    name = fields.Char(string='Reason', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    visible_in_portal = fields.Boolean(string='Selectable in Portal', default=True)
    retention_message = fields.Text(string='Message', help="This message will be displayed to convince the customer to stay (e.g., We don't want you to leave, can we offer to schedule a meeting with your account manager?)")
    retention_button_text = fields.Char(string='Button Text', help="The text to display on the call to action")
    retention_button_link = fields.Char(string='Button Link', help="The redirect link of the call to action")
