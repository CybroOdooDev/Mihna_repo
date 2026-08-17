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
from odoo.addons.l10n_om_flick.lib.flick_client import FlickClient


class ResCompany(models.Model):
    """ Stores this company's Flick Network API credentials and exposes the single seam
    (`_l10n_om_flick_get_client`) the connector is created through. """
    _inherit = 'res.company'

    l10n_om_flick_base_url = fields.Char(
        string="Flick API Base URL", default="https://sb-om-api.flick.network",
        help="Flick Network's sandbox server. Their production host was not published at the "
             "time this module was written - replace with the production URL once Flick confirms "
             "it.",
    )
    l10n_om_flick_api_key = fields.Char(
        string="Flick API Key", groups='base.group_system',
        help="Static API key, sent as the 'X-Flick-Auth-Key' header on every call.",
    )
    l10n_om_flick_participant_id = fields.Char(
        string="Flick Participant ID",
        help="This company's Flick Peppol 'Participant' id. Register as a Participant via the "
             "Flick dashboard/API first (POST /v1/participants) - no document can be submitted "
             "before that is done.",
    )

    def _l10n_om_flick_get_client(self):
        """ Return a `FlickClient` configured with this company's credentials. """
        self.ensure_one()
        return FlickClient(
            base_url=self.l10n_om_flick_base_url,
            api_key=self.l10n_om_flick_api_key,
            participant_id=self.l10n_om_flick_participant_id,
        )
