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
from odoo import fields, models, _


class ResConfigSettings(models.TransientModel):
    """ Exposes the company's Flick Network credentials on the Accounting settings screen. """
    _inherit = 'res.config.settings'

    l10n_om_flick_base_url = fields.Char(related='company_id.l10n_om_flick_base_url', readonly=False)
    l10n_om_flick_api_key = fields.Char(related='company_id.l10n_om_flick_api_key', readonly=False)
    l10n_om_flick_participant_id = fields.Char(related='company_id.l10n_om_flick_participant_id',
                                                readonly=False)

    def action_l10n_om_flick_test_connection(self):
        """ Call Flick's GET /v1/auth/verify with the currently-saved API Key to confirm it's
        valid. Raises a clear UserError (via the client's shared request handling) on failure; on
        success, shows a plain confirmation - no document data is touched either way. """
        self.company_id._l10n_om_flick_get_client().test_connection()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Connection successful"),
                'message': _("Flick Network accepted the configured API Key."),
                'type': 'success',
                'sticky': False,
            },
        }
