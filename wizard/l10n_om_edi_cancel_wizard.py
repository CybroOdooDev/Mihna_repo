# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, _
from odoo.exceptions import UserError


class L10nOmEdiCancelWizard(models.TransientModel):
    _name = 'l10n.om.edi.cancel.wizard'
    _description = "Oman E-Invoicing Cancellation Wizard"

    # NOTE: Oman's exact cancellation-vs-credit-note rules were not detailed in the regulatory brief
    # this module was built against. This wizard is a placeholder capturing a reason and forwarding the
    # cancellation request to the ASP; revisit once the Oman Tax Authority's rules are confirmed.
    document_id = fields.Many2one(comodel_name='l10n.om.edi.document', string="Document", required=True, readonly=True)
    reason = fields.Char(string="Cancellation Reason", required=True)

    def button_confirm_cancel(self):
        self.ensure_one()
        if not self.reason.strip():
            raise UserError(_("You must provide a reason for cancelling this document."))

        document = self.document_id
        connector = document.company_id._l10n_om_edi_get_connector()
        if connector.cancel(document.asp_reference, self.reason):
            document.l10n_om_edi_state = 'cancelled'
