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
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

date_format = "%Y-%m-%d"



class HrResignation(models.Model):
    """ Model for HR Resignations. This model is used to track employee
        resignations."""
    _name = 'hr.resignation'
    _description = 'HR Resignation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'employee_id'

    name = fields.Char(string='Order Reference', copy=False,
                       readonly=True, index=True,
                       default=lambda self: _('New'))
    employee_id = fields.Many2one('hr.employee', string="Employee",
                                  default=lambda
                                      self: self.env.user.employee_id.id,
                                  help='Name of the employee for '
                                       'whom the request is creating')
    department_id = fields.Many2one('hr.department', string="Department",
                                    related='employee_id.department_id',
                                    help='Department of the employee')
    resign_confirm_date = fields.Date(string="Confirmed Date",
                                      help='Date on which the request '
                                           'is confirmed by the employee.',
                                      track_visibility="always")
    approved_revealing_date = fields.Date(
        string="Approved Last Day Of Employee",
        help='Date on which the request is confirmed by the manager.',
        track_visibility="always")
    joined_date = fields.Date(string="Join Date",
                              help='Joining date of the employee.'
                                   'i.e Start date of the first contract')
    expected_revealing_date = fields.Date(string="Last Day of Employee",
                                          required=True,
                                          help='Employee requested date on '
                                               'which employee is revealing '
                                               'from the company.')
    reason = fields.Text(string="Reason", required=True,
                         help='Specify reason for leaving the company')
    notice_period = fields.Integer(string="Notice Period",
                                compute="_compute_notice_period",
                                help="Notice Period of the employee in days")
    state = fields.Selection(
        [('draft', 'Draft'), ('confirm', 'Confirm'), 
         ('manager_approved', 'Manager Approved'),
         ('approved', 'Approved'),
         ('clearance', 'Clearance'),
         ('settlement', 'Settlement'),
         ('relieved', 'Relieved'),
         ('cancel', 'Rejected')],
        string='Status', default='draft', track_visibility="always")

    change_employee = fields.Boolean(string="Change Employee",
                                     compute="_compute_change_employee",
                                     help="Checks , if the user has permission"
                                          " to change the employee")
    is_manager = fields.Boolean(compute='_compute_is_manager', string="Is Manager")
    employee_contract = fields.Char(
        string="Contract Template",
        compute="_compute_notice_period",
        store=True,
        help="Current Contract of the employee"
    )

    # Process Fields
    clearance_line_ids = fields.One2many('hr.resignation.clearance.line', 'resignation_id', string='Clearance Lines')
    clearance_progress = fields.Float(string='Clearance Progress', compute='_compute_clearance_progress')
    settlement_state = fields.Selection([('draft', 'Draft'), ('computed', 'Computed'), ('approved', 'Approved')], string='Settlement State', default='draft')
    survey_id = fields.Many2one('survey.survey', string='Exit Interview Template')
    exit_interview_id = fields.Many2one('survey.user_input', string='Exit Interview')
    relieving_date = fields.Date(string='Relieving Date')

    # Analytics Fields
    reason_category_id = fields.Many2one('hr.departure.reason', string='Reason Category')
    is_regrettable = fields.Boolean(string='Regrettable Attrition')
    rehire_eligible = fields.Boolean(string='Rehire Eligible')
    replacement_employee_id = fields.Many2one('hr.employee', string='Replacement Employee')
    handover_notes = fields.Text(string='Handover Notes')

    # Settlement Fields
    pending_salary = fields.Float(string='Pending Salary')
    leave_encashment = fields.Float(string='Leave Encashment')
    gratuity = fields.Float(string='Gratuity')
    bonus = fields.Float(string='Bonus')
    loan_recovery = fields.Float(string='Loan Recovery')
    advance_recovery = fields.Float(string='Advance Recovery')
    notice_recovery = fields.Float(string='Notice Recovery')
    asset_recovery = fields.Float(string='Asset Recovery', compute='_compute_asset_recovery', store=True)
    net_settlement = fields.Float(string='Net Settlement', compute='_compute_net_settlement')
    payslip_id = fields.Many2one('hr.payslip', string='Settlement Payslip')

    @api.depends('employee_id')
    def _compute_change_employee(self):
        """ Check whether the user has the permission to change the employee"""
        res_user = self.env.user
        self.change_employee = res_user.has_group('hr.group_hr_user')

    @api.depends('employee_id.parent_id.user_id')
    def _compute_is_manager(self):
        for rec in self:
            rec.is_manager = (rec.employee_id.parent_id.user_id == self.env.user) or self.env.user.has_group('hr.group_hr_user')

    @api.constrains('employee_id')
    def _check_employee_id(self):
        """ Constraint method to check if the current user has the permission
             to create a resignation request for the specified employee.
        """
        for resignation in self:
            if not self.env.user.has_group('hr.group_hr_user'):
                if (resignation.employee_id.user_id.id and
                        resignation.employee_id.user_id.id != self.env.uid):
                    raise ValidationError(
                        _('You cannot create a request for other employees'))

    @api.constrains('employee_id', 'state')
    def _check_joined_date(self):
        """ Check if there is an active resignation request for the
            same employee with a confirmed or approved state."""
        for resignation in self:
            if resignation.state in ['confirm', 'approved']:
                resignation_request = self.env['hr.resignation'].search(
                    [('employee_id', '=', resignation.employee_id.id),
                     ('state', 'in', ['confirm', 'approved']),
                     ('id', '!=', resignation.id)])
                if resignation_request:
                    raise ValidationError(
                        _('There is a resignation request in confirmed or'
                          ' approved state for this employee'))

    @api.depends(
        'employee_id',
        'employee_id.joining_date',
        'employee_id.version_id.date_start',
        'employee_id.version_id.date_end'
    )
    def _compute_notice_period(self):
        """Compute notice period for each resignation."""
        today = fields.Date.today()
        for rec in self:
            rec.joined_date = rec.employee_id.joining_date if rec.employee_id else False
            rec.employee_contract = False
            rec.notice_period = 0

            if rec.employee_id:
                contract = self.env['hr.version'].sudo().search([
                    ('employee_id', '=', rec.employee_id.id),
                    '|', ('date_start', '=', False),
                    ('date_start', '<=', today),
                    '|', ('date_end', '=', False),
                    ('date_end', '>=', today),
                ], limit=1)

                if contract:
                    rec.employee_contract = contract.contract_template_id.name
                    rec.notice_period = contract.notice_days

    @api.depends('clearance_line_ids', 'clearance_line_ids.state')
    def _compute_clearance_progress(self):
        for rec in self:
            total = len(rec.clearance_line_ids)
            cleared = len(rec.clearance_line_ids.filtered(lambda l: l.state == 'cleared'))
            rec.clearance_progress = (cleared / total * 100.0) if total > 0 else 0.0

    @api.depends('pending_salary', 'leave_encashment', 'gratuity', 'bonus', 'loan_recovery', 'advance_recovery', 'notice_recovery', 'asset_recovery')
    def _compute_net_settlement(self):
        for rec in self:
            rec.net_settlement = (rec.pending_salary + rec.leave_encashment + rec.gratuity + rec.bonus) - (rec.loan_recovery + rec.advance_recovery + rec.notice_recovery + rec.asset_recovery)

    @api.depends('clearance_line_ids', 'clearance_line_ids.due_amount')
    def _compute_asset_recovery(self):
        for rec in self:
            rec.asset_recovery = sum(rec.clearance_line_ids.mapped('due_amount'))

    @api.model
    def create(self, vals):
        """Override create to assign a sequence for the record(s)."""
        if isinstance(vals, list):  # multiple records
            for v in vals:
                if v.get('name', _('New')) == _('New'):
                    v['name'] = self.env['ir.sequence'].next_by_code(
                        'hr.resignation') or _('New')
        else:  # single record
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'hr.resignation') or _('New')

        return super(HrResignation, self).create(vals)

    def action_confirm_resignation(self):
        """ Method triggered by the 'Confirm' button to confirm the
        resignation request."""
        for resignation in self:
            if resignation.joined_date:
                if (resignation.joined_date >=
                        resignation.expected_revealing_date):
                    raise ValidationError(
                        _('Last date of the Employee must '
                          'be anterior to Joining date'))
            else:
                raise ValidationError(
                    _('Please set a Joining Date for employee'))
            if self.env.company.sudo().enable_manager_approval:
                resignation.state = 'confirm'
                manager = resignation.sudo().employee_id.parent_id
                if manager and manager.user_id:
                    resignation.activity_schedule(
                        'mail.mail_activity_data_todo',
                        user_id=manager.user_id.id,
                        summary=_('Review resignation request'),
                        note=_('Please review the resignation request for %s.') % resignation.employee_id.name
                    )
            else:
                resignation.state = 'manager_approved'
            resignation.resign_confirm_date = str(fields.Datetime.now())

    def action_manager_approve(self):
        """ Method triggered by the Line Manager to approve the resignation."""
        for resignation in self:
            resignation.state = 'manager_approved'

    def action_cancel_resignation(self):
        """ Method triggered by the 'Cancel' button to cancel the resignation
            request."""
        for resignation in self:
            resignation.state = 'cancel'

    def action_reject_resignation(self):
        """ Method triggered by the 'Reject' button to reject the
            resignation request."""
        for resignation in self:
            resignation.state = 'cancel'

    def action_reset_to_draft(self):
        """ Method triggered by the 'Set to Draft' button to reset the
        resignation request to the 'draft' state."""
        for resignation in self:
            resignation.state = 'draft'
            resignation.employee_id.active = True
            resignation.employee_id.resigned = False
            resignation.employee_id.fired = False

    def action_approve_resignation(self):
        """ Method triggered by the 'Approve' button to
               approve the resignation."""
        for resignation in self:
            if (resignation.expected_revealing_date and
                    resignation.resign_confirm_date):
                employee_contract = self.env['hr.version'].sudo().search(
                    [('employee_id', '=', resignation.employee_id.id)])
                if not employee_contract:
                    raise ValidationError(
                        _("There are no Contracts found for this employee"))
                for contract in employee_contract:
                    resignation.state = 'clearance'
                    resignation.approved_revealing_date = (
                            resignation.resign_confirm_date + timedelta(
                        days=contract.notice_days))

                # Generate clearance lines from template
                template = self.env.company.clearance_template_id
                if template:
                    for c_type in template.clearance_type_ids:
                        clearance_line = self.env['hr.resignation.clearance.line'].create({
                            'resignation_id': resignation.id,
                            'clearance_type_id': c_type.id,
                            'responsible_user_id': c_type.default_responsible_id.id or self.env.uid,
                        })
                        if clearance_line.responsible_user_id:
                            resignation.activity_schedule(
                                'mail.mail_activity_data_todo',
                                user_id=clearance_line.responsible_user_id.id,
                                summary=_('Clearance Check'),
                                note=_('Please review the clearance checklist for %s.') % resignation.employee_id.name
                            )
                
                # Check for open custodies
                resignation._check_open_custody()
            else:
                raise ValidationError(_('Please Enter Valid Dates.'))

    def _check_open_custody(self):
        for resignation in self:
            open_custodies = self.env['hr.custody'].search([
                ('employee_id', '=', resignation.employee_id.id),
                ('state', '=', 'approved')
            ])
            if open_custodies:
                # Find IT/Admin clearance line to block
                admin_lines = resignation.clearance_line_ids.filtered(lambda l: l.clearance_type_id.name in ['IT', 'Admin'])
                if admin_lines:
                    remarks = "Pending return:\n" + "\n".join([f"- {c.custody_property_id.name} ({c.name})" for c in open_custodies])
                    for line in admin_lines:
                        line.state = 'blocked'
                        line.remarks = remarks

    def action_compute_settlement(self):
        for resignation in self:
            resignation.settlement_state = 'computed'

    def action_approve_settlement(self):
        for resignation in self:
            if resignation.clearance_progress < 100.0:
                raise ValidationError(_("Cannot approve settlement until all clearance lines are cleared!"))
            
            # Payroll Integration: Create a Payslip for the final settlement
            payslip_vals = {
                'employee_id': resignation.employee_id.id,
                'name': f"F&F Settlement - {resignation.employee_id.name}",
            }
            payslip = self.env['hr.payslip'].create(payslip_vals)
            resignation.payslip_id = payslip.id
            resignation.state = 'settlement'
            resignation.settlement_state = 'approved'

    def action_relieve(self):
        for resignation in self:
            if resignation.state != 'settlement' or resignation.settlement_state != 'approved':
                raise ValidationError(_("Clearance and Settlement must be completed before relieving."))
            
            resignation.state = 'relieved'
            resignation.relieving_date = fields.Date.today()
            
            # Deactivate employee
            resignation.employee_id.active = False
            resignation.employee_id.resign_date = resignation.expected_revealing_date
            
            if resignation.reason_category_id.name == 'Resigned':
                resignation.employee_id.resigned = True
            elif resignation.reason_category_id.name == 'Fired':
                resignation.employee_id.fired = True
            
            departure_reason_id = resignation.reason_category_id

            resignation.employee_id.departure_reason_id = departure_reason_id
            resignation.employee_id.departure_date = resignation.relieving_date
            
            if resignation.employee_id.user_id:
                resignation.employee_id.user_id.active = False
                resignation.employee_id.user_id = None

    def action_withdraw(self):
        for resignation in self:
            if resignation.state == 'relieved':
                raise ValidationError(_("Cannot withdraw a resignation that is already relieved."))
            resignation.state = 'cancel'
            resignation.employee_id.active = True
            resignation.employee_id.resigned = False
            resignation.employee_id.fired = False

    @api.model
    def update_employee_status(self):
        today = fields.Date.today()
        resignations = self.search([
            ('state', '=', 'settlement'),
            ('settlement_state', '=', 'approved'),
            ('expected_revealing_date', '<=', today)
        ])
        for resignation in resignations:
            resignation.action_relieve()
    def action_send_exit_interview(self):
        self.ensure_one()
        
        partner = self.employee_id.user_id.partner_id or self.employee_id.work_contact_id
        if not partner:
            if self.employee_id.work_email:
                # If they have a work email but no partner, try to find or create one
                partner = self.env['res.partner'].search([('email', '=', self.employee_id.work_email)], limit=1)
                if not partner:
                    partner = self.env['res.partner'].sudo().create({
                        'name': self.employee_id.name,
                        'email': self.employee_id.work_email,
                    })
            else:
                raise ValidationError(_("The employee must have a linked user, private address, or work email to send an interview."))

        if not self.survey_id:
            raise ValidationError(_("Please select an Exit Interview Template before sending."))

        local_context = dict(
            default_partner_ids=partner.ids,
            default_survey_id=self.survey_id.id,
            default_email_layout_xmlid='mail.mail_notification_light',
        )

        return {
            'type': 'ir.actions.act_window',
            'name': _("Send Exit Interview"),
            'view_mode': 'form',
            'res_model': 'survey.invite',
            'target': 'new',
            'context': local_context,
        }
