# Part of Odoo. See LICENSE file for full copyright and licensing details.
from typing import Literal

from odoo import models, _


class AccountEdiXmlPint_Ae(models.AbstractModel):
    """ Builds the PINT AE Invoice/CreditNote XML (Corners 1-4) for a posted `account.move`.

    * PINT Official documentation: https://docs.peppol.eu/poac/pint/pint/
    * The UAE Electronic Invoicing System uses a 5-corner Peppol model (UAE Electronic Invoicing
      Guidelines v1.1, s5.1). Unlike Oman's programme, the UAE Ministry of Finance's documentation
      does not describe any separate "Tax Data Document" built by the taxpayer's own system: Corner 2
      (the supplier's ASP) reports Tax Data to Corner 5 (the Federal Tax Authority) itself, derived
      from this same Electronic Invoice XML - so this builder only produces one document, not two.
    * No QR code or barcode is part of the format (Guidelines s5.3) - this builder does not add one.
    """
    _name = 'account.edi.xml.pint_ae'
    _inherit = ["account.edi.xml.ubl_bis3"]
    _description = "UAE implementation of Peppol International (PINT) model for Billing"

    def _export_invoice_filename(self, invoice):
        # EXTENDS account_edi_ubl_cii
        return f"{invoice.name.replace('/', '_')}_pint_ae.xml"

    def _get_customization_id(self, process_type: Literal['billing', 'selfbilling'] = 'billing'):
        # EXTENDS account_edi_ubl_cii/account.edi.xml.ubl_bis3
        if process_type == 'billing':
            return 'urn:peppol:pint:billing-1@ae-1'
        # NOTE: not literally confirmed anywhere in the Ministry's published documents (no PINT-AE
        # self-billing customization ID is quoted) - inferred by the same "billing-1@xx-1 /
        # selfbilling-1@xx-1" naming pattern used by every other published PINT country
        # specialization (Malaysia, Oman, ...), since PINT's process-type suffixing convention is a
        # structural part of the PINT methodology itself, not something country-specific. Revisit if
        # the official PINT-AE Data Dictionary specifies otherwise.
        return 'urn:peppol:pint:selfbilling-1@ae-1'

    # -------------------------------------------------------------------------
    # EXPORT: Templates
    # -------------------------------------------------------------------------

    def _ubl_add_customization_id_node(self, vals):
        # EXTENDS account.edi.xml.ubl_bis3
        super()._ubl_add_customization_id_node(vals)
        is_self_billing = self._is_document(vals, 'self_invoice', 'self_credit_note')
        process_type = 'selfbilling' if is_self_billing else 'billing'
        vals['document_node']['cbc:CustomizationID']['_text'] = self._get_customization_id(process_type=process_type)

    def _ubl_add_profile_id_node(self, vals):
        # EXTENDS account.edi.xml.ubl_bis3
        super()._ubl_add_profile_id_node(vals)
        vals['document_node']['cbc:ProfileID']['_text'] = 'urn:peppol:bis:billing'

    def _ubl_add_notes_nodes_all_invoices(self, vals):
        # EXTENDS account.edi.xml.ubl_pint
        #
        # Two UAE-specific data points are appended to the free-text Note here rather than as their
        # own dedicated XML elements:
        #
        # 1. The "Invoice transaction type code" 8-bit flag string (Mandatory Fields spec s4.1, field
        #    5) and, when the domestic reverse charge scenario applies, the required reference to
        #    which category of goods it covers (Guidelines s10.5.1). NOT CONFIRMED against an official
        #    PINT-AE XSD/schematron - not publicly available at the time this module was written -
        #    so this is a deliberate, clearly-labelled placeholder representation. Revisit once the
        #    Peppol PINT-AE Data Dictionary is published and gives an actual element/path for these.
        # 2. The Free Zone scenario's "ultimate beneficiary" reference (Guidelines s10.4, scenario 1),
        #    for the same reason - not encoded as a separate party block pending schema confirmation.
        super()._ubl_add_notes_nodes_all_invoices(vals)
        invoice = vals['invoice']

        extra_notes = [f"AE-TRANSACTION-TYPE-CODE:{invoice.l10n_ae_transaction_type_code}"]
        if invoice.l10n_ae_flag_margin_scheme:
            extra_notes.append(_("Margin scheme applies: displayed VAT amount is not the actual VAT due."))
        if invoice.l10n_ae_reverse_charge_goods_type:
            label = dict(invoice._fields['l10n_ae_reverse_charge_goods_type'].selection)[invoice.l10n_ae_reverse_charge_goods_type]
            extra_notes.append(_("Domestic reverse charge - goods category: %s", label))
        if invoice.l10n_ae_beneficiary_partner_id:
            extra_notes.append(_("Ultimate beneficiary: %s", invoice.l10n_ae_beneficiary_partner_id.display_name))

        existing_note = vals['document_node']['cbc:Note']['_text']
        combined_note = ' | '.join(filter(None, [existing_note, *extra_notes]))
        vals['document_node']['cbc:Note'] = {'_text': combined_note or None}

    # -------------------------------------------------------------------------
    # EXPORT: Constraints
    # -------------------------------------------------------------------------

    def _export_invoice_constraints(self, invoice, vals):
        # EXTENDS account_edi_ubl_cii
        constraints = super()._export_invoice_constraints(invoice, vals)

        supplier = vals['supplier']
        customer = vals['customer']

        if not supplier.l10n_ae_tin:
            constraints['l10n_ae_supplier_tin'] = _(
                "The supplier's UAE Tax Identification Number (TIN) is required to generate a PINT AE "
                "invoice - it is used to build the Peppol Participant Identifier (Seller electronic "
                "address). Set it on the company's contact record."
            )
        if not supplier.commercial_partner_id.l10n_ae_legal_registration_number:
            constraints['l10n_ae_supplier_legal_registration'] = _(
                "The supplier's UAE legal registration number (Trade License / Emirates ID / Passport "
                "/ Cabinet Decision) is required to generate a PINT AE invoice."
            )
        if customer.commercial_partner_id.country_code == 'AE' and customer.peppol_eas not in (False, '0235'):
            constraints['l10n_ae_customer_peppol_eas'] = _(
                "The customer's Peppol e-address scheme should be UAE TIN (0235) for a domestic UAE "
                "invoice."
            )

        # NOTE: this is intentionally minimal, mirroring the same caution as the Oman PINT
        # implementation this module was modeled on. The UAE's official PINT-AE schematron ("BR-AE-*"
        # business rules, by analogy with BR-MY-*/BR-SA-*) is not yet public. Do not add speculative
        # constraints here beyond what's already certain - extend this once the Ministry publishes it.
        return constraints
