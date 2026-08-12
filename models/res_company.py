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
from odoo import fields, models

from odoo.addons.l10n_om_convergex.lib.convergex_client import ConvergeXClient


class ResCompany(models.Model):
    """ Stores this company's ConvergeX API credentials and exposes the single seam
    (`_l10n_om_convergex_get_client`) the connector is created through. """
    _inherit = 'res.company'

    l10n_om_convergex_base_url = fields.Char(string="ConvergeX API Base URL", default="https://convergex.biz")
    l10n_om_convergex_client_id = fields.Char(string="ConvergeX Client ID")
    l10n_om_convergex_client_secret = fields.Char(string="ConvergeX Client Secret", groups='base.group_system')
    l10n_om_convergex_invoice_type_uuid = fields.Char(
        string="ConvergeX Standard Invoice Type UUID",
        default="92a163ea-b2ba-40b8-8ae1-670edfd975e4",
        help="ConvergeX requires a valid, active invoice_type UUID on every create call - it is "
             "not optional in practice, despite their own Postman examples suggesting otherwise. "
             "The default here is ConvergeX's documented 'Standard' type; confirm it against your "
             "own account's GET /api/customer/invoice-types/ if invoice creation still fails with "
             "an invalid-UUID error.",
    )
    l10n_om_convergex_credit_note_type_uuid = fields.Char(
        string="ConvergeX Credit Note Type UUID",
        default="42596eac-a3b6-40b3-bfbf-67a008b2fc6b",
        help="Same as the Standard Invoice Type UUID above, but for credit notes. ConvergeX's "
             "documented default is their 'Credit Note (OTA)' type.",
    )

    def _l10n_om_convergex_get_client(self):
        """ Return a `ConvergeXClient` configured with this company's credentials. """
        self.ensure_one()
        return ConvergeXClient(
            base_url=self.l10n_om_convergex_base_url,
            client_id=self.l10n_om_convergex_client_id,
            client_secret=self.l10n_om_convergex_client_secret,
        )
