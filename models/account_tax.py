# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountTax(models.Model):
    """Lets the accountant declare, per tax, which Aigentrix VAT category (Section 6.6
    taxCategory: S/Z/E/O) that tax represents on an e-invoice line - Odoo's own tax record has
    no such classification, so this module doesn't infer/guess it from the tax amount."""
    _inherit = 'account.tax'

    l10n_ae_aigentrix_tax_category = fields.Selection(
        selection=[
            ('S', "S - Standard Rate"),
            ('Z', "Z - Zero-Rated"),
            ('E', "E - Exempt from VAT"),
            ('O', "O - Outside VAT Scope"),
        ],
        string="Aigentrix VAT Category",
        default='S',
        help="Peppol tax category code sent as 'taxCategory' on every invoice line using this "
             "tax (Section 6.6).",
    )
    l10n_ae_aigentrix_vat_exempt_reason_code = fields.Char(
        string="Aigentrix VAT Exempt Reason Code",
        help="Sent as 'vatExemptReasonCode' (IBT-186). MANDATORY when the Aigentrix VAT Category "
             "above is 'E' (Exempt) - rule [ibr-167-ae] otherwise rejects the submission "
             "(Section 7.2).",
    )
    l10n_ae_aigentrix_vat_exempt_reason_text = fields.Char(
        string="Aigentrix VAT Exempt Reason (Text)",
        help="Sent as 'vatExemptReasonText' - human-readable exemption reason description.",
    )

    @api.constrains('l10n_ae_aigentrix_tax_category', 'l10n_ae_aigentrix_vat_exempt_reason_code')
    def _check_l10n_ae_aigentrix_vat_exempt_reason_code(self):
        """Enforce rule [ibr-167-ae] (Section 7.2/10) at configuration time, rather than only
        discovering it when the Aigentrix API rejects a submission."""
        for tax in self:
            if tax.l10n_ae_aigentrix_tax_category == 'E' and not tax.l10n_ae_aigentrix_vat_exempt_reason_code:
                raise ValidationError(_(
                    "[ibr-167-ae] %(tax)s: the Aigentrix VAT Exempt Reason Code is mandatory when "
                    "the Aigentrix VAT Category is 'E' (Exempt).", tax=tax.display_name,
                ))
