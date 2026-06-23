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
                lambda l: l.account_id.account_type in ('liability_payable', 'asset_receivable') 
                and not l.reconciled and l.credit > 0
            )
            
            for line in payable_lines:
                partner_id = line.partner_id.id or slip.employee_id.address_home_id.id
                if not partner_id:
                    raise UserError(_("No partner found for employee %s. Please configure the Private Address on the employee form.") % slip.employee_id.name)
                # Create the payment
                payment_vals = {
                    'date': self.payment_date,
                    'amount': line.credit,
                    'payment_type': 'outbound',
                    'partner_type': 'supplier',
                    'partner_id': partner_id,
                    'journal_id': self.journal_id.id,
                    'payment_method_line_id': self.payment_method_line_id.id,
                    'ref': _("Payment for %s") % slip.name,
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
