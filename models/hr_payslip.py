# -*- coding: utf-8 -*-
#############################################################################
#   A part of Open HRMS Project <https://www.openhrms.com>
#
#    Cybrosys Technologies Pvt. Ltd.
#    Copyright (C) 2026-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Abhijith CK (<https://www.cybrosys.com>)
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
from odoo import api, models


class HrPayslip(models.Model):
    """Inherited to add fields"""
    _inherit = 'hr.payslip'

    @api.model
    def get_inputs(self, contract_ids, date_from, date_to):
        """used get inputs , to add datas"""
        res = super().get_inputs(contract_ids, date_from, date_to)
        contract_obj = self.env['hr.version']
        for contract in contract_ids:
            emp_id = contract_obj.browse(contract.id).employee_id if hasattr(contract, 'id') else contract_obj.browse(
                contract).employee_id

            eligible_insurances = emp_id.insurance_ids.filtered(
                lambda i: i.state == 'active' and not i.is_deducted and i.date_from <= date_to
            )
            total_deduction = sum(ins.deducted_amount for ins in eligible_insurances)

            if total_deduction != 0:
                insur_input = next((r for r in res if r.get('code') == 'INSUR'), None)
                if insur_input:
                    insur_input['amount'] = total_deduction
                else:
                    res.append({
                        'name': 'Insurance Amount',
                        'code': 'INSUR',
                        'amount': total_deduction,
                        'contract_id': contract.id if hasattr(contract, 'id') else contract,
                    })
        return res

    def action_payslip_done(self):
        """Override to mark the insurance as deducted once the payslip is done"""
        res = super(HrPayslip, self).action_payslip_done()
        for slip in self:
            if any(line.code == 'INSUR' for line in slip.line_ids):
                eligible_insurances = slip.employee_id.insurance_ids.filtered(
                    lambda i: i.state == 'active' and not i.is_deducted and i.date_from <= slip.date_to
                )
                for ins in eligible_insurances:
                    ins.is_deducted = True
        return res
