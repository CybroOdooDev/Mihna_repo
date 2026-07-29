# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_om_edi_document_ids = fields.One2many(
        comodel_name='l10n.om.edi.document', inverse_name='move_id', string="Oman E-Invoicing Documents")
    l10n_om_edi_document_count = fields.Integer(compute='_compute_l10n_om_edi_document_count')
    l10n_om_edi_state = fields.Selection(related='l10n_om_edi_document_ids.l10n_om_edi_state', string="Oman E-Invoicing State")

    @api.depends('l10n_om_edi_document_ids')
    def _compute_l10n_om_edi_document_count(self):
        for move in self:
            move.l10n_om_edi_document_count = len(move.l10n_om_edi_document_ids)

    def _l10n_om_edi_get_or_create_document(self):
        self.ensure_one()
        document = self.l10n_om_edi_document_ids.filtered(lambda d: d.l10n_om_edi_state not in ('rejected', 'cancelled'))[:1]
        if not document:
            document = self.env['l10n.om.edi.document'].create({
                'move_id': self.id,
                'company_id': self.company_id.id,
            })
        return document

    def action_l10n_om_edi_submit(self):
        """ Generate the PINT OM + TDD XML and submit them to the company's configured ASP. """
        for move in self:
            document = move._l10n_om_edi_get_or_create_document()
            document._action_submit()

    def action_l10n_om_edi_view_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "Oman E-Invoicing Documents",
            'res_model': 'l10n.om.edi.document',
            'view_mode': 'list,form',
            'domain': [('move_id', '=', self.id)],
        }
