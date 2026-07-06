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
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class HrLoan(models.Model):
    """ Model for managing loan requests."""
    _name = 'hr.loan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Loan Request"

    @api.model
    def default_get(self, field_list):
        """ Function used to pass employee corresponding to current login user
            as default employee while creating new loan request
            :param field_list : Fields and values for the model hr.loan"""
        result = super(HrLoan, self).default_get(field_list)
        if result.get('user_id'):
            user_id = result['user_id']
        else:
            user_id = self.env.context.get('user_id', self.env.user.id)
        result['employee_id'] = self.env['hr.employee'].search(
            [('user_id', '=', user_id)], limit=1).id
        return result

    name = fields.Char(string="Loan Name", default="New", readonly=True,
                       help="Name of the loan")
    date = fields.Date(string="Date", default=fields.Date.today(),
                       readonly=True, help="Date of the loan request")
    employee_id = fields.Many2one('hr.employee', string="Employee",
                                  required=True, help="Employee Name")
    department_id = fields.Many2one('hr.department',
                                    related="employee_id.department_id",
                                    readonly=True,
                                    string="Department",
                                    help="The department to which the "
                                         "employee belongs.")
    installment = fields.Integer(string="No Of Installments", default=1,
                                 help="Number of installments")
    payment_date = fields.Date(string="Payment Start Date", required=True,
                               default=fields.Date.today(),
                               help="Date of the payment")
    loan_lines = fields.One2many('hr.loan.line', 'loan_id',
                                 string="Loan Line",
                                 help="Details of installment lines "
                                      "associated with the loan.",
                                 index=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 help="Company",
                                 default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  required=True, help="Currency",
                                  default=lambda self: self.env.user.
                                  company_id.currency_id)
    job_position_id = fields.Many2one('hr.job',
                                   related="employee_id.job_id",
                                   readonly=True, string="Job Position",
                                   help="Job position of the employee")
    loan_amount = fields.Float(string="Loan Amount", required=True,
                               help="Loan amount")
    total_amount = fields.Float(string="Total Amount", store=True,
                                readonly=True, compute='_compute_total_amount',
                                help="The total amount of the loan")
    balance_amount = fields.Float(string="Balance Amount", store=True,
                                  compute='_compute_total_amount',
                                  help="""The remaining balance amount of the 
                                  loan after deducting 
                                  the total paid amount.""")
    total_paid_amount = fields.Float(string="Total Paid Amount", store=True,
                                     compute='_compute_total_amount',
                                     help="The total amount that has been "
                                          "paid towards the loan.")
    remaining_principal = fields.Float(string="Remaining Principal", store=True,
                                       compute='_compute_total_amount',
                                       help="The remaining principal amount of the loan, used for early settlement.")
    interest_rate = fields.Float(string="Interest Rate (%)", help="Interest rate for the loan")
    interest_type = fields.Selection([('flat', 'Flat Rate'), ('reducing', 'Reducing Balance')], string="Interest Type", default='flat')
    total_interest_amount = fields.Float(string="Total Interest Amount", compute='_compute_total_amount', store=True, help="Total interest amount calculated")
    is_fully_paid = fields.Boolean(string="Fully Paid", compute='_compute_total_amount', store=True, help="Indicates if the loan is fully paid off.")
    state = fields.Selection(
        [('draft', 'Draft'), ('waiting_approval_1', 'Submitted'),
         ('approve', 'Approved'), ('refuse', 'Refused'), ('cancel', 'Canceled'),
         ], string="State", default='draft', help="The current state of the "
                                                  "loan request.", copy=False)

    def _compute_total_amount(self):
        """ Compute total loan amount,balance amount and total paid amount"""
        for loan in self:
            total_paid = sum(line.amount for line in loan.loan_lines if line.paid)
            paid_principal = sum(line.principal_amount for line in loan.loan_lines if line.paid)
            total_interest = sum(line.interest_amount for line in loan.loan_lines)
            
            loan.total_interest_amount = total_interest
            loan.total_amount = loan.loan_amount + total_interest
            loan.balance_amount = loan.total_amount - total_paid
            loan.total_paid_amount = total_paid
            loan.remaining_principal = loan.loan_amount - paid_principal
            loan.is_fully_paid = loan.state == 'approve' and loan.total_amount > 0 and round(loan.balance_amount, 2) <= 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            # check for existing pending loans
            loan_count = self.env['hr.loan'].search_count([
                ('employee_id', '=', values.get('employee_id')),
                ('state', '=', 'approve'),
                ('balance_amount', '!=', 0)
            ])
            if loan_count:
                raise ValidationError(
                    _("The Employee already has a pending installment")
                )

            # generate sequence
            values['name'] = self.env['ir.sequence'].next_by_code(
                'hr.loan.seq') or _('New')

        return super(HrLoan, self).create(vals_list)

    def action_compute_installment(self):
        """This automatically create the installment the employee need to pay to
            company based on payment start date and the no of installments.
            """
        for loan in self:
            unpaid_lines = loan.loan_lines.filtered(lambda l: not l.paid)
            paid_lines = loan.loan_lines.filtered(lambda l: l.paid)
            unpaid_lines.with_context(early_settlement=True).unlink()

            date_start = datetime.strptime(str(loan.payment_date), '%Y-%m-%d')
            if paid_lines:
                last_paid = max(paid_lines.mapped('date'))
                date_start = last_paid + relativedelta(months=1)

            remaining_installments = loan.installment - len(paid_lines)
            if remaining_installments <= 0:
                continue

            remaining_principal = loan.loan_amount - sum(paid_lines.mapped('principal_amount'))
            principal_per_installment = remaining_principal / remaining_installments

            total_interest = 0.0
            if loan.interest_rate > 0:
                if loan.interest_type == 'flat':
                    total_interest = remaining_principal * (loan.interest_rate / 100.0)
                elif loan.interest_type == 'reducing':
                    temp_principal = remaining_principal
                    for i in range(remaining_installments):
                        total_interest += temp_principal * (loan.interest_rate / 100.0)
                        temp_principal -= principal_per_installment

            interest_per_installment = 0.0
            if remaining_installments > 0:
                interest_per_installment = total_interest / remaining_installments

            for i in range(1, remaining_installments + 1):
                interest_amt = interest_per_installment
                    
                self.env['hr.loan.line'].with_context(early_settlement=True).create({
                    'date': date_start,
                    'principal_amount': principal_per_installment,
                    'interest_amount': interest_amt,
                    'amount': principal_per_installment + interest_amt,
                    'employee_id': loan.employee_id.id,
                    'loan_id': loan.id})
                date_start = date_start + relativedelta(months=1)
            loan._compute_total_amount()
        return True

    def action_refuse(self):
        """ Function to reject loan request"""
        return self.write({'state': 'refuse'})

    def action_submit(self):
        """ Function to submit loan request"""
        self.write({'state': 'waiting_approval_1'})

    def action_cancel(self):
        """ Function to cancel loan request"""
        self.write({'state': 'cancel'})

    def action_approve(self):
        """ Function to approve loan request"""
        for data in self:
            if not data.loan_lines:
                raise ValidationError(_("Please Compute installment"))
            else:
                self.write({'state': 'approve'})

    def action_early_settlement(self):
        """ Open wizard to early settle loan """
        self.ensure_one()
        if self.state != 'approve':
            raise UserError(_("Early settlement is only allowed for approved loans."))
        
        paid_principal = sum(self.loan_lines.filtered(lambda l: l.paid).mapped('principal_amount'))
        remaining_principal = self.loan_amount - paid_principal

        return {
            'name': _('Early Settlement'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.loan.early.settlement',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_loan_id': self.id,
                'default_amount': remaining_principal,
            }
        }

    def write(self, vals):
        """ Override write to trigger automated email notifications """
        res = super(HrLoan, self).write(vals)
        
        for loan in self:
            if 'state' in vals:
                if vals['state'] == 'waiting_approval_1':
                    template = self.env.ref('ohrms_loan.email_template_loan_submitted', raise_if_not_found=False)
                    if template:
                        template.send_mail(loan.id, force_send=True)
                elif vals['state'] == 'approve':
                    template = self.env.ref('ohrms_loan.email_template_loan_approved', raise_if_not_found=False)
                    if template:
                        template.send_mail(loan.id, force_send=True)
                        
            if 'is_fully_paid' in vals and vals['is_fully_paid']:
                template = self.env.ref('ohrms_loan.email_template_loan_closed', raise_if_not_found=False)
                if template:
                    template.send_mail(loan.id, force_send=True)
                    
        return res

    def action_deferment(self):
        """ Open wizard to defer loan installment """
        self.ensure_one()
        if self.state != 'approve':
            raise UserError(_("Deferment is only allowed for approved loans."))
        if self.balance_amount <= 0:
            raise UserError(_("This loan is already fully paid."))
            
        return {
            'name': _('Defer Installment'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.loan.deferment',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_loan_id': self.id,
            }
        }

    def action_topup(self):
        """ Open wizard to top-up loan """
        self.ensure_one()
        if self.state != 'approve':
            raise UserError(_("Top-Up is only allowed for approved loans."))
        if self.balance_amount <= 0:
            raise UserError(_("This loan is already fully paid."))
            
        return {
            'name': _('Top-Up Loan'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.loan.topup',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_loan_id': self.id,
            }
        }

    def unlink(self):
        """ Function which restrict the deletion of approved or submitted
                loan request"""
        for loan in self:
            if loan.state not in ('draft', 'cancel'):
                raise UserError(_(
                    'You cannot delete a loan which is not in draft '
                    'or cancelled state'))
        return super(HrLoan, self).unlink()
