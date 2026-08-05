# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class ResCompany(models.Model):
    """ Exposes the company's UAE Tax Identification Number (TIN) and legal registration details,
    related through to `partner_id` so they stay in sync with the company's contact record. """
    _inherit = 'res.company'

    l10n_ae_tin = fields.Char(related='partner_id.l10n_ae_tin', readonly=False)
    l10n_ae_legal_registration_type = fields.Selection(related='partner_id.l10n_ae_legal_registration_type', readonly=False)
    l10n_ae_legal_registration_number = fields.Char(related='partner_id.l10n_ae_legal_registration_number', readonly=False)
