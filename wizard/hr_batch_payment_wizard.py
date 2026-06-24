# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class HrBatchPaymentWizard(models.TransientModel):
    _name = 'hr.batch.payment.wizard'
    _description = 'Batch Payment Wizard'

    journal_id = fields.Many2one('account.journal', string='Payment Journal', required=True, domain=[('type', 'in', ('bank', 'cash'))])
    payment_method_line_id = fields.Many2one('account.payment.method.line', string='Payment Method', required=True,
                                             domain="[('journal_id', '=', journal_id), ('payment_type', '=', 'outbound')]")
    payment_date = fields.Date(string='Payment Date', required=True, default=fields.Date.context_today)
    payslip_ids = fields.Many2many('hr.payslip', string='Payslips', required=True)
    amount = fields.Monetary(string='Amount', compute='_compute_amount_memo')
    memo = fields.Char(string='Memo', compute='_compute_amount_memo')
    currency_id = fields.Many2one('res.currency', compute='_compute_currency_id')
    partner_bank_id = fields.Many2one('res.partner.bank', string='Recipient Bank Account')

    @api.depends('payslip_ids')
    def _compute_amount_memo(self):
        for wizard in self:
            if wizard.payslip_ids:
                wizard.amount = sum(wizard.payslip_ids.mapped('net_wage'))
                if len(wizard.payslip_ids) == 1:
                    wizard.memo = wizard.payslip_ids[0].number
                else:
                    wizard.memo = _("Batch Payment: %s Payslips") % len(wizard.payslip_ids)
            else:
                wizard.amount = 0.0
                wizard.memo = False

    @api.depends('payslip_ids')
    def _compute_currency_id(self):
        for wizard in self:
            if wizard.payslip_ids:
                wizard.currency_id = wizard.payslip_ids[0].company_id.currency_id.id
            else:
                wizard.currency_id = self.env.company.currency_id.id

    @api.model
    def default_get(self, fields_list):
        res = super(HrBatchPaymentWizard, self).default_get(fields_list)
        if self.env.context.get('active_model') == 'hr.payslip.run':
            run_id = self.env.context.get('active_id')
            if run_id:
                run = self.env['hr.payslip.run'].browse(run_id)
                res['payslip_ids'] = [(6, 0, run.slip_ids.ids)]
        elif self.env.context.get('active_model') == 'hr.payslip':
            res['payslip_ids'] = [(6, 0, self.env.context.get('active_ids', []))]
        return res

    def action_create_payment(self):
        self.ensure_one()
        payslips = self.payslip_ids.filtered(lambda p: p.state == 'done' and p.move_id)
        if not payslips:
            raise UserError(_("There are no confirmed payslips with accounting entries selected."))

        payments_created = self.env['account.payment']
        
        for slip in payslips:
            # Find the payable line from the payslip's journal entry
            payable_lines = slip.move_id.line_ids.filtered(
                lambda l: l.account_id.reconcile 
                and not l.reconciled and l.credit > 0
            )
            
            for line in payable_lines:
                partner_id = line.partner_id.id or slip.employee_id.work_contact_id.id
                if not partner_id:
                    raise UserError(_("No partner found for employee %s. Please configure the Private Address on the employee form.") % slip.employee_id.name)
                # Create the payment
                payment_vals = {
                    'date': self.payment_date,
                    'amount': line.credit,
                    'payment_type': 'outbound',
                    'partner_type': 'supplier',
                    'partner_id': partner_id,
                    'destination_account_id': line.account_id.id,
                    'journal_id': self.journal_id.id,
                    'payment_method_line_id': self.payment_method_line_id.id,
                    'memo': _("Payment for %s") % slip.name,
                }
                payment = self.env['account.payment'].create(payment_vals)
                payment.action_post()
                payments_created |= payment
                
                # Reconcile the payment with the payslip's payable line
                payment_lines = payment.line_ids.filtered(
                    lambda l: l.account_id == line.account_id and not l.reconciled
                )
                if payment_lines:
                    (line + payment_lines).reconcile()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Successfully created and reconciled %s payments.') % len(payments_created),
                'sticky': False,
                'type': 'success',
            }
        }
