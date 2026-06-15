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


class HrEmployee(models.Model):
    """Inherited the 'hr.employee' model to add onchange methods and actions to
    record changes in department, job position, hourly cost, and provides access
     to related historical data for HR employees."""
    _inherit = 'hr.employee'

    department_history_ids = fields.One2many('department.history', 'employee_id', string='Job/Department History')
    salary_history_ids = fields.One2many('salary.history', 'employee_id', string='Salary History')
    contract_history_ids = fields.One2many('contract.history', 'employee_id', string='Contract History')
    hourly_cost_history_ids = fields.One2many('hourly.cost', 'employee_id', string='Hourly Cost History')

    @api.onchange('department_id')
    def _onchange_department_id(self):
        """Create a record in 'department.history' when the 'department_id'
        field changes."""
        employee_id = self.env['hr.employee'].browse(self._origin.id)
        self.env['department.history'].sudo().create({
            'employee': self._origin.id,
            'employee_name': employee_id.name,
            'updated_date': fields.Datetime.now(),
            'changed_field': 'Department',
            'current_value': self.department_id.name
        })

    @api.onchange('job_id')
    def _onchange_job_id(self):
        """Create a record in 'department.history' when the 'job_id' field
        changes."""
        employee_id = self.env['hr.employee'].browse(self._origin.id)
        self.env['department.history'].sudo().create({
            'employee': self._origin.id,
            'employee_name': employee_id.name,
            'updated_date': fields.Date.today(),
            'changed_field': 'Job Position',
            'current_value': self.job_id.name
        })

    @api.onchange('hourly_cost')
    def _onchange_hourly_cost(self):
        """Create a record in 'hourly.cost' when the 'hourly_cost' field
        changes."""
        employee_id = self.env['hr.employee'].browse(self._origin.id)
        self.env['hourly.cost'].sudo().create({
            'employee': self._origin.id,
            'employee_name': employee_id.name,
            'updated_date': fields.Datetime.now(),
            'current_value': self.hourly_cost
        })

    @api.onchange('wage')
    def _onchange_employee_wage(self):
        """Create a record in 'salary.history' when the 'wage' field changes."""
        self.env['salary.history'].sudo().create([{
            'employee': self.employee_id.id,
            'employee_name': self.employee_id,
            'updated_date': fields.Datetime.now(),
            'current_value': self.wage,
        }])

    @api.onchange('contract_date_start')
    def _onchange_contract_date_start(self):
        """Create a record in 'contract.history' when the 'date_start' field
        changes."""
        self.env['contract.history'].create([{
            'employee': self.employee_id.id,
            'employee_name': self.employee_id,
            'updated_date': fields.Date.today(),
            'changed_field': 'Start Date',
            'current_value': self.date_start,
        }])

    @api.onchange('contract_date_end')
    def _onchange_contract_date_end(self):
        """Create a record in 'contract.history' when the 'date_end' field
        changes."""
        self.env['contract.history'].create([{
            'employee': self.employee_id.id,
            'employee_name': self.employee_id,
            'updated_date': fields.Date.today(),
            'changed_field': 'End Date',
            'current_value': self.date_end,
        }])

    @api.onchange('contract_type_id')
    def _onchange_contract_type_id(self):
        """Create a record in 'contract.history' when the 'contract_type_id' field
        changes."""
    @api.model
    def get_employee_history_timeline(self, employee_id):
        """Aggregate history from all 4 models and compute old -> new values."""
        history_items = []
        
        # Helper to format currency
        def fmt_currency(val):
            try:
                fval = float(val)
                return f"₹{fval:,.2f}"
            except (ValueError, TypeError):
                return str(val) if val else "None"

        # 1. Salary History
        salaries = self.env['salary.history'].search([('employee_id', '=', employee_id)], order='updated_date asc, id asc')
        prev_salary_val = None
        for s in salaries:
            curr_val = s.current_value
            curr_float = 0.0
            prev_float = 0.0
            try:
                curr_float = float(curr_val)
                if prev_salary_val is not None:
                    prev_float = float(prev_salary_val)
            except ValueError:
                pass
                
            subtitle = ""
            if prev_salary_val is not None and prev_float > 0 and curr_float > 0:
                diff = curr_float - prev_float
                pct = (diff / prev_float) * 100
                sign = "+" if diff > 0 else ""
                subtitle = f"{sign}₹{diff:,.2f} ({sign}{pct:,.2f}%)"

            history_items.append({
                'id': f'salary_{s.id}',
                'record_id': s.id,
                'category': 'SALARY',
                'date': s.updated_date.strftime('%d %b %Y') if s.updated_date else '',
                'time': s.create_date.strftime('%I:%M %p') if s.create_date else '',
                'sort_date': s.updated_date,
                'title': f"{fmt_currency(prev_salary_val)} → {fmt_currency(s.current_value)}",
                'subtitle': subtitle,
                'author_name': s.create_uid.name if s.create_uid else 'System',
                'author_id': s.create_uid.id if s.create_uid else False,
                'icon': 'fa-dollar',
                'color': '#10b981', # Bright Emerald Green
                'light_color': '#dcfce7', # Visible light green
            })
            prev_salary_val = s.current_value

        # 2. Hourly Cost
        hourlys = self.env['hourly.cost'].search([('employee_id', '=', employee_id)], order='updated_date asc, id asc')
        prev_hourly_val = None
        for h in hourlys:
            curr_val = h.current_value
            curr_float = 0.0
            prev_float = 0.0
            try:
                curr_float = float(curr_val)
                if prev_hourly_val is not None:
                    prev_float = float(prev_hourly_val)
            except ValueError:
                pass
                
            subtitle = ""
            if prev_hourly_val is not None and prev_float > 0 and curr_float > 0:
                diff = curr_float - prev_float
                pct = (diff / prev_float) * 100
                sign = "+" if diff > 0 else ""
                subtitle = f"{sign}₹{diff:,.2f} ({sign}{pct:,.2f}%)"

            history_items.append({
                'id': f'hourly_{h.id}',
                'record_id': h.id,
                'category': 'HOURLY COST',
                'date': h.updated_date.strftime('%d %b %Y') if h.updated_date else '',
                'time': h.create_date.strftime('%I:%M %p') if h.create_date else '',
                'sort_date': h.updated_date,
                'title': f"{fmt_currency(prev_hourly_val)} → {fmt_currency(h.current_value)}",
                'subtitle': subtitle,
                'author_name': h.create_uid.name if h.create_uid else 'System',
                'author_id': h.create_uid.id if h.create_uid else False,
                'icon': 'fa-clock-o',
                'color': '#8b5cf6', # Bright Purple
                'light_color': '#ede9fe', # Visible light purple
            })
            prev_hourly_val = h.current_value

        # 3. Contract History
        contracts = self.env['contract.history'].search([('employee_id', '=', employee_id)], order='updated_date asc, id asc')
        contract_prevs = {}
        for c in contracts:
            field = c.changed_field or 'Contract'
            prev = contract_prevs.get(field, 'None')
            history_items.append({
                'id': f'contract_{c.id}',
                'record_id': c.id,
                'category': 'CONTRACT',
                'date': c.updated_date.strftime('%d %b %Y') if c.updated_date else '',
                'time': c.create_date.strftime('%I:%M %p') if c.create_date else '',
                'sort_date': c.updated_date,
                'title': f"{prev} → {c.current_value}",
                'subtitle': "",
                'author_name': c.create_uid.name if c.create_uid else 'System',
                'author_id': c.create_uid.id if c.create_uid else False,
                'icon': 'fa-file-text-o',
                'color': '#f97316', # Bright Orange
                'light_color': '#ffedd5', # Visible light orange
            })
            contract_prevs[field] = c.current_value

        # 4. Job / Department History
        deps = self.env['department.history'].search([('employee_id', '=', employee_id)], order='updated_date asc, id asc')
        dep_prevs = {}
        for d in deps:
            field = d.changed_field or 'Job/Department'
            prev = dep_prevs.get(field, 'None')
            history_items.append({
                'id': f'dep_{d.id}',
                'record_id': d.id,
                'category': 'JOB / DEPARTMENT',
                'date': d.updated_date.strftime('%d %b %Y') if d.updated_date else '',
                'time': d.create_date.strftime('%I:%M %p') if d.create_date else '',
                'sort_date': d.updated_date,
                'title': f"{prev} → {d.current_value}",
                'subtitle': "",
                'author_name': d.create_uid.name if d.create_uid else 'System',
                'author_id': d.create_uid.id if d.create_uid else False,
                'icon': 'fa-briefcase',
                'color': '#3b82f6', # Bright Blue
                'light_color': '#dbeafe', # Visible light blue
            })
            dep_prevs[field] = d.current_value

        # Sort combined history items by date descending, then ID descending
        # Ensure sort_date is a comparable type
        def get_sort_key(item):
            d = item['sort_date']
            from datetime import datetime, date
            if isinstance(d, datetime):
                dt = d
            elif isinstance(d, date):
                dt = datetime(d.year, d.month, d.day)
            else:
                dt = datetime.min
            return (dt, item.get('record_id', 0))

        history_items.sort(key=get_sort_key, reverse=True)
        
        # Remove sort_date before sending to frontend as it's not JSON serializable if date/datetime object
        for item in history_items:
            del item['sort_date']

        return history_items


