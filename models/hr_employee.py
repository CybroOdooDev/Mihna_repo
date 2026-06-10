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
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the1`
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
import pandas as pd
from collections import defaultdict
from datetime import timedelta, datetime, date
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.http import request
from odoo.tools import float_utils
from odoo.tools import format_duration
from pytz import utc

ROUNDING_FACTOR = 16


class HrEmployee(models.Model):
    """ Inherit hr_employee to add birthday field and custom methods. """
    _inherit = 'hr.employee'

    birthday = fields.Date(string='Date of Birth', groups="base.group_user",
                           help="Birthday of employee")

    def attendance_manual(self):
        """Create and update an attendance for the user employee"""
        employee = request.env['hr.employee'].sudo().browse(
            self.env.user.employee_id.id)
        latitude = request.geoip.location.latitude
        longitude = request.geoip.location.longitude
        if latitude and longitude:
            geo_obj = request.env['base.geocoder']
            location_request = geo_obj._call_openstreetmap_reverse(latitude, longitude)
            if location_request and location_request.get('display_name'):
                location = location_request.get('display_name')
            else:
                location = _('Unknown')
        else:
            city = request.geoip.city.name
            country = request.geoip.country.name
            if city and country:
                location = f"{city}, {country}"
            else:
                location = _('Unknown')
        employee.sudo()._attendance_action_change({
            'location': location,
            'latitude': request.geoip.location.latitude or False,
            'longitude': request.geoip.location.longitude or False,
            'ip_address': request.geoip.ip,
            'browser': request.httprequest.user_agent.browser,
            'mode': 'kiosk'
        })
        return employee

    @api.model
    def check_user_group(self):
        """To check the user is a hr manager or not"""
        uid = request.session.uid
        user = self.env['res.users'].sudo().search([('id', '=', uid)], limit=1)
        if user.has_group('hr.group_hr_manager'):
            return True
        else:
            return False

    @api.model
    def get_user_employee_details(self, date_from=None, date_to=None):
        """To fetch the details of employee"""
        uid = request.session.uid
        employee = self.env['hr.employee'].sudo().search_read(
            [('user_id', '=', uid)], limit=1)
        
        attendance_domain = [('employee_id', '=', employee[0]['id'])]
        if date_from: attendance_domain.append(('check_in', '>=', date_from))
        if date_to: attendance_domain.append(('check_in', '<=', date_to + ' 23:59:59'))
        attendance = self.env['hr.attendance'].sudo().search_read(
            attendance_domain,
            fields=['id', 'check_in', 'check_out', 'worked_hours'])
        attendance_line = []
        for line in attendance:
            if line['check_in'] and line['check_out']:
                val = {
                    'id':line['id'],
                    'date': line['check_in'].date(),
                    'sign_in': line['check_in'].time().strftime('%H:%M'),
                    'sign_out': line['check_out'].time().strftime('%H:%M'),
                    'worked_hours': format_duration(line['worked_hours'])
                }
                attendance_line.append(val)
        leave_domain = [('employee_id', '=', employee[0]['id'])]
        if date_from: leave_domain.append(('request_date_from', '>=', date_from))
        if date_to: leave_domain.append(('request_date_from', '<=', date_to))
        leaves = self.env['hr.leave'].sudo().search_read(
            leave_domain,
            fields=['request_date_from', 'request_date_to', 'state',
                    'holiday_status_id'])
        for line in leaves:
            line['type'] = line.pop('holiday_status_id')[1]
            if line['state'] == 'confirm':
                line['state'] = 'To Approve'
                line['color'] = 'orange'
            elif line['state'] == 'validate1':
                line['state'] = 'Second Approval'
                line['color'] = '#7CFC00'
            elif line['state'] == 'validate':
                line['state'] = 'Approved'
                line['color'] = 'green'
            elif line['state'] == 'cancel':
                line['state'] = 'Cancelled'
                line['color'] = 'red'
            else:
                line['state'] = 'Refused'
                line['color'] = 'red'
        expense_domain = [('employee_id', '=', employee[0]['id'])]
        if date_from: expense_domain.append(('date', '>=', date_from))
        if date_to: expense_domain.append(('date', '<=', date_to))
        expense = self.env['hr.expense'].sudo().search_read(
            expense_domain,
            fields=['name', 'date', 'state', 'total_amount'])
        for line in expense:
            if line['state'] == 'draft':
                line['state'] = 'To Report'
                line['color'] = '#17A2B8'
            elif line['state'] == 'reported':
                line['state'] = 'To Submit'
                line['color'] = '#17A2B8'
            elif line['state'] == 'submitted':
                line['state'] = 'Submitted'
                line['color'] = '#FFAC00'
            elif line['state'] == 'approved':
                line['state'] = 'Approved'
                line['color'] = '#28A745'
            elif line['state'] == 'done':
                line['state'] = 'Done'
                line['color'] = '#28A745'
            else:
                line['state'] = 'Refused'
                line['color'] = 'red'
        lta_domain = [('state', 'in', ['confirm', 'validate1'])]
        if date_from: lta_domain.append(('request_date_from', '>=', date_from))
        if date_to: lta_domain.append(('request_date_from', '<=', date_to))
        leaves_to_approve = self.env['hr.leave'].sudo().search_count(lta_domain)
        today = datetime.strftime(datetime.today(), '%Y-%m-%d')
        query = """
        select count(id)
        from hr_leave
        WHERE (hr_leave.date_from::DATE,hr_leave.date_to::DATE) 
        OVERLAPS ('%s', '%s') and
        state='validate'""" % (today, today)
        cr = self._cr
        cr.execute(query)
        leaves_today = cr.fetchall()
        first_day = date.today().replace(day=1)
        last_day = (date.today() + relativedelta(months=1, day=1)) - timedelta(
            1)
        query = """
                select count(id)
                from hr_leave
                WHERE (hr_leave.date_from::DATE,hr_leave.date_to::DATE) 
                OVERLAPS ('%s', '%s')
                and  state='validate'""" % (first_day, last_day)
        cr = self._cr
        cr.execute(query)
        leaves_this_month = cr.fetchall()
        alloc_domain = [('state', 'in', ['confirm', 'validate1'])]
        if date_from: alloc_domain.append(('create_date', '>=', date_from))
        if date_to: alloc_domain.append(('create_date', '<=', date_to + ' 23:59:59'))
        leaves_alloc_req = self.env['hr.leave.allocation'].sudo().search_count(alloc_domain)
        ts_domain = [('project_id', '!=', False), ('user_id', '=', uid)]
        if date_from: ts_domain.append(('date', '>=', date_from))
        if date_to: ts_domain.append(('date', '<=', date_to))
        timesheet_count = self.env['account.analytic.line'].sudo().search_count(ts_domain)
        contract_domain = [('employee_id', '=', employee[0]['id'])]
        if date_from: contract_domain.append(('date_start', '>=', date_from))
        if date_to: contract_domain.append(('date_start', '<=', date_to))
        contract_count = self.env['hr.version'].sudo().search_count(contract_domain)
        timesheet_view_id = self.env.ref(
            'hr_timesheet.hr_timesheet_line_search')
        job_domain = []
        if date_from: job_domain.append(('create_date', '>=', date_from))
        if date_to: job_domain.append(('create_date', '<=', date_to + ' 23:59:59'))
        job_applications = self.env['hr.applicant'].sudo().search_count(job_domain)
        if employee:
            sql = """select broad_factor from hr_employee_broad_factor 
            where id =%s"""
            self.env.cr.execute(sql, (employee[0]['id'],))
            result = self.env.cr.dictfetchall()
            broad_factor = result[0]['broad_factor'] if result[0][
                'broad_factor'] else False
            if employee[0]['birthday']:
                diff = relativedelta(datetime.today(), employee[0]['birthday'])
                age = diff.years
            else:
                age = False
            if employee[0]['joining_date']:
                experience = employee[0]['joining_date'].strftime('%b %Y')
            else:
                experience = False
            if employee:
                data = {
                    'broad_factor': broad_factor if broad_factor else 0,
                    'leaves_to_approve': leaves_to_approve,
                    'leaves_today': leaves_today,
                    'leaves_this_month': leaves_this_month,
                    'leaves_alloc_req': leaves_alloc_req,
                    'emp_timesheets': timesheet_count,
                    'contracts_count': contract_count,
                    'job_applications': job_applications,
                    'timesheet_view_id': timesheet_view_id,
                    'experience': experience,
                    'age': age,
                    'attendance_lines': attendance_line,
                    'leave_lines': leaves,
                    'expense_lines': expense
                }
                employee[0].update(data)
            return employee
        else:
            return False

    @api.model
    def get_upcoming(self, date_from=None, date_to=None):
        """It returns upcoming events, announcements and birthday"""
        cr = self._cr
        uid = request.session.uid
        employee = self.env['hr.employee'].sudo().search([('user_id', '=', uid)],
                                                  limit=1)
        today = fields.Date.today()
        birthday_employees = self.env['hr.employee'].sudo().search_read(
            [('birthday', '!=', False)], fields=['id', 'name', 'birthday', 'department_id'], order='birthday ASC')

        filtered_birthdays = []
        for emp in birthday_employees:
            if emp['birthday'].month == today.month and emp['birthday'].day == today.day:
                emp['is_birthday'] = True
                emp['days'] = 0
            else:
                emp_birthday = emp['birthday'].replace(year=today.year)
                # If birthday already passed this year, next one is next year
                if emp_birthday < today:
                    emp_birthday = emp_birthday.replace(year=today.year + 1)
                emp['days'] = (emp_birthday - today).days
                emp['is_birthday'] = False
                
            # Filter by date_range
            if date_from and date_to:
                try:
                    df = fields.Date.from_string(date_from)
                    dt = fields.Date.from_string(date_to)
                    emp_birthday_current_year = emp['birthday'].replace(year=df.year)
                    if emp_birthday_current_year < df:
                        emp_birthday_current_year = emp_birthday_current_year.replace(year=df.year + 1)
                    if df <= emp_birthday_current_year <= dt:
                        filtered_birthdays.append(emp)
                except Exception:
                    pass
            else:
                filtered_birthdays.append(emp)
                
        # Sort by days ascending and limit to 4
        filtered_birthdays.sort(key=lambda x: x['days'])
        birthday_employees = filtered_birthdays[:4]
                
        ann_domain = [('state', '=', 'approved')]
        if date_from: ann_domain.append(('date_start', '>=', date_from))
        if date_to: ann_domain.append(('date_start', '<=', date_to))
        else: ann_domain.append(('date_start', '<=', fields.Date.today()))
        
        ann_domain.extend([
             '|', ('is_announcement', '=', True),
             '|', '|',
             ('employee_ids', 'in', employee.id),
             ('department_ids', 'in', employee.department_id.id),
             ('position_ids', 'in', employee.job_id.id),
        ])
        announcements = self.env['hr.announcement'].search_read(
            ann_domain, fields=['announcement_reason', 'date_start', 'date_end'])

        event_domain = [
            ('date_begin', '>=', date_from if date_from else fields.Datetime.now()),
            ('date_begin', '<=', date_to + ' 23:59:59' if date_to else '2099-12-31')
        ]
        events = self.env['event.event'].search_read(
            domain=event_domain,
            fields=['id','name', 'date_begin', 'date_end', 'address_id'],
            order='date_begin'
        )

        return {
            'birthday': birthday_employees,
            'event': events,
            'announcement': announcements
        }

    @api.model
    def get_open_hrms_requests(self, date_from=None, date_to=None):
        """Fetch counts of open/pending requests across OpenHRMS modules."""
        result = {
            'loan': 0,
            'salary_advance': 0,
            'resignation': 0,
            'transfer': 0,
            'shift': 0,
            'custody': 0
        }
        
        def _get_domain(base_domain):
            d = list(base_domain)
            if date_from: d.append(('create_date', '>=', date_from))
            if date_to: d.append(('create_date', '<=', date_to + ' 23:59:59'))
            return d
            
        if 'hr.loan' in self.env and self.env['hr.loan'].check_access_rights('read', raise_exception=False):
            result['loan'] = self.env['hr.loan'].search_count(_get_domain([('state', 'in', ['draft', 'waiting_approval_1'])]))
        else:
            result['loan'] = False
            
        if 'salary.advance' in self.env and self.env['salary.advance'].check_access_rights('read', raise_exception=False):
            result['salary_advance'] = self.env['salary.advance'].search_count(_get_domain([('state', 'in', ['draft', 'submit', 'waiting_approval'])]))
        else:
            result['salary_advance'] = False
            
        if 'hr.resignation' in self.env and self.env['hr.resignation'].check_access_rights('read', raise_exception=False):
            result['resignation'] = self.env['hr.resignation'].search_count(_get_domain([('state', 'in', ['draft', 'confirm'])]))
        else:
            result['resignation'] = False
            
        if 'employee.transfer' in self.env and self.env['employee.transfer'].check_access_rights('read', raise_exception=False):
            result['transfer'] = self.env['employee.transfer'].search_count(_get_domain([('state', '=', 'draft')]))
        else:
            result['transfer'] = False
            
        if 'service.request' in self.env and self.env['service.request'].check_access_rights('read', raise_exception=False):
            result['shift'] = self.env['service.request'].search_count(_get_domain([('state', '=', 'draft')]))
        else:
            result['shift'] = False
            
        return result

    @api.model
    def get_dept_employee(self, date_from=None, date_to=None):
        """Retrieve the details of employees in each department."""
        cr = self._cr
        cr.execute(""" SELECT e.department_id, d.name, COUNT(e.id)
    FROM hr_employee_public e
    JOIN hr_department d ON d.id = e.department_id
    GROUP BY e.department_id, d.name""")
        dat = cr.fetchall()
        data = []
        for i in range(0, len(dat)):
            data.append(
                {'label': list(dat[i][1].values())[0], 'value': dat[i][2]})
        return data

    @api.model
    def get_monthly_leave_status_trend(self, date_from=None, date_to=None):
        """Returns monthly leave trend categorized by Approved, Pending, Rejected"""
        user = self.env.user
        if not user.has_group('hr.group_hr_manager'):
            return []
            
        month_list = []
        for i in range(5, -1, -1):
            last_month = datetime.now() - relativedelta(months=i)
            text = format(last_month, '%b %Y') # e.g. Jun 2026
            month_list.append(text)
            
        where_clause = "state in ('validate', 'confirm', 'validate1', 'refuse')"
        
        sql = f"""
        SELECT h.id, h.employee_id, h.state
             , to_char(y, 'FMMon YYYY') as month_year
             , GREATEST(y                    , h.date_from) AS date_from
             , LEAST   (y + interval '1 month', h.date_to)   AS date_to
        FROM  (select * from hr_leave where {where_clause}) h
             , generate_series(date_trunc('month', date_from::timestamp)
                             , date_trunc('month', date_to::timestamp)
                             , interval '1 month') y
        where date_trunc('month', GREATEST(y , h.date_from)) >= 
        date_trunc('month', now()) - interval '6 month' and
        date_trunc('month', GREATEST(y , h.date_from)) <= 
        date_trunc('month', now())
        """
        self.env.cr.execute(sql)
        results = self.env.cr.dictfetchall()
        
        trend = {m: {'Approved': 0, 'Pending': 0, 'Rejected': 0} for m in month_list}
        
        for line in results:
            employee = self.browse(line['employee_id'])
            from_dt = fields.Datetime.from_string(line['date_from'])
            to_dt = fields.Datetime.from_string(line['date_to'])
            days = employee.get_work_days_dashboard(from_dt, to_dt)
            
            m_year = line['month_year'].strip()
            if m_year in trend:
                state = line['state']
                if state == 'validate':
                    trend[m_year]['Approved'] += days
                elif state in ('confirm', 'validate1'):
                    trend[m_year]['Pending'] += days
                elif state == 'refuse':
                    trend[m_year]['Rejected'] += days
                    
        result_list = []
        for m in month_list:
            result_list.append({
                'l_month': m,
                'Approved': trend[m]['Approved'],
                'Pending': trend[m]['Pending'],
                'Rejected': trend[m]['Rejected']
            })
            
        return result_list

    @api.model
    def get_department_leave(self, date_from=None, date_to=None):
        """Returns the department monthly wise leave information"""
        user = self.env.user
        if not user.has_group('hr.group_hr_manager'):
            return [], []
        month_list = []
        graph_result = []
        for i in range(5, -1, -1):
            last_month = datetime.now() - relativedelta(months=i)
            text = format(last_month, '%B %Y')
            month_list.append(text)
        self.env.cr.execute(
            """select id, name from hr_department where active=True """)
        departments = self.env.cr.dictfetchall()
        department_list = [list(x['name'].values())[0] for x in departments]
        for month in month_list:
            leave = {}
            for dept in departments:
                leave[list(dept['name'].values())[0]] = 0
            vals = {
                'l_month': month,
                'leave': leave
            }
            graph_result.append(vals)
            
        where_clause = "state = 'validate'"
        if date_from:
            where_clause += f" and request_date_from >= '{date_from}'"
        if date_to:
            where_clause += f" and request_date_from <= '{date_to}'"
            
        sql = f"""
        SELECT h.id, h.employee_id,h.department_id
             , extract('month' FROM y)::int AS leave_month
             , to_char(y, 'Month YYYY') as month_year
             , GREATEST(y                    , h.date_from) AS date_from
             , LEAST   (y + interval '1 month', h.date_to)   AS date_to
        FROM  (select * from hr_leave where {where_clause}) h
             , generate_series(date_trunc('month', date_from::timestamp)
                             , date_trunc('month', date_to::timestamp)
                             , interval '1 month') y
        where date_trunc('month', GREATEST(y , h.date_from)) >= 
        date_trunc('month', now()) - interval '6 month' and
        date_trunc('month', GREATEST(y , h.date_from)) <= 
        date_trunc('month', now())
        and h.department_id is not null
        """
        self.env.cr.execute(sql)
        results = self.env.cr.dictfetchall()
        leave_lines = []
        for line in results:
            employee = self.browse(line['employee_id'])
            from_dt = fields.Datetime.from_string(line['date_from'])
            to_dt = fields.Datetime.from_string(line['date_to'])
            days = employee.get_work_days_dashboard(from_dt, to_dt)
            line['days'] = days
            vals = {
                'department': line['department_id'],
                'l_month': line['month_year'],
                'days': days
            }
            leave_lines.append(vals)
        if leave_lines:
            df = pd.DataFrame(leave_lines)
            rf = df.groupby(['l_month', 'department']).sum()
            result_lines = rf.to_dict('index')
            for month in month_list:
                for line in result_lines:
                    if month.replace(' ', '') == line[0].replace(' ', ''):
                        match = list(filter(lambda d: d['l_month'] in [month],
                                            graph_result))[0]['leave']
                        dept_name = self.env['hr.department'].browse(
                            line[1]).name
                        if match:
                            match[dept_name] = result_lines[line]['days']
        for result in graph_result:
            result['l_month'] = result['l_month'].split(' ')[:1][0].strip()[
                                :3] + " " + \
                                result['l_month'].split(' ')[1:2][0]

        return graph_result, department_list

    def get_work_days_dashboard(self, from_datetime, to_datetime,
                                compute_leaves=False, calendar=None,
                                domain=None):
        """Calculate employee worked hours/day details"""
        resource = self.resource_id
        calendar = calendar or self.resource_calendar_id
        if not from_datetime.tzinfo:
            from_datetime = from_datetime.replace(tzinfo=utc)
        if not to_datetime.tzinfo:
            to_datetime = to_datetime.replace(tzinfo=utc)
        from_full = from_datetime - timedelta(days=1)
        to_full = to_datetime + timedelta(days=1)
        intervals = calendar._attendance_intervals_batch(from_full, to_full,
                                                         resource)
        day_total = defaultdict(float)
        for start, stop, meta in intervals[resource.id]:
            day_total[start.date()] += (stop - start).total_seconds() / 3600
        if compute_leaves:
            intervals = calendar._work_intervals_batch(from_datetime,
                                                       to_datetime, resource,
                                                       domain)
        else:
            intervals = calendar._attendance_intervals_batch(from_datetime,
                                                             to_datetime,
                                                             resource)
        day_hours = defaultdict(float)
        for start, stop, meta in intervals[resource.id]:
            day_hours[start.date()] += (stop - start).total_seconds() / 3600
        days = sum(
            float_utils.round(ROUNDING_FACTOR * day_hours[day] / day_total[
                day]) / ROUNDING_FACTOR
            for day in day_hours
        )
        return days

    @api.model
    def employee_leave_trend(self, date_from=None, date_to=None):
        """Logged employee monthly wise leave information"""
        leave_lines = []
        month_list = []
        graph_result = []
        for i in range(5, -1, -1):
            last_month = datetime.now() - relativedelta(months=i)
            text = format(last_month, '%B %Y')
            month_list.append(text)
        uid = request.session.uid
        employee = self.env['hr.employee'].sudo().search_read(
            [('user_id', '=', uid)], limit=1)
        for month in month_list:
            vals = {
                'l_month': month,
                'leave': 0
            }
            graph_result.append(vals)
        sql = """
                SELECT h.id, h.employee_id
                     , extract('month' FROM y)::int AS leave_month
                     , to_char(y, 'Month YYYY') as month_year
                     , GREATEST(y                    , h.date_from) AS date_from
                     , LEAST   (y + interval '1 month', h.date_to)   AS date_to
                FROM  (select * from hr_leave where state = 'validate') h
                     , generate_series(date_trunc('month', date_from::timestamp)
                                     , date_trunc('month', date_to::timestamp)
                                     , interval '1 month') y
                where date_trunc('month', GREATEST(y , h.date_from)) >= 
                date_trunc('month', now()) - interval '6 month' and
                date_trunc('month', GREATEST(y , h.date_from)) <= 
                date_trunc('month', now()) and h.employee_id = %s """
        self.env.cr.execute(sql, (employee[0]['id'],))
        results = self.env.cr.dictfetchall()
        for line in results:
            employee = self.browse(line['employee_id'])
            from_dt = fields.Datetime.from_string(line['date_from'])
            to_dt = fields.Datetime.from_string(line['date_to'])
            days = employee.get_work_days_dashboard(from_dt, to_dt)
            line['days'] = days
            vals = {
                'l_month': line['month_year'],
                'days': days
            }
            leave_lines.append(vals)
        if leave_lines:
            df = pd.DataFrame(leave_lines)
            rf = df.groupby(['l_month']).sum()
            result_lines = rf.to_dict('index')
            for line in result_lines:
                match = list(filter(
                    lambda d: d['l_month'].replace(' ', '') == line.replace(' ',
                                                                            ''),
                    graph_result))
                if match:
                    match[0]['leave'] = result_lines[line]['days']
        for result in graph_result:
            result['l_month'] = result['l_month'].split(' ')[:1][0].strip()[
                                :3] + " " + \
                                result['l_month'].split(' ')[1:2][0]
        return graph_result

    @api.model
    def join_resign_trends(self, date_from=None, date_to=None):
        """Returns join/resign details of departments"""
        cr = self._cr
        month_list = []
        join_trend = []
        resign_trend = []
        for i in range(5, -1, -1):
            last_month = datetime.now() - relativedelta(months=i)
            text = format(last_month, '%B %Y')
            month_list.append(text)
        for month in month_list:
            vals = {
                'l_month': month,
                'count': 0
            }
            join_trend.append(vals)
        for month in month_list:
            vals = {
                'l_month': month,
                'count': 0
            }
            resign_trend.append(vals)
        cr.execute('''select to_char(joining_date, 'Month YYYY') as l_month,
         count(id) from hr_employee
        WHERE joining_date BETWEEN CURRENT_DATE - INTERVAL '6 months'
        AND CURRENT_DATE + interval '1 month - 1 day'
        group by l_month''')
        join_data = cr.fetchall()
        cr.execute('''select to_char(resign_date, 'Month YYYY') as l_month,
         count(id) from hr_employee
        WHERE resign_date BETWEEN CURRENT_DATE - INTERVAL '6 months'
        AND CURRENT_DATE + interval '1 month - 1 day'
        group by l_month;''')
        resign_data = cr.fetchall()

        for line in join_data:
            match = list(filter(
                lambda d: d['l_month'].replace(' ', '') == line[0].replace(' ',
                                                                           ''),
                join_trend))
            if match:
                match[0]['count'] = line[1]
        for line in resign_data:
            match = list(filter(
                lambda d: d['l_month'].replace(' ', '') == line[0].replace(' ',
                                                                           ''),
                resign_trend))
            if match:
                match[0]['count'] = line[1]
        for join in join_trend:
            join['l_month'] = join['l_month'].split(' ')[:1][0].strip()[:3]
        for resign in resign_trend:
            resign['l_month'] = resign['l_month'].split(' ')[:1][0].strip()[:3]
        graph_result = [{
            'name': 'Join',
            'values': join_trend
        }, {
            'name': 'Resign',
            'values': resign_trend
        }]
        return graph_result

    @api.model
    def get_attrition_rate(self, date_from=None, date_to=None):
        """Returns monthly wise attrition rate"""
        month_attrition = []
        monthly_join_resign = self.join_resign_trends()
        month_join = monthly_join_resign[0]['values']
        month_resign = monthly_join_resign[1]['values']
        sql = """
        SELECT (date_trunc('month', CURRENT_DATE))::date - interval '1' 
        month * s.a AS month_start
        FROM generate_series(0,5,1) AS s(a);"""
        self._cr.execute(sql)
        month_start_list = self._cr.fetchall()
        for month_date in month_start_list:
            self._cr.execute("""select count(id), 
            to_char(date '%s', 'Month YYYY') as l_month from hr_employee
            where resign_date> date '%s' or resign_date is null and 
            joining_date < date '%s'
            """ % (month_date[0], month_date[0], month_date[0],))
            month_emp = self._cr.fetchone()
            match_join = \
                list(filter(
                    lambda d: d['l_month'] == month_emp[1].split(' ')[:1][
                                                  0].strip()[:3], month_join))[
                    0][
                    'count']
            match_resign = \
                list(filter(
                    lambda d: d['l_month'] == month_emp[1].split(' ')[:1][
                                                  0].strip()[:3],
                    month_resign))[0][
                    'count']
            month_avg = (month_emp[0] + match_join - match_resign + month_emp[
                0]) / 2
            attrition_rate = (match_resign / month_avg) * 100 \
                if month_avg != 0 else 0
            vals = {
                'month': month_emp[1].split(' ')[:1][0].strip()[:3],
                'attrition_rate': round(float(attrition_rate), 2)
            }
            month_attrition.append(vals)
        return month_attrition

    @api.model
    def get_employee_skill(self, date_from=None, date_to=None):
        """ Retrieve employee skills and its progress"""
        employee = self.env['hr.employee'].sudo().search(
            [('user_id', '=', request.session.uid)], limit=1)
        skills = self.env['hr.employee.skill'].sudo().search_read(
            [('employee_id', '=', employee.id)])
        dataset = []
        for rec in skills:
            vals = {
                'skills': rec['skill_type_id'][1] + '-' + rec['skill_id'][1],
                'progress': rec['level_progress']
            }
            dataset.append(vals)
        return dataset

    @api.model
    def get_employee_project_tasks(self, date_from=None, date_to=None):
        """Get employee's project tasks"""
        employee = self.env['hr.employee'].sudo().browse(self.env.uid)
        if not employee:
            return []

        # Get tasks assigned to the current user
        domain = [
            ('user_ids', 'in', self.env.uid),
            ('active', '=', True)
        ]
        if date_from: domain.append(('date_deadline', '>=', date_from))
        if date_to: domain.append(('date_deadline', '<=', date_to))
        
        tasks = self.env['project.task'].sudo().search(domain, order='date_deadline asc')
        task_data = []
        for task in tasks:
            task_data.append({
                'id': task.id,
                'task_name': task.name,
                'project_name': task.project_id.name if task.project_id else 'No Project',
                'date_deadline': task.date_deadline.strftime('%Y-%m-%d') if task.date_deadline else '',
                'stage_name': task.stage_id.name if task.stage_id else 'No Stage',
            })
        return task_data


    @api.model
    def employee_attendance_trend(self, date_from=None, date_to=None):
        """Weekly trend of unique people who attended by day of week"""
        day_abbr = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        graph_result = []
        
        today = datetime.now()
        start_of_week = today - relativedelta(days=today.weekday()) # Monday
        start_of_week_str = start_of_week.strftime('%Y-%m-%d 00:00:00')
        end_of_week = start_of_week + relativedelta(days=6)
        end_of_week_str = end_of_week.strftime('%Y-%m-%d 23:59:59')
        
        for abbr in day_abbr:
            vals = {
                'l_month': abbr, # Reusing l_month key to avoid breaking frontend JS
                'attendance': 0
            }
            graph_result.append(vals)

        sql = """
            SELECT to_char(check_in, 'Dy') as day_abbr, 
                   COUNT(DISTINCT employee_id) as attendance
            FROM hr_attendance
            WHERE check_in >= %s
              AND check_in <= %s
            GROUP BY to_char(check_in, 'Dy')
        """
        self.env.cr.execute(sql, (start_of_week_str, end_of_week_str))
        results = self.env.cr.dictfetchall()
        
        for res in results:
            d_abbr = res['day_abbr'].strip()
            for line in graph_result:
                if line['l_month'] == d_abbr:
                    line['attendance'] = res['attendance']
                    
        return graph_result
