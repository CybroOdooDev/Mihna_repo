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
    """ Exposes the company's ConvergeX credentials on the Accounting settings screen. """
    _inherit = 'res.config.settings'

    l10n_om_convergex_base_url = fields.Char(related='company_id.l10n_om_convergex_base_url', readonly=False)
    l10n_om_convergex_client_id = fields.Char(related='company_id.l10n_om_convergex_client_id', readonly=False)
    l10n_om_convergex_client_secret = fields.Char(related='company_id.l10n_om_convergex_client_secret', readonly=False)
    l10n_om_convergex_invoice_type_uuid = fields.Char(related='company_id.l10n_om_convergex_invoice_type_uuid',
                                                      readonly=False)
    l10n_om_convergex_credit_note_type_uuid = fields.Char(related='company_id.l10n_om_convergex_credit_note_type_uuid',
                                                          readonly=False)

    def action_l10n_om_convergex_test_connection(self):
        """ Fetch a JWT token with the currently-saved Client ID/Secret to confirm they're valid.
        Raises a clear UserError (via the client's shared request handling) on failure; on success,
        shows a plain confirmation - no invoice or customer data is touched either way. """
        self.company_id._l10n_om_convergex_get_client().test_connection()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Connection successful"),
                'message': _("ConvergeX accepted the configured Client ID and Client Secret."),
                'type': 'success',
                'sticky': False,
            },
        }
