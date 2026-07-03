# -*- coding: utf-8 -*-
#############################################################################
#    A part of Open HRMS Project <https://www.openhrms.com>
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2025-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrLoanLine(models.Model):
    """ Model for managing details of loan request installments"""
    _name = "hr.loan.line"
    _description = "Installment Line"

    date = fields.Date(string="Payment Date", required=True,
                       help="Date of the payment")
    employee_id = fields.Many2one('hr.employee', string="Employee",
                                  help="Employee")
    amount = fields.Float(string="Amount", required=True, help="Amount")
    paid = fields.Boolean(string="Paid", help="Indicates whether the "
                                              "installment has been paid.")
    loan_id = fields.Many2one('hr.loan', string="Loan Ref.",
                              help="Reference to the associated loan.")
    payslip_id = fields.Many2one('hr.payslip', string="Payslip Ref.",
                                 help="Reference to the associated "
                                      "payslip, if any.")

    @api.model_create_multi
    def create(self, vals_list):
        lines = super(HrLoanLine, self).create(vals_list)
        for line in lines:
            if line.loan_id.state == 'approve' and not self.env.context.get('early_settlement'):
                raise UserError(_("You cannot add installment lines to an approved loan."))
        return lines

    def write(self, vals):
        for line in self:
            if line.loan_id.state == 'approve' and not self.env.context.get('early_settlement'):
                # Allow updates to 'paid' and 'payslip_id' from payslip processing
                allowed_fields = {'paid', 'payslip_id'}
                if any(field not in allowed_fields for field in vals):
                    raise UserError(_("You cannot modify installment lines of an approved loan."))
        return super(HrLoanLine, self).write(vals)

    def unlink(self):
        for line in self:
            if line.loan_id.state == 'approve' and not self.env.context.get('early_settlement'):
                raise UserError(_("You cannot delete installment lines from an approved loan."))
        return super(HrLoanLine, self).unlink()
