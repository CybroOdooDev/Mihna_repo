# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from markupsafe import Markup

class HrLoanTopup(models.TransientModel):
    _name = 'hr.loan.topup'
    _description = 'Loan Top-Up Wizard'

    loan_id = fields.Many2one('hr.loan', string="Loan", required=True)
    topup_amount = fields.Float(string="Top-Up Amount", required=True, help="Additional amount to add to the existing loan.")
    additional_installments = fields.Integer(string="Additional Installments", default=0, help="Optional: Number of extra months to extend the loan term.")

    def action_topup(self):
        self.ensure_one()
        if self.topup_amount <= 0:
            raise UserError(_("Top-Up Amount must be strictly positive."))
            
        loan = self.loan_id
        
        # 1. Add top-up amount to loan amount
        old_amount = loan.loan_amount
        loan.loan_amount += self.topup_amount
        
        # 2. Add additional installments
        if self.additional_installments > 0:
            loan.installment += self.additional_installments
            
        # 3. Restructure the schedule safely
        # We pass early_settlement=True in context to bypass the block on unlinking/creating lines
        loan.with_context(early_settlement=True).action_compute_installment()
        
        # 4. Trigger Accounting Entry if available
        if hasattr(loan, 'action_topup_accounting'):
            loan.action_topup_accounting(self.topup_amount)
            
        # 5. Log action in chatter
        msg = Markup(_(
            "<b>Loan Top-Up Processed</b><br/>"
            "An additional amount of <b>%s</b> has been added to the loan.<br/>"
            "The loan principal was increased from %s to %s.<br/>"
            "The future schedule has been automatically recalculated."
        )) % (self.topup_amount, old_amount, loan.loan_amount)
        loan.message_post(body=msg)
        
        return {'type': 'ir.actions.act_window_close'}
