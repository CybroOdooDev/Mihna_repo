# -*- coding: utf-8 -*-
from odoo import fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_ae_aigentrix_base_url = fields.Char(related='company_id.l10n_ae_aigentrix_base_url', readonly=False)
    l10n_ae_aigentrix_api_key = fields.Char(related='company_id.l10n_ae_aigentrix_api_key', readonly=False)
    l10n_ae_aigentrix_company_id = fields.Integer(related='company_id.l10n_ae_aigentrix_company_id', readonly=False)
    l10n_ae_aigentrix_peppol_participant_id = fields.Char(
        related='company_id.l10n_ae_aigentrix_peppol_participant_id', readonly=False)

    def action_l10n_ae_aigentrix_test_connection(self):
        """Confirm the configured API Key/Base URL work, using GET /eInvoiceEntry (Section 4.3) -
        the only endpoint documented as side-effect-free with no path parameter required. Its
        'startDate'/'endDate' query parameters are documented as required, so today's date is
        sent for both, together with perPage=1 to keep the call cheap."""
        self.ensure_one()
        client = self.company_id._l10n_ae_aigentrix_get_client()
        today = fields.Date.context_today(self).isoformat()
        client.list_entries({
            'companyId': self.l10n_ae_aigentrix_company_id or None,
            'startDate': today,
            'endDate': today,
            'perPage': 1,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Connection Successful"),
                'message': _("Successfully connected to the Aigentrix E-Invoice API."),
                'type': 'success',
                'sticky': False,
            }
        }
