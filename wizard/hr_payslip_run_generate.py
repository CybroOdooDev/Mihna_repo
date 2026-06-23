# -*- coding: utf-8 -*-
from odoo import fields, models

class HrPayslipRunGenerate(models.TransientModel):
    _inherit = 'hr.payslip.run.generate'

    journal_id = fields.Many2one(related='payslip_run_id.journal_id', string='Salary Journal', readonly=True)
