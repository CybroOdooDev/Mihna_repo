# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.addons.account_edi_ubl_cii.models.account_edi_common import EAS_MAPPING

# UAE Tax Identification Number (TIN), Peppol e-address scheme (EAS/ICD) code 0235.
#
# Odoo core already registers `EAS_MAPPING['AE'] = {'0235': 'vat'}` (account_edi_common.py) - i.e. by
# default it would use the partner's VAT/TRN field directly as the Peppol Participant Identifier.
# That is NOT correct for the UAE e-invoicing mandate: per the UAE Electronic Invoicing Guidelines
# (s3, "Participant Identifier (or End Point ID)") and the Mandatory Fields spec (Highlights, field
# #11 "Seller electronic address"), the identifier is `0235:` followed by the 10-digit Tax
# Identification Number (TIN) - the first 10 digits of the (15-digit) Tax Registration Number (TRN) -
# NOT the full TRN itself, and NOT necessarily derived from the VAT TRN at all: a Person's TIN can
# come from a Corporate Tax registration distinct from their VAT TRN (Mandatory Fields, Highlights).
# So this deliberately overrides the stock mapping to point at a dedicated `l10n_ae_tin` field instead
# of `vat`, rather than trying to auto-derive it by truncating `vat`.
EAS_MAPPING['AE'] = {'0235': 'l10n_ae_tin'}

_check_l10n_ae_tin_re = re.compile(r"^\d{10}$")


class ResPartner(models.Model):
    """ Adds the UAE Tax Identification Number (TIN) and legal registration fields used to build a
    Person's Peppol Participant Identifier and to populate PINT AE invoices. """
    _inherit = 'res.partner'

    invoice_edi_format = fields.Selection(selection_add=[('pint_ae', "United Arab Emirates (Peppol PINT AE)")])

    l10n_ae_tin = fields.Char(
        string="Tax Identification Number (TIN)",
        help="10-digit Tax Identification Number issued by the Federal Tax Authority - the first 10 "
             "digits of a Tax Registration Number (TRN). Used to build this Person's Peppol "
             "Participant Identifier (`0235:<TIN>`) for UAE Electronic Invoicing. Not necessarily the "
             "same as the first 10 digits of the VAT TRN entered in the 'Tax ID' field above - see "
             "the UAE Electronic Invoicing Guidelines, Highlights section.",
    )
    l10n_ae_legal_registration_type = fields.Selection(
        selection=[
            ('TL', "Trade License"),
            ('EID', "Emirates ID"),
            ('PAS', "Passport"),
            ('CD', "Cabinet Decision"),
        ],
        string="Legal Registration Type (UAE e-Invoicing)",
        help="Nature of the legal registration number below, as required by the UAE Electronic "
             "Invoice Mandatory Fields spec (s4.1, fields #14/#25).",
    )
    l10n_ae_legal_registration_number = fields.Char(
        string="Legal Registration Number (UAE e-Invoicing)",
        help="Trade license / Emirates ID / passport / Cabinet Decision reference identifying this "
             "Person as a legal entity, per the UAE Electronic Invoice Mandatory Fields spec (s4.1, "
             "fields #13/#24).",
    )

    @api.depends('l10n_ae_tin')
    def _compute_peppol_endpoint(self):
        # EXTENDS 'account_edi_ubl_cii'
        #
        # Core's own `_compute_peppol_endpoint` is only decorated `@api.depends('peppol_eas')` - it
        # recomputes when the EAS *code* changes, not when the field EAS_MAPPING points the code at
        # changes value. Since this module repoints AE's mapping at `l10n_ae_tin` (see EAS_MAPPING
        # override above) rather than the already-present `vat`, a partner that gets its TIN filled in
        # *after* its country/EAS has already settled on '0235' would otherwise be left with a blank
        # `peppol_endpoint` until something else happens to toggle `peppol_eas` again. Odoo merges
        # `@api.depends` lists by method name across the inheritance chain, so re-declaring this same
        # compute here with an extra dependency - not overriding its logic - is enough to fix that.
        super()._compute_peppol_endpoint()

    @api.constrains('l10n_ae_tin')
    def _check_l10n_ae_tin(self):
        """ Reject a TIN that isn't exactly 10 digits. """
        for partner in self:
            if partner.l10n_ae_tin and not _check_l10n_ae_tin_re.match(partner.l10n_ae_tin):
                raise ValidationError(_(
                    "The UAE Tax Identification Number (TIN) of %(partner)s must be exactly 10 digits.",
                    partner=partner.display_name,
                ))

    def _get_edi_builder(self, invoice_edi_format):
        """ Return the PINT AE XML builder for the 'pint_ae' format. """
        # EXTENDS 'account_edi_ubl_cii'
        if invoice_edi_format == 'pint_ae':
            return self.env['account.edi.xml.pint_ae']
        return super()._get_edi_builder(invoice_edi_format)

    def _get_ubl_cii_formats_info(self):
        """ Register the 'pint_ae' format as UAE-only and not reachable via an Odoo-operated Peppol
        access point. """
        # EXTENDS 'account_edi_ubl_cii'
        formats_info = super()._get_ubl_cii_formats_info()
        # 'on_peppol' is False: PINT AE is a valid Peppol format, but there is no Odoo-operated access
        # point for the UAE - reaching the network always requires an Accredited Service Provider
        # (ASP), see l10n_ae_edi. Revisit once such an integration is live.
        formats_info['pint_ae'] = {'countries': ['AE'], 'on_peppol': False}
        return formats_info

    @api.model
    def _commercial_fields(self):
        """ Propagate the UAE TIN and legal registration fields from a commercial entity to its
        contacts, alongside Odoo's other commercial fields (e.g. `vat`). """
        return super()._commercial_fields() + [
            'l10n_ae_tin', 'l10n_ae_legal_registration_type', 'l10n_ae_legal_registration_number',
        ]
