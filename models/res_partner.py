#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2026-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
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
import re

from odoo import models

_check_vat_om_re = re.compile(r"^OM\d{10}$")

# Flick's own EAS scheme code for the Oman VAT identifier (0248) - the same code
# 'l10n_om_edi' registers on 'peppol_eas' (account_edi_ubl_cii). This module doesn't depend on
# that, so it's hardcoded here rather than read from a 'peppol_eas' field that may not exist.
_OMAN_VAT_EAS = "0248"


class ResPartner(models.Model):
    """ Format-only Oman VAT check, and the Flick 'party' JSON builder shared by the seller
    (company) and buyer (invoice partner) sides of a submission. """
    _inherit = 'res.partner'

    def check_vat_om(self, vat):
        """ Format-only check: 'OM' followed by 10 digits.

        Wired into base_vat's country-specific check_vat_<code> mechanism, so a bad Oman VAT is
        caught when the partner is saved in Odoo, rather than only surfacing later when Flick
        Network rejects it at submission.
        """
        return bool(_check_vat_om_re.match(vat))

    def _l10n_om_flick_get_party_payload(self):
        """ Build the 'issuing_party'/'receiving_party' JSON object Flick expects for this partner
        (either the seller's or the buyer's commercial partner). """
        self.ensure_one()
        partner = self.commercial_partner_id
        peppol_id = f"{_OMAN_VAT_EAS}:{partner.vat}" if partner.vat else None
        # 'l10n_om_address_line3'/'l10n_om_cr_number' only exist when 'l10n_om_edi' is also
        # installed - this module doesn't depend on it, so fall back to no third address line/no
        # registration identifier when absent.
        address_line3 = getattr(partner, 'l10n_om_address_line3', False)
        cr_number = getattr(partner, 'l10n_om_cr_number', False)
        # IBT-030/047, "0..n" array of registration identifiers - Odoo has no scheme-coded registry
        # of identifier types, so only the Oman CR (Commercial Registration) number is sent, when
        # available.
        identifiers = [{'type': 'CR', 'value': cr_number}] if cr_number else []
        return {
            'legal_name': partner.name,
            'trade_name': partner.name,
            'peppol_id': peppol_id,
            'vat_number': partner.vat,
            'street_address': partner.street,
            'additional_street_address': partner.street2,
            'additional_address_lines': [address_line3] if address_line3 else [],
            'city_address': partner.city,
            'postal_zone': partner.zip,
            # One of Oman's 4 free zones (SHRFZ/SEZAD/SLLFZ/AFZ) or "MO" for Mainland Oman - Odoo has
            # no field for free-zone registration, so default to "MO" (true for most businesses).
            'country_subdivision_code': "MO",
            'country_code': partner.country_id.code,
            'identifiers': identifiers,
            'contact_name': partner.name,
            'contact_telephone': partner.phone,
            'contact_email': partner.email,
        }
