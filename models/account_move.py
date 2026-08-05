# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class AccountMove(models.Model):
    """ Adds the UAE-specific special-scenario flags, transaction type code, and PINT AE import
    recognition to `account.move`. """
    _inherit = 'account.move'

    # -------------------------------------------------------------------------
    # The 8 special scenarios (UAE Electronic Invoicing Guidelines v1.1, s10.4), assembled into the
    # "Invoice transaction type code" bitstring required by the Mandatory Fields spec (s4.1, field 5).
    #
    # 7 of the 8 are left as plain, manually-set booleans rather than auto-detected: nothing in the
    # Ministry's documents defines an unambiguous rule for e.g. "this is a Free Zone supply" or "this
    # is a disclosed agent billing arrangement" that could be derived reliably from existing Odoo data
    # (fiscal position, product category, etc.) without risking a wrong guess on a compliance-relevant
    # field. Only "Exports" (buyer outside the UAE) has an unambiguous, purely geographic definition
    # (Guidelines s10.4, row 8: "Buyer country code <> AE") and is therefore computed automatically.
    # -------------------------------------------------------------------------

    l10n_ae_flag_free_zone = fields.Boolean(
        string="UAE: Free Zone Supply",
        help="Tick if this transaction involves a Free Zone entity (supplier, buyer, or beneficiary) "
             "or the supply itself takes place within/from a Free Zone. See UAE Electronic Invoicing "
             "Guidelines s10.4, scenario 1.",
    )
    l10n_ae_flag_deemed_supply = fields.Boolean(
        string="UAE: Deemed Supply",
        help="Tick if this is a supply deemed to be a Taxable Supply for VAT purposes (e.g. no-"
             "consideration supplies, or goods/services owned at the date of VAT deregistration). See "
             "UAE Electronic Invoicing Guidelines s10.4, scenario 2.",
    )
    l10n_ae_flag_margin_scheme = fields.Boolean(
        string="UAE: Margin Scheme",
        help="Tick if VAT is calculated only on the supplier's margin (e.g. qualifying second-hand "
             "goods). The displayed VAT amount is forced to 0 even though the tax category block is "
             "still present. See UAE Electronic Invoicing Guidelines s10.4, scenario 3.",
    )
    l10n_ae_flag_summary_invoice = fields.Boolean(
        string="UAE: Summary Invoice",
        help="Tick if multiple transactions with the same customer over a defined period are "
             "consolidated onto this single summary invoice. See UAE Electronic Invoicing Guidelines "
             "s10.4, scenario 4.",
    )
    l10n_ae_flag_continuous_supply = fields.Boolean(
        string="UAE: Continuous Supply",
        help="Tick if this supply is provided on an ongoing/recurring basis or includes periodic "
             "invoicing (e.g. retainers, milestone billing). See UAE Electronic Invoicing Guidelines "
             "s10.4, scenario 5.",
    )
    l10n_ae_flag_agent_billing = fields.Boolean(
        string="UAE: Disclosed Agent Billing",
        help="Tick if a Person is acting as a disclosed agent on behalf of a named principal, issuing "
             "this invoice on the principal's behalf. Does not apply to undisclosed agents. See UAE "
             "Electronic Invoicing Guidelines s10.4, scenario 6.",
    )
    l10n_ae_flag_ecommerce = fields.Boolean(
        string="UAE: Supply through e-Commerce",
        help="Tick if this is an electronic commerce supply through an Electronic Commerce Medium as "
             "defined by Ministerial Decision No. 26 of 2023. See UAE Electronic Invoicing Guidelines "
             "s10.4, scenario 7.",
    )
    l10n_ae_flag_export = fields.Boolean(
        string="UAE: Export",
        compute='_compute_l10n_ae_flag_export',
        store=True,
        help="Automatically set when the buyer is established outside the UAE. See UAE Electronic "
             "Invoicing Guidelines s10.4, scenario 8.",
    )

    l10n_ae_beneficiary_partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="UAE: Ultimate Beneficiary",
        help="Only relevant for the Free Zone scenario: the Person that ultimately uses, consumes, or "
             "owns what is being supplied, when different from the invoiced buyer. See UAE Electronic "
             "Invoicing Guidelines s10.4, scenario 1.",
    )
    l10n_ae_reverse_charge_goods_type = fields.Selection(
        selection=[
            ('electronic_devices', "Electronic devices"),
            ('precious_metals_stones', "Precious metals and precious stones"),
            ('crude_refined_oil', "Crude or refined oil"),
            ('natural_gas', "Unprocessed or processed natural gas"),
            ('pure_hydrocarbons', "Pure hydrocarbons"),
            ('metal_scrap', "Metal scrap trading"),
        ],
        string="UAE: Reverse Charge Goods Type",
        help="Required reference on the Electronic Invoice when the domestic (UAE-registrant-to-"
             "registrant) reverse charge mechanism tax category is used. See UAE Electronic Invoicing "
             "Guidelines s10.5.1.",
    )
    l10n_ae_vat_point_date = fields.Date(
        string="UAE: VAT Point Date",
        help="Date of supply, only needed if different from the Invoice Issue Date. See UAE "
             "Electronic Invoice Mandatory Fields spec, Constraint #23.",
    )

    l10n_ae_transaction_type_code = fields.Char(
        string="UAE: Invoice Transaction Type Code",
        compute='_compute_l10n_ae_transaction_type_code',
        help="8-character flag string (Free Zone, Deemed Supply, Margin Scheme, Summary Invoice, "
             "Continuous Supply, Disclosed Agent Billing, Supply through e-Commerce, Exports), as "
             "defined by the UAE Electronic Invoice Mandatory Fields spec, s4.1, field 5.",
    )

    @api.depends('partner_id.commercial_partner_id.country_code', 'company_id')
    def _compute_l10n_ae_flag_export(self):
        """ Set the Export flag automatically when the buyer is established outside the UAE. """
        for move in self:
            move.l10n_ae_flag_export = bool(
                move.partner_id.commercial_partner_id.country_code
                and move.partner_id.commercial_partner_id.country_code != 'AE'
            )

    @api.depends(
        'l10n_ae_flag_free_zone', 'l10n_ae_flag_deemed_supply', 'l10n_ae_flag_margin_scheme',
        'l10n_ae_flag_summary_invoice', 'l10n_ae_flag_continuous_supply', 'l10n_ae_flag_agent_billing',
        'l10n_ae_flag_ecommerce', 'l10n_ae_flag_export',
    )
    def _compute_l10n_ae_transaction_type_code(self):
        """ Assemble the 8 special-scenario booleans into the 8-character transaction type code
        bitstring, in the field order fixed by the Mandatory Fields spec (s4.1, field 5). """
        for move in self:
            move.l10n_ae_transaction_type_code = ''.join('1' if flag else '0' for flag in (
                move.l10n_ae_flag_free_zone,
                move.l10n_ae_flag_deemed_supply,
                move.l10n_ae_flag_margin_scheme,
                move.l10n_ae_flag_summary_invoice,
                move.l10n_ae_flag_continuous_supply,
                move.l10n_ae_flag_agent_billing,
                move.l10n_ae_flag_ecommerce,
                move.l10n_ae_flag_export,
            ))

    def _get_import_file_type(self, file_data):
        """ Identify PINT AE files (billing and self-billing). """
        # EXTENDS 'account_edi_ubl_cii'
        tree = file_data['xml_tree']
        if tree is not None and tree.findtext('{*}CustomizationID') in (
            'urn:peppol:pint:billing-1@ae-1',
            'urn:peppol:pint:selfbilling-1@ae-1',
        ):
            return 'account.edi.xml.pint_ae'

        return super()._get_import_file_type(file_data)
