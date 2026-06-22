# -*- coding: utf-8 -*-
from odoo import models

class PayslipConfirm(models.TransientModel):
    """Create a new model for getting mass confirm wizard"""
    _name = 'payslip.confirm'
    _description = 'Mass Confirm Payslip'

    def confirm_payslip(self):
        """Mass Confirmation of Payslip"""
        context = self._context
        record_ids = context.get('active_ids', [])
        for each in record_ids:
            payslip_id = self.env['hr.payslip'].search([('id', '=', each),
                                                        ('state', 'not in',
                                                         ['cancel', 'done'])])
            if payslip_id:
                payslip_id.action_payslip_done()
