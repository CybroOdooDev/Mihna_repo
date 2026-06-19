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
from odoo import fields, models, api
from dateutil.relativedelta import relativedelta


class HrInsurance(models.Model):
    """Created a new model for employee insurance"""
    _name = 'hr.insurance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'HR Insurance'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', string='Employee',
                                  required=True, help="Employee", tracking=True)
    policy_id = fields.Many2one('insurance.policy',
                                string='Policy', required=True, help="Policy", tracking=True)
    insurer_id = fields.Many2one(related='policy_id.insurer_id', string='Insurance Provider', readonly=True)
    group_policy_number = fields.Char(related='policy_id.group_policy_number', string='Group Policy Number', readonly=True)
    amount = fields.Float(string='Premium', required=True, help="Policy amount", tracking=True)
    sum_insured = fields.Float(string="Sum Insured", required=True,
                               help="Insured sum", tracking=True)
    policy_coverage = fields.Selection([('monthly', 'Monthly'),
                                        ('yearly', 'Yearly')],
                                       required=True, default='monthly',
                                       string='Policy Coverage',
                                       help="Duration of the policy", tracking=True)
    date_from = fields.Date(string='Date From',
                            default=fields.Date.today(), readonly=True,
                            help="Start date", tracking=True)
    date_to = fields.Date(string='Date To', help="End date", tracking=True)
    state = fields.Selection([('active', 'Active'),
                              ('expired', 'Expired'), ],
                             default='active', string="State",
                             compute='_compute_status',
                                 store=True,
                             help="State for the insurance", tracking=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 required=True, help="Company",
                                 default=lambda self: self.env.user.company_id)

    def action_renewal(self):
        """Action to renew an expired policy by updating the start date."""
        for rec in self:
            if rec.state == 'expired':
                rec.date_from = fields.Date.today()
                # _compute_status will automatically recalculate date_to and set state='active'

    @api.depends('date_from','date_to', 'policy_coverage', 'sum_insured', 'amount')
    def _compute_status(self):
        """This function is get and set state"""
        current_date = fields.Date.today()
        for rec in self:
            if rec.policy_coverage == 'monthly':
                rec.date_to = fields.Date.end_of(rec.date_from, 'month')
            if rec.policy_coverage == 'yearly':
                rec.date_to = fields.Date.end_of(rec.date_from, 'year')
            if rec.date_from <= current_date:
                if rec.date_to and rec.date_to >= current_date:
                    rec.state = 'active'
                else:
                    rec.state = 'expired'
            else:
                rec.state = 'active'
                
    @api.model
    def _cron_update_insurance_status(self):
        """Cron job to update insurance status and schedule reminders"""
        # Recompute status for all active policies
        active_policies = self.search([('state', '=', 'active')])
        for policy in active_policies:
            policy._compute_status()
            
        # Check for policies expiring in exactly 7 days
        warning_date = fields.Date.today() + relativedelta(days=7)
        expiring_policies = self.search([
            ('state', '=', 'active'),
            ('date_to', '=', warning_date)
        ])
        
        for policy in expiring_policies:
            # Assign activity to the employee's related user, or fallback to the system user
            user_id = policy.employee_id.user_id.id or self.env.user.id
            policy.activity_schedule(
                'mail.mail_activity_data_todo',
                note='Insurance Policy is expiring in 7 days! Please review for renewal.',
                user_id=user_id
            )
