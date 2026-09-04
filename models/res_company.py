# -*- coding: utf-8 -*-
from odoo import fields, models

from odoo.addons.l10n_ae_aigentrix.lib.aigentrix_client import AigentrixClient


class ResCompany(models.Model):
    """Stores this company's Aigentrix External Gateway credentials (Section 1/2 of the API
    guide) and exposes the single seam (`_l10n_ae_aigentrix_get_client`) the connector is
    created through."""
    _inherit = 'res.company'

    l10n_ae_aigentrix_base_url = fields.Char(
        string="Aigentrix Base URL", default="http://localhost:8095",
        help="Root URL of the Aigentrix External Gateway (Section 2 'baseUrl'), e.g. "
             "http://localhost:8095. All endpoints are called under "
             "<Base URL>/external/api/v1.",
    )
    l10n_ae_aigentrix_api_key = fields.Char(
        string="Aigentrix API Key", groups='base.group_system',
        help="Sent as the 'X-API-KEY' header on every call (Section 1, Authentication).",
    )
    l10n_ae_aigentrix_company_id = fields.Integer(
        string="Aigentrix Company ID",
        help="Your Aigentrix 'companyId' (Section 2), required on every eInvoiceEntry call.",
    )
    l10n_ae_aigentrix_peppol_participant_id = fields.Char(
        string="Peppol Supplier Participant ID",
        help="This company's Peppol participant ID, sent as 'supplierParticipantId', e.g. "
             "0088:1234567890123 (Section 5.1).",
    )

    def _l10n_ae_aigentrix_get_client(self):
        """Return an `AigentrixClient` configured with this company's credentials."""
        self.ensure_one()
        return AigentrixClient(
            base_url=self.l10n_ae_aigentrix_base_url,
            api_key=self.l10n_ae_aigentrix_api_key,
        )
