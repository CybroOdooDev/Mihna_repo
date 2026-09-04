# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_ae_aigentrix_peppol_participant_id = fields.Char(
        string="Peppol Customer Participant ID",
        help="This partner's Peppol participant ID, sent as 'customerParticipantId' when they "
             "are the buyer on an e-invoice, e.g. 0088:9876543210987 (Section 5.1).",
    )
