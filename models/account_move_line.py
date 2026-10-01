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


class AccountMoveLine(models.Model):
    """ Extends invoice lines to store line-level Oman classification fields:
    HS code (IBT-158) and ISIC code (BTOM-033). """
    _inherit = 'account.move.line'

    l10n_om_hs_code = fields.Char(
        string="Oman HS Code",
        compute='_compute_l10n_om_classification_codes',
        store=True,
        readonly=False,
        copy=False,
        size=12,
        help="12-digit Oman Harmonized System code (IBT-158) mandatory for B2B Goods lines.",
    )
    l10n_om_isic_code = fields.Char(
        string="Oman ISIC Code",
        compute='_compute_l10n_om_classification_codes',
        store=True,
        readonly=False,
        copy=False,
        size=6,
        help="6-digit Oman Industrial Classification Code (BTOM-033).",
    )

    @api.depends('product_id', 'company_id')
    def _compute_l10n_om_classification_codes(self):
        for line in self:
            if line.product_id:
                line.l10n_om_hs_code = line.product_id.l10n_om_hs_code or False
                line.l10n_om_isic_code = (
                    line.product_id.l10n_om_isic_code
                    or line.company_id.l10n_om_default_isic_code
                    or False
                )
            else:
                line.l10n_om_hs_code = False
                line.l10n_om_isic_code = line.company_id.l10n_om_default_isic_code or False

    @api.constrains('l10n_om_hs_code')
    def _check_l10n_om_hs_code(self):
        for line in self:
            if line.l10n_om_hs_code:
                code = line.l10n_om_hs_code.strip()
                if not (code.isdigit() and len(code) == 12):
                    raise ValidationError(_(
                        "Line '%s': Oman HS Code must be exactly 12 digits.", line.name or line.product_id.name or '/'
                    ))

    @api.constrains('l10n_om_isic_code')
    def _check_l10n_om_isic_code(self):
        for line in self:
            if line.l10n_om_isic_code:
                code = line.l10n_om_isic_code.strip()
                if not (code.isdigit() and len(code) == 6):
                    raise ValidationError(_(
                        "Line '%s': Oman ISIC Code must be exactly 6 digits.", line.name or line.product_id.name or '/'
                    ))
