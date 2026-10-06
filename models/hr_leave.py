# -*- coding: utf-8 -*-
#############################################################################
#
#    A part of OpenHRMS Project <https://www.openhrms.com>
#
#    Copyright (C) 2026-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions (odoo@cybrosys.com)
#
#    This program is under the terms of the Odoo Proprietary License v1.0
#    (OPL-1)
#    It is forbidden to publish, distribute, sublicense, or sell copies of the
#    Software or modified copies of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
#    OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
#    MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#    IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
#    CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
#    TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#    SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
#############################################################################
import re
from datetime import datetime
from odoo import api, models
from odoo.tools import email_split


class HrLeave(models.Model):
    """Inherited hr leave to inherit the message_new function"""
    _inherit = 'hr.leave'

    def _get_leave_type_from_subject(self, subject, employee):
        """Try to match a leave type name from the email subject.
        Falls back to first available no-allocation type accessible to the
        employee's company."""
        company = employee.company_id or self.env.company
        country_id = company.country_id.id if company.country_id else False
        domain = [
            ('company_id', 'in', [company.id, False]),
            '|', ('country_id', '=', False), ('country_id', '=', country_id)
        ]
        all_leave_types = self.env['hr.leave.type'].search(domain)
        subject_lower = subject.lower()
        for leave_type in all_leave_types:
            if leave_type.name.lower() in subject_lower:
                return leave_type
        leave_type = all_leave_types.filtered(
            lambda l_type: not l_type.requires_allocation)[:1]
        if not leave_type:
            leave_type = all_leave_types[:1]
        return leave_type

    def _extract_leave_dates(self, msg_body):
        """Extract start and end dates from email body."""
        clean_body = re.sub(
            r'<br\s*/?>', ' ', msg_body or '', flags=re.IGNORECASE)
        clean_body = re.sub(r'<[^>]+>', ' ', clean_body)
        clean_body = clean_body.replace('&nbsp;', ' ')
        clean_body = clean_body.replace('&amp;', '&')

        date_list = re.findall(r'\b\d{1,2}/\d{1,2}/\d{4}\b', clean_body)
        if not date_list:
            return None, None

        start_date = datetime.strptime(date_list[0], '%d/%m/%Y').date()
        date_to = (
            datetime.strptime(date_list[1], '%d/%m/%Y').date()
            if len(date_list) > 1 else start_date
        )
        return start_date, date_to

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """This function extracts required fields of hr.leave from incoming
        mail then creating records"""
        if custom_values is None:
            custom_values = {}
        msg_subject = msg_dict.get('subject', '')
        mail_from = msg_dict.get('email_from', '')

        alias_prefix = self.env['ir.config_parameter'].sudo().get_param(
            'ent_hr_leave_request_aliasing.alias_prefix')
        alias_domain = self.env['ir.config_parameter'].sudo().get_param(
            'ent_hr_leave_request_aliasing.alias_domain')

        subject_match = re.search(
            alias_prefix, msg_subject, re.IGNORECASE) if alias_prefix else None
        domain_match = (
            re.search(re.escape(alias_domain), mail_from, re.IGNORECASE)
            if alias_domain else None
        )

        if subject_match and domain_match:
            email_address = email_split(mail_from)[0]
            employee = self.env['hr.employee'].sudo().search(
                ['|', ('work_email', 'ilike', email_address),
                 ('user_id.email', 'ilike', email_address)], limit=1)

            if not employee:
                return super().message_new(msg_dict, custom_values)

            start_date, date_to = self._extract_leave_dates(
                msg_dict.get('body', ''))

            if start_date and date_to:
                # Check if same employee already has an active request for
                # these dates
                existing = self.env['hr.leave'].sudo().search([
                    ('employee_id', '=', employee.id),
                    ('name', '=', msg_subject.strip()),
                    ('request_date_from', '=', start_date),
                    ('request_date_to', '=', date_to),
                    ('state', 'not in', ['refuse', 'cancel']),
                ], limit=1)

                # Also check if employee already has an approved leave
                # overlapping these dates
                if not existing:
                    existing = self.env['hr.leave'].sudo().search([
                        ('employee_id', '=', employee.id),
                        ('state', 'in', ['validate', 'validate1']),
                        ('request_date_from', '<=', date_to),
                        ('request_date_to', '>=', start_date),
                    ], limit=1)

                if existing:
                    return existing

                leave_type = self._get_leave_type_from_subject(
                    msg_subject, employee)

                if leave_type:
                    return self.sudo().create({
                        'name': msg_subject.strip(),
                        'employee_id': employee.id,
                        'holiday_status_id': leave_type.id,
                        'request_date_from': start_date,
                        'request_date_to': date_to,
                    })
            else:
                existing = self.env['hr.leave'].sudo().search([
                    ('employee_id', '=', employee.id),
                    ('name', '=', msg_subject.strip()),
                    ('state', 'not in', ['refuse', 'cancel']),
                ], order='id desc', limit=1)
                if existing:
                    return existing

        return super().message_new(msg_dict, custom_values)
