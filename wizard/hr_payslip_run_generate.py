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

class HrPayslipRunGenerate(models.TransientModel):
    _name = 'hr.payslip.run.generate'
    _description = 'Payslip Run Generation Wizard'

    struct_id = fields.Many2one('hr.payroll.structure', string='Salary Structure',
                                help='Select the Salary Structure to generate payslips for.')
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Payslip Batch')

    @api.model
    def default_get(self, fields):
        res = super(HrPayslipRunGenerate, self).default_get(fields)
        if self.env.context.get('active_id') and self.env.context.get('active_model') == 'hr.payslip.run':
            print(self.env.context.get('active_id'),"Dddddddddddddddddddd")
            res['payslip_run_id'] = self.env.context.get('active_id')
        return res

    def action_continue(self):
        """Proceed to the next wizard to select employees, passing the structure"""
        self.ensure_one()
        
        context = dict(self.env.context)
        if self.struct_id:
            context['default_struct_id'] = self.struct_id.id
        if self.payslip_run_id:
            context['active_id'] = self.payslip_run_id.id
            context['active_ids'] = [self.payslip_run_id.id]
            context['batch_run_id'] = self.payslip_run_id.id
        print(context,"contextcontextcontext")
        return {
            'name': _('Select Employees'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip.employees',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }
