# -*- coding: utf-8 -*-
from odoo import models, fields


class HrWorkEntryType(models.Model):
    _inherit = 'hr.work.entry.type'

    is_paid = fields.Boolean(
        string='Is Paid',
        default=True,
        help="If unchecked, this worked day will not contribute to the paid amount in payroll."
    )
