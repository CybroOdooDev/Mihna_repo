<<<<<<< HEAD
=======
<<<<<<< HEAD
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
# -*- coding: utf-8 -*-
from odoo import models, fields

class ProductTemplate(models.Model):
    """Inherited Product Template model to define if a product represents a recurring subscription plan."""
<<<<<<< HEAD
=======
=======
from odoo import models, fields

class ProductTemplate(models.Model):
>>>>>>> 3dc072b0baf4fdf36cb95d0de9a7ca7e99d431a0
>>>>>>> 6e137d94e21b733a141af3856f203ebc023ea986
    _inherit = 'product.template'

    recurring_ok = fields.Boolean(string='Subscription Product', default=False, help='Check if this product is a recurring subscription plan.')
    subscription_plan_id = fields.Many2one('subscription.plan', string='Subscription Plan', help='Plan used when selling this product.')
