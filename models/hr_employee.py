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

    def write(self, vals):
        """Record history for employee fields when they are changed and saved."""
        track_dict = {}
        for employee in self:
            c_type = getattr(employee, 'contract_type_id', False)
            track_dict[employee.id] = {
                'department_id': employee.department_id.id,
                'department_name': employee.department_id.name,
                'job_id': employee.job_id.id,
                'job_name': employee.job_id.name,
                'hourly_cost': employee.hourly_cost,
                'wage': getattr(employee, 'wage', False),
                'contract_date_start': getattr(employee, 'contract_date_start', False),
                'contract_date_end': getattr(employee, 'contract_date_end', False),
                'contract_type_id': c_type.id if c_type else False,
                'contract_type_name': c_type.name if c_type else False,
            }

        res = super(HrEmployee, self).write(vals)

        for employee in self:
            old_vals = track_dict[employee.id]
            
            if 'department_id' in vals and old_vals['department_id'] != employee.department_id.id:
                new_val = employee.department_id.name
                latest = self.env['department.history'].sudo().search([('employee_id', '=', employee.id), ('changed_field', '=', 'Department')], order='id desc', limit=1)
                if not latest or str(latest.current_value) != str(new_val):
                    if not latest and old_vals['department_name']:
                        self.env['department.history'].sudo().create({
                            'employee': str(employee.id),
                            'employee_name': employee.name,
                            'updated_date': employee.create_date or fields.Datetime.now(),
                            'changed_field': 'Department',
                            'current_value': old_vals['department_name']
                        })
                    self.env['department.history'].sudo().create({
                        'employee': str(employee.id),
                        'employee_name': employee.name,
                        'updated_date': fields.Datetime.now(),
                        'changed_field': 'Department',
                        'current_value': new_val
                    })
                
            if 'job_id' in vals and old_vals['job_id'] != employee.job_id.id:
                new_val = employee.job_id.name
                latest = self.env['department.history'].sudo().search([('employee_id', '=', employee.id), ('changed_field', '=', 'Job Position')], order='id desc', limit=1)
                if not latest or str(latest.current_value) != str(new_val):
                    if not latest and old_vals['job_name']:
                        self.env['department.history'].sudo().create({
                            'employee': str(employee.id),
                            'employee_name': employee.name,
                            'updated_date': employee.create_date or fields.Datetime.now(),
                            'changed_field': 'Job Position',
                            'current_value': old_vals['job_name']
                        })
                    self.env['department.history'].sudo().create({
                        'employee': str(employee.id),
                        'employee_name': employee.name,
                        'updated_date': fields.Date.today(),
                        'changed_field': 'Job Position',
                        'current_value': new_val
                    })
                
            if 'hourly_cost' in vals and old_vals['hourly_cost'] != employee.hourly_cost:
                new_val = employee.hourly_cost
                latest = self.env['hourly.cost'].sudo().search([('employee_id', '=', employee.id)], order='id desc', limit=1)
                if not latest or str(latest.current_value) != str(new_val):
                    if not latest and old_vals['hourly_cost']:
                        self.env['hourly.cost'].sudo().create({
                            'employee': str(employee.id),
                            'employee_name': employee.name,
                            'updated_date': employee.create_date or fields.Datetime.now(),
                            'current_value': str(old_vals['hourly_cost'])
                        })
                    self.env['hourly.cost'].sudo().create({
                        'employee': str(employee.id),
                        'employee_name': employee.name,
                        'updated_date': fields.Datetime.now(),
                        'current_value': str(new_val)
                    })
                
            if 'wage' in vals and old_vals['wage'] != getattr(employee, 'wage', False):
                new_val = getattr(employee, 'wage', False)
                latest = self.env['salary.history'].sudo().search([('employee_id', '=', employee.id)], order='id desc', limit=1)
                if not latest or str(latest.current_value) != str(new_val):
                    if not latest and old_vals['wage']:
                        self.env['salary.history'].sudo().create({
                            'employee': str(employee.id),
                            'employee_name': employee.name,
                            'updated_date': employee.create_date or fields.Datetime.now(),
                            'current_value': str(old_vals['wage'])
                        })
                    self.env['salary.history'].sudo().create({
                        'employee': str(employee.id),
                        'employee_name': employee.name,
                        'updated_date': fields.Datetime.now(),
                        'current_value': str(new_val),
                    })
                
            if 'contract_date_start' in vals and old_vals['contract_date_start'] != getattr(employee, 'contract_date_start', False):
                new_val = getattr(employee, 'contract_date_start', False)
                latest = self.env['contract.history'].sudo().search([('employee_id', '=', employee.id), ('changed_field', '=', 'Start Date')], order='id desc', limit=1)
                if not latest or str(latest.current_value) != str(new_val):
                    if not latest and old_vals['contract_date_start']:
                        self.env['contract.history'].sudo().create({
                            'employee': str(employee.id),
                            'employee_name': employee.name,
                            'updated_date': employee.create_date or fields.Datetime.now(),
                            'changed_field': 'Start Date',
                            'current_value': str(old_vals['contract_date_start'])
                        })
                    self.env['contract.history'].sudo().create({
                        'employee': str(employee.id),
                        'employee_name': employee.name,
                        'updated_date': fields.Date.today(),
                        'changed_field': 'Start Date',
                        'current_value': str(new_val),
                    })
                
            if 'contract_date_end' in vals and old_vals['contract_date_end'] != getattr(employee, 'contract_date_end', False):
                new_val = getattr(employee, 'contract_date_end', False)
                latest = self.env['contract.history'].sudo().search([('employee_id', '=', employee.id), ('changed_field', '=', 'End Date')], order='id desc', limit=1)
                if not latest or str(latest.current_value) != str(new_val):
                    if not latest and old_vals['contract_date_end']:
                        self.env['contract.history'].sudo().create({
                            'employee': str(employee.id),
                            'employee_name': employee.name,
                            'updated_date': employee.create_date or fields.Datetime.now(),
                            'changed_field': 'End Date',
                            'current_value': str(old_vals['contract_date_end'])
                        })
                    self.env['contract.history'].sudo().create({
                        'employee': str(employee.id),
                        'employee_name': employee.name,
                        'updated_date': fields.Date.today(),
                        'changed_field': 'End Date',
                        'current_value': str(new_val),
                    })
                
            if 'contract_type_id' in vals and old_vals['contract_type_id'] != (getattr(employee, 'contract_type_id', False).id if getattr(employee, 'contract_type_id', False) else False):
                ctype = getattr(employee, 'contract_type_id', False)
                new_val = ctype.name if ctype else False
                latest = self.env['contract.history'].sudo().search([('employee_id', '=', employee.id), ('changed_field', '=', 'Contract Type')], order='id desc', limit=1)
                if not latest or str(latest.current_value) != str(new_val):
                    if not latest and old_vals['contract_type_name']:
                        self.env['contract.history'].sudo().create({
                            'employee': str(employee.id),
                            'employee_name': employee.name,
                            'updated_date': employee.create_date or fields.Datetime.now(),
                            'changed_field': 'Contract Type',
                            'current_value': old_vals['contract_type_name']
                        })
                    self.env['contract.history'].sudo().create({
                        'employee': str(employee.id),
                        'employee_name': employee.name,
                        'updated_date': fields.Date.today(),
                        'changed_field': 'Contract Type',
                        'current_value': str(new_val) if new_val else False,
                    })

        return res

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
                # No previous value exists yet (first time this field is
                # ever set) - show a dash instead of the literal word "None".
                return str(val) if val else "—"

        def fmt_time(dt):
            if not dt:
                return ''
            return fields.Datetime.context_timestamp(self, dt).strftime('%I:%M %p')

        # 1. Salary History
        salaries = self.env['salary.history'].search([('employee_id', '=', employee_id)],
                                                     order='updated_date asc, id asc')
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
            subtitle_color = '#16a34a'
            subtitle_bg = '#dcfce7'
            if prev_salary_val is not None and prev_float > 0 and curr_float > 0:
                diff = curr_float - prev_float
                pct = (diff / prev_float) * 100
                sign = "+" if diff > 0 else ""
                subtitle = f"{sign}₹{diff:,.2f} ({sign}{pct:,.2f}%)"
                if diff < 0:
                    subtitle_color = '#dc2626'  # decrease: red
                    subtitle_bg = '#fee2e2'

            history_items.append({
                'id': f'salary_{s.id}',
                'record_id': s.id,
                'category': 'SALARY',
                'date': s.updated_date.strftime('%d %b %Y') if s.updated_date else '',
                'time': fmt_time(s.create_date),
                'sort_date': s.create_date,
                'title': f"{fmt_currency(prev_salary_val)} → {fmt_currency(s.current_value)}",
                'subtitle': subtitle,
                'subtitle_color': subtitle_color,
                'subtitle_bg': subtitle_bg,
                'author_name': s.create_uid.name if s.create_uid else 'System',
                'author_id': s.create_uid.id if s.create_uid else False,
                'icon': 'fa-dollar',
                'color': '#22c55e',  # Professional Green
                'light_color': '#dcfce7',  # Very light green
                'gradient': 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)',
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
            subtitle_color = '#16a34a'
            subtitle_bg = '#dcfce7'
            if prev_hourly_val is not None and prev_float > 0 and curr_float > 0:
                diff = curr_float - prev_float
                pct = (diff / prev_float) * 100
                sign = "+" if diff > 0 else ""
                subtitle = f"{sign}₹{diff:,.2f} ({sign}{pct:,.2f}%)"
                if diff < 0:
                    subtitle_color = '#dc2626'  # decrease: red
                    subtitle_bg = '#fee2e2'

            history_items.append({
                'id': f'hourly_{h.id}',
                'record_id': h.id,
                'category': 'HOURLY COST',
                'date': h.updated_date.strftime('%d %b %Y') if h.updated_date else '',
                'time': fmt_time(h.create_date),
                'sort_date': h.create_date,
                'title': f"{fmt_currency(prev_hourly_val)} → {fmt_currency(h.current_value)}",
                'subtitle': subtitle,
                'subtitle_color': subtitle_color,
                'subtitle_bg': subtitle_bg,
                'author_name': h.create_uid.name if h.create_uid else 'System',
                'author_id': h.create_uid.id if h.create_uid else False,
                'icon': 'fa-clock-o',
                'color': '#a855f7',  # Professional Purple
                'light_color': '#f3e8ff',  # Very light purple
                'gradient': 'linear-gradient(135deg, #a855f7 0%, #9333ea 100%)',
            })
            prev_hourly_val = h.current_value

        # 3. Contract History
        contracts = self.env['contract.history'].search([('employee_id', '=', employee_id)],
                                                        order='updated_date asc, id asc')
        contract_prevs = {}
        for c in contracts:
            field = c.changed_field or 'Contract'
            prev = contract_prevs.get(field, '—')
            history_items.append({
                'id': f'contract_{c.id}',
                'record_id': c.id,
                'category': 'CONTRACT',
                'date': c.updated_date.strftime('%d %b %Y') if c.updated_date else '',
                'time': fmt_time(c.create_date),
                'sort_date': c.create_date,
                'title': f"{prev} → {c.current_value}",
                'subtitle': "",
                'author_name': c.create_uid.name if c.create_uid else 'System',
                'author_id': c.create_uid.id if c.create_uid else False,
                'icon': 'fa-file-text-o',
                'color': '#f97316',  # Professional Orange
                'light_color': '#ffedd5',  # Very light orange
                'gradient': 'linear-gradient(135deg, #f97316 0%, #ea580c 100%)',
            })
            contract_prevs[field] = c.current_value

        # 4. Job / Department History
        deps = self.env['department.history'].search([('employee_id', '=', employee_id)],
                                                     order='updated_date asc, id asc')
        dep_prevs = {}
        for d in deps:
            field = d.changed_field or 'Job/Department'
            prev = dep_prevs.get(field, '—')
            history_items.append({
                'id': f'dep_{d.id}',
                'record_id': d.id,
                'category': 'JOB/DEPT',
                'date': d.updated_date.strftime('%d %b %Y') if d.updated_date else '',
                'time': fmt_time(d.create_date),
                'sort_date': d.create_date,
                'title': f"{prev} → {d.current_value}",
                'subtitle': "",
                'author_name': d.create_uid.name if d.create_uid else 'System',
                'author_id': d.create_uid.id if d.create_uid else False,
                'icon': 'fa-briefcase',
                'color': '#3b82f6',  # Professional Blue
                'light_color': '#dbeafe',  # Very light blue
                'gradient': 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
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
