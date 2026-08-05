# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class AccountMove(models.Model):
    """ Adds the UAE ASP submission-tracking fields and actions to `account.move`. """
    _inherit = 'account.move'

    l10n_ae_edi_document_ids = fields.One2many(
        comodel_name='l10n.ae.edi.document', inverse_name='move_id', string="UAE E-Invoicing Documents")
    l10n_ae_edi_document_count = fields.Integer(compute='_compute_l10n_ae_edi_document_count')
    l10n_ae_edi_state = fields.Selection(related='l10n_ae_edi_document_ids.l10n_ae_edi_state', string="UAE E-Invoicing State")

    @api.depends('l10n_ae_edi_document_ids')
    def _compute_l10n_ae_edi_document_count(self):
        """ Count the UAE E-Invoicing documents linked to this move, for the stat button. """
        for move in self:
            move.l10n_ae_edi_document_count = len(move.l10n_ae_edi_document_ids)

    def _l10n_ae_edi_get_or_create_document(self):
        """ Return this move's active (not rejected/cancelled) UAE E-Invoicing document, creating one
        if none exists yet. """
        self.ensure_one()
        document = self.l10n_ae_edi_document_ids.filtered(lambda d: d.l10n_ae_edi_state not in ('rejected', 'cancelled'))[:1]
        if not document:
            document = self.env['l10n.ae.edi.document'].create({
                'move_id': self.id,
                'company_id': self.company_id.id,
            })
        return document

    def action_l10n_ae_edi_submit(self):
        """ Generate the PINT AE XML and submit it to the company's configured ASP. """
        for move in self:
            document = move._l10n_ae_edi_get_or_create_document()
            document._action_submit()

    def action_l10n_ae_edi_view_documents(self):
        """ Open the list of UAE E-Invoicing documents linked to this move. """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "UAE E-Invoicing Documents",
            'res_model': 'l10n.ae.edi.document',
            'view_mode': 'list,form',
            'domain': [('move_id', '=', self.id)],
        }
