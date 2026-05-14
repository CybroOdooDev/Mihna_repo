# -*- coding: utf-8 -*-
from odoo import fields, models


class PosConfig(models.Model):
    """
    Extends POS configuration to define the allowed refund return period.
    """
    _inherit = 'pos.config'

    return_period = fields.Integer(
        string="Return Period (Days)",
        default=0,
        help="Number of days the order can be refunded. 0 means no limit."
    )


class ResConfigSettings(models.TransientModel):
    """
    Extends POS settings to manage the refund return period.
    """
    _inherit = 'res.config.settings'

    pos_return_period = fields.Integer(
        related='pos_config_id.return_period',
        readonly=False,
        string="Return Period",
        help="Number of days the order can be refunded."
    )
