# -*- coding: utf-8 -*-
#############################################################################
#    A part of Open HRMS Project <https://www.openhrms.com>
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2026-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
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
from odoo import api, fields, models


class DepartmentHistory(models.Model):
    """Model for tracking the historical changes in an employee's department
    or job position."""
    _name = 'department.history'
    _description = 'Department History'
    _rec_name = 'employee_name'

    employee = fields.Char(string='Employee ID',
                           help="ID of the associated Employee")
    employee_id = fields.Many2one('hr.employee', string='Employee Ref', compute='_compute_employee_id', store=True)
    employee_name = fields.Char(string='Employee Name',
                                help="Name of the employee whose department "
                                     "or job position has changed.")
    changed_field = fields.Char(string='Job position/Department',
                                help="Indicates the department or job position "
                                     "that was changed in the employee's "
                                     "record.")
    updated_date = fields.Date(string='Date',
                               help="Date on which department or job "
                                    "position changed")
    current_value = fields.Char(string='Designation',
                                help="Updated Designation")

    @api.depends('employee')
    def _compute_employee_id(self):
        """
        Compute the actual hr.employee record from the stored employee ID string.
        """
        for rec in self:
            if rec.employee and rec.employee.isdigit():
                rec.employee_id = int(rec.employee)
            else:
                rec.employee_id = False
