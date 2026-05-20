<<<<<<< HEAD
=======
<<<<<<< HEAD
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
# -*- coding: utf-8 -*-
from odoo import models, fields

class AccountMove(models.Model):
    """Inherited Account Move model to link invoices with active subscription contracts."""
<<<<<<< HEAD
=======
=======
from odoo import models, fields

class AccountMove(models.Model):
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
    _inherit = 'account.move'

    subscription_id = fields.Many2one('subscription.subscription', string='Subscription', readonly=True, copy=False)
