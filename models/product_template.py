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
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    """ Extends product template to hold Oman HS code (IBT-158) and ISIC code (BTOM-033)
    for Oman e-invoicing compliance. """
    _inherit = 'product.template'

    l10n_om_hs_code = fields.Char(
        string="Oman HS Code",
        size=12,
        copy=False,
        help="12-digit Oman Harmonized System code (IBT-158) mandatory for B2B Goods lines.",
    )
    l10n_om_isic_code = fields.Char(
        string="Oman ISIC Code",
        size=6,
        copy=False,
        help="6-digit Oman Industrial Classification Code (BTOM-033). Overrides the company default if set.",
    )

    @api.constrains('l10n_om_hs_code')
    def _check_l10n_om_hs_code(self):
        for product in self:
            if product.l10n_om_hs_code:
                code = product.l10n_om_hs_code.strip()
                if not (code.isdigit() and len(code) == 12):
                    raise ValidationError(_(
                        "Oman HS Code must be exactly 12 digits for product '%s'.", product.display_name
                    ))

    @api.constrains('l10n_om_isic_code')
    def _check_l10n_om_isic_code(self):
        for product in self:
            if product.l10n_om_isic_code:
                code = product.l10n_om_isic_code.strip()
                if not (code.isdigit() and len(code) == 6):
                    raise ValidationError(_(
                        "Oman ISIC Code must be exactly 6 digits for product '%s'.", product.display_name
                    ))
