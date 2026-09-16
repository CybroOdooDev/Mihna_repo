# -*- coding: utf-8 -*-
#############################################################################
#    A part of OpenHRMS Project <https://www.openhrms.com>
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2025-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
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
from odoo import models


class PortalEntry(models.Model):
    """Inherits portal.entry to conditionally show the employee verification
    card in the portal dashboard for verification agents."""
    _inherit = 'portal.entry'

    def _filter_visible_portal_cards(self):
        visible_entries = super()._filter_visible_portal_cards()
        entry = self.env.ref('employee_background.portal_employee_verification', raise_if_not_found=False)
        if entry and entry in self:
            partner = self.env.user.partner_id
            if partner.verification_agent or self.env['employee.verification'].sudo().search_count([
                ('agency_id', '=', partner.id),
                ('state', '=', 'assign')
            ]):
                visible_entries |= entry
        return visible_entries
