# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class HrLoanEarlySettlement(models.TransientModel):
    _name = 'hr.loan.early.settlement'
    _description = 'Early Settlement Wizard'

    loan_id = fields.Many2one('hr.loan', string="Loan", required=True)
    amount = fields.Float(string="Settlement Amount", required=True)
    settlement_type = fields.Selection([
        ('next_installments', 'Deduct from Next Installment(s)'),
        ('spread_equally', 'Spread Equally Across Remaining Installments')
    ], string="Settlement Method", required=True, default='next_installments')

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("Amount must be greater than zero."))
            if round(rec.amount, 2) > round(rec.loan_id.balance_amount, 2):
                raise ValidationError(_("Amount cannot exceed the remaining balance amount."))

    def action_settle(self):
        for rec in self:
            loan = rec.loan_id
            if loan.state != 'approve':
                raise ValidationError(_("Early settlement is only allowed for approved loans."))

            unpaid_lines = loan.loan_lines.filtered(lambda l: not l.paid)
            if not unpaid_lines:
                raise ValidationError(_("No unpaid installments to settle."))

            # Add a payment line
            self.env['hr.loan.line'].with_context(early_settlement=True).create({
                'date': fields.Date.today(),
                'amount': rec.amount,
                'employee_id': loan.employee_id.id,
                'loan_id': loan.id,
                'paid': True,
            })

            # Adjust unpaid lines
            remaining_s = rec.amount
            if rec.settlement_type == 'next_installments':
                for line in unpaid_lines.sorted('date'):
                    if round(remaining_s, 2) <= 0:
                        break
                    if line.amount <= remaining_s + 0.001:
                        remaining_s -= line.amount
                        line.with_context(early_settlement=True).unlink()
                    else:
                        line.with_context(early_settlement=True).write({'amount': line.amount - remaining_s})
                        remaining_s = 0

            elif rec.settlement_type == 'spread_equally':
                while round(remaining_s, 2) > 0:
                    existing_lines = unpaid_lines.filtered(lambda l: l.exists())
                    if not existing_lines:
                        break
                    per_line = remaining_s / len(existing_lines)
                    for line in existing_lines:
                        if round(remaining_s, 2) <= 0:
                            break
                        if line.amount <= per_line + 0.001:
                            remaining_s -= line.amount
                            line.with_context(early_settlement=True).unlink()
                        else:
                            line.with_context(early_settlement=True).write({'amount': line.amount - per_line})
                            remaining_s -= per_line

            loan._compute_total_amount()
        return {'type': 'ir.actions.act_window_close'}
