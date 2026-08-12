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
import uuid

from odoo import fields, models


class ResPartner(models.Model):
    """ Tracks whether this partner has been synced to ConvergeX's Customer Master, and its last
    known PEPPOL network status there. """
    _inherit = 'res.partner'

    l10n_om_convergex_erp_uuid = fields.Char(
        string="ConvergeX ERP UUID", copy=False,
        help="The erp_uuid this partner is synced to ConvergeX's Customer Master under - this "
             "module uses the partner's own database id, converted to text.",
    )
    l10n_om_convergex_peppol_status = fields.Char(
        string="ConvergeX PEPPOL Status", copy=False, readonly=True,
        help="This partner's peppol_network_status as last reported by ConvergeX's Customer Master "
             "sync response (e.g. 'registered', 'not_registered') - informational only.",
    )

    def _l10n_om_convergex_get_customer_payload(self):
        """ Build the Customer Master sync payload ConvergeX expects for this partner (the invoice
        buyer), from whatever Odoo already has on the commercial partner.

        ConvergeX's own Customer Master sync docs say `erp_uuid` can be any string (their example
        is "ERP-CUST-0001") - but the *create invoice* endpoint's live validator rejects
        `customer_erp_uuid` values that aren't actually UUID-shaped. To satisfy both, a real UUID4
        is generated and persisted here the first time a partner is synced, rather than using the
        partner's own (non-UUID) database id.
        """
        self.ensure_one()
        partner = self.commercial_partner_id
        existing = partner.l10n_om_convergex_erp_uuid
        is_valid_uuid = False
        if isinstance(existing, str):
            try:
                uuid.UUID(existing)
                is_valid_uuid = True
            except ValueError:
                pass
        if not is_valid_uuid:
            # Empty (Odoo represents that as False, not None or '' - uuid.UUID(False) raises
            # AttributeError, not TypeError/ValueError, since it unconditionally calls .replace()
            # on its argument before validating its type, which the isinstance check above avoids
            # relying on entirely), or a leftover non-UUID value from before this validation
            # existed (e.g. the partner's own database id, echoed back and saved by an earlier
            # failed submission) - either way, replace it with a real UUID4.
            partner.l10n_om_convergex_erp_uuid = str(uuid.uuid4())
        # 'l10n_om_cr_number' (the Oman CR Number) is only present when 'l10n_om_edi' is also
        # installed - this module doesn't depend on it, so fall back to the VAT number when absent.
        cr_number = getattr(partner, 'l10n_om_cr_number', False)
        return {
            'erp_uuid': partner.l10n_om_convergex_erp_uuid,
            'customer_name': partner.name,
            'tax_id': partner.vat or '',
            'registration_number': cr_number or partner.vat or '',
            'email': partner.email or '',
            'phone': partner.phone or '',
            'website': partner.website or '',
            'address_line1': partner.street or '',
            'address_line2': partner.street2 or '',
            'city': partner.city or '',
            'postal_code': partner.zip or '',
            'country': partner.country_id.name or '',
            'country_code': partner.country_id.code or '',
            'endpoint_scheme': '0248',
            'endpoint_id': partner.vat or '',
            'is_active': True,
        }
