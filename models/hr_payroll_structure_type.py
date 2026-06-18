# -*- coding: utf-8 -*-
from odoo import fields, models


class HrPayrollStructureType(models.Model):
    _inherit = 'hr.payroll.structure.type'

    default_struct_id = fields.Many2one(
        'hr.payroll.structure',
        string="Pay Structure",
        help="Default structure for this pay category"
    )
