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
from odoo import fields, models, _


class HrPayslipRun(models.Model):
    """Extends the standard 'hr.payslip.run' model to include additional fields
    for managing payroll runs.
    Methods:
        compute_total_amount: Compute the total amount of the payroll run."""
    _inherit = 'hr.payslip.run'

    journal_id = fields.Many2one(comodel_name='account.journal',
                                 string='Salary Journal',
                                 required=True, help="Journal associated with "
                                                     "the record",
                                 default=lambda self: self.env[
                                     'account.journal'].search(
                                     [('type', '=', 'general')],
                                     limit=1))
    move_count = fields.Integer(compute='_compute_move_count', string='Journal Entries')
    payment_count = fields.Integer(compute='_compute_payment_count', string='Payments')

    def _compute_payment_count(self):
        for run in self:
            run.payment_count = self.env['account.payment'].search_count([('memo', 'in', run.slip_ids.mapped('number'))])

    def action_register_payment(self):
        self.ensure_one()
        for slip in self.slip_ids.filtered(lambda s: s.state == 'done'):
            slip.action_register_payment()
        return True

    def action_open_payments(self):
        self.ensure_one()
        payments = self.env['account.payment'].search([('memo', 'in', self.slip_ids.mapped('number'))])
        return {
            'name': _('Payments'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', payments.ids)],
        }

    def _compute_move_count(self):
        for run in self:
            run.move_count = len(run.mapped('slip_ids.move_id'))

    def action_open_journal_entries(self):
        self.ensure_one()
        moves = self.mapped('slip_ids.move_id')
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_journal_line")
        action['domain'] = [('id', 'in', moves.ids)]
        action['context'] = {'default_journal_id': self.journal_id.id}
        return action
