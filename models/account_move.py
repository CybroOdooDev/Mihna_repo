# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import html2plaintext

# Section 6.8 "Common UN/ECE Unit Codes" - the only quantityUom values this API guide documents.
# Odoo's own UoM records carry no such code, so standard UoMs are mapped here by external id;
# anything not listed (and any custom UoM) falls back to 'EA' (Each), the closest generic unit
# among the documented codes - never a code outside this documented list.
UOM_TO_AIGENTRIX_CODE = {
    'uom.product_uom_unit': 'EA',
    'uom.product_uom_kgm': 'KGM',
    'uom.product_uom_day': 'DAY',
    'uom.product_uom_hour': 'HUR',
    'uom.product_uom_meter': 'MTR',
    'uom.product_uom_litre': 'LTR',
    'uom.product_uom_cubic_meter': 'MTQ',
}

# Section 6.5 Invoice Type Codes.
INVOICE_TYPE_CODE_SELECTION = [
    ('380', "380 - Commercial Invoice"),
    ('381', "381 - Credit Note"),
    ('386', "386 - Prepayment Invoice"),
    ('388', "388 - Tax Invoice"),
]

# Section 6.7 Payment Means Codes (paymentMeansCode).
PAYMENT_MEANS_CODE_SELECTION = [
    ('10', "10 - Cash payment"),
    ('30', "30 - Credit transfer (bank wire)"),
    ('42', "42 - Payment to bank account"),
    ('48', "48 - Bank card or credit card"),
    ('49', "49 - Direct debit"),
    ('57', "57 - Standing order / bank mandate"),
    ('97', "97 - Clearing between trading partners"),
]

# NOT in the API guide - confirmed live against the Aigentrix API's own schematron response
# (rule [ibr-128-ae]): when country is AE, the party's country-subdivision code must be one of
# these 7 values, not the emirate/state code shown in the guide's own example ("e.g. DU").
# Odoo's own UAE res.country.state records use a different 2-letter code, mapped here.
UAE_EMIRATE_CODE_MAP = {
    'AJ': 'AJM',  # Ajman
    'AZ': 'AUH',  # Abu Dhabi
    'DU': 'DXB',  # Dubai
    'FU': 'FUJ',  # Fujairah
    'RK': 'RAK',  # Ras Al Khaimah
    'SH': 'SHJ',  # Sharjah
    'UQ': 'UAQ',  # Umm Al Quwain
}


def _get_uom_code(uom):
    """Map a product UoM to its Aigentrix quantityUom code - see UOM_TO_AIGENTRIX_CODE above."""
    xmlid = uom.get_external_id()
    if xmlid and uom.id in xmlid:
        return UOM_TO_AIGENTRIX_CODE.get(xmlid[uom.id], 'EA')
    return 'EA'


def _get_item_type(product):
    """Section 5.2 itemTypeGoodsServices: 'S' = Service, 'G' = Goods."""
    return 'S' if product and product.type == 'service' else 'G'


def _get_country_subdivision(partner):
    """Country-subdivision code for `partner` - see UAE_EMIRATE_CODE_MAP above for why this isn't
    simply `partner.state_id.code` when the country is AE."""
    code = partner.state_id.code
    if partner.country_id.code == 'AE' and code:
        return UAE_EMIRATE_CODE_MAP.get(code, code)
    return code or None


class AccountMove(models.Model):
    """Adds the Aigentrix E-Invoice fields/actions to customer invoices and credit notes."""
    _inherit = 'account.move'

    l10n_ae_aigentrix_document_ids = fields.One2many(
        comodel_name='l10n.ae.aigentrix.document', inverse_name='move_id', string="Aigentrix Documents")
    l10n_ae_aigentrix_document_count = fields.Integer(compute='_compute_l10n_ae_aigentrix_document_count')
    l10n_ae_aigentrix_status = fields.Selection(
        related='l10n_ae_aigentrix_document_ids.state', string="Aigentrix Status")

    # -- EInvoiceCreateRequestDTO header fields with no direct 1:1 Odoo core field --------------
    l10n_ae_aigentrix_invoice_type_code = fields.Selection(
        selection=INVOICE_TYPE_CODE_SELECTION, string="Aigentrix Invoice Type Code",
        compute='_compute_l10n_ae_aigentrix_invoice_type_code', store=True, readonly=False, copy=False,
        help="Sent as 'invoiceTypeCode' (Section 5.1/6.5). Defaults from the move type; change to "
             "386/388 for a prepayment or tax invoice.",
    )
    l10n_ae_aigentrix_transaction_type = fields.Selection(
        selection=[('B2B', "B2B"), ('B2C', "B2C")], string="Aigentrix Transaction Type",
        compute='_compute_l10n_ae_aigentrix_transaction_type', store=True, readonly=False, copy=False,
        help="Sent as 'invoiceTransactionType'. Defaults from whether the customer is a company.",
    )
    l10n_ae_aigentrix_original_invoice_reference = fields.Char(
        string="Aigentrix Original Invoice Reference", compute='_compute_l10n_ae_aigentrix_original_invoice_reference',
        store=True, readonly=False, copy=False,
        help="Sent as 'originalInvoiceReference' - required for credit notes (Section 5.1). "
             "Defaults from the reversed invoice, when this credit note was created from one.",
    )
    l10n_ae_aigentrix_original_invoice_reference_date = fields.Date(
        string="Aigentrix Original Invoice Date", compute='_compute_l10n_ae_aigentrix_original_invoice_reference',
        store=True, readonly=False, copy=False,
        help="Sent as 'originalInvoiceReferenceDate'.",
    )
    l10n_ae_aigentrix_buyer_reference = fields.Char(
        string="Aigentrix Buyer Reference", copy=False,
        help="Sent as 'buyerReference' - the buyer's own internal reference.",
    )
    l10n_ae_aigentrix_order_reference = fields.Char(
        string="Aigentrix Order Reference", compute='_compute_l10n_ae_aigentrix_order_reference',
        store=True, readonly=False, copy=False,
        help="Sent as 'orderReference' - purchase order reference. Defaults from the Source "
             "Document, when set.",
    )
    l10n_ae_aigentrix_contract_document_reference = fields.Char(
        string="Aigentrix Contract Reference", copy=False,
        help="Sent as 'contractDocumentReference'.",
    )
    l10n_ae_aigentrix_tax_point_date = fields.Date(
        string="Aigentrix Tax Point Date", copy=False, help="Sent as 'taxPointDate'.")
    l10n_ae_aigentrix_period_start_date = fields.Date(
        string="Aigentrix Period Start", copy=False, help="Sent as 'invoicePeriodStartDate'.")
    l10n_ae_aigentrix_period_end_date = fields.Date(
        string="Aigentrix Period End", copy=False, help="Sent as 'invoicePeriodEndDate'.")
    l10n_ae_aigentrix_delivery_location = fields.Char(
        string="Aigentrix Delivery Location", copy=False, help="Sent as 'deliveryLocation'.")
    l10n_ae_aigentrix_delivery_address_line1 = fields.Char(
        string="Aigentrix Delivery Address", copy=False, help="Sent as 'deliveryAddressLine1'.")
    l10n_ae_aigentrix_delivery_city = fields.Char(
        string="Aigentrix Delivery City", copy=False, help="Sent as 'deliveryCity'.")
    l10n_ae_aigentrix_delivery_country_id = fields.Many2one(
        comodel_name='res.country', string="Aigentrix Delivery Country", copy=False,
        help="Sent as 'deliveryCountryCode' (ISO 3166-1 alpha-2).",
    )
    l10n_ae_aigentrix_delivery_party_name = fields.Char(
        string="Aigentrix Delivery Party Name", copy=False, help="Sent as 'deliveryPartyName'.")
    l10n_ae_aigentrix_delivery_incoterms = fields.Char(
        string="Aigentrix Delivery Incoterms", copy=False,
        help="Sent as 'deliveryIncoterms', e.g. DDP, EXW, CIF.",
    )
    l10n_ae_aigentrix_tax_rep_name = fields.Char(
        string="Aigentrix Tax Representative", copy=False, help="Sent as 'taxRepName'.")
    l10n_ae_aigentrix_tax_rep_tax_id = fields.Char(
        string="Aigentrix Tax Representative VAT ID", copy=False, help="Sent as 'taxRepTaxId'.")
    l10n_ae_aigentrix_payment_means_code = fields.Selection(
        selection=PAYMENT_MEANS_CODE_SELECTION, string="Aigentrix Payment Means Code",
        compute='_compute_l10n_ae_aigentrix_payment_means_code', store=True, readonly=False, copy=False,
        help="Sent as 'payments[0].paymentMeansCode' (Section 5.4/6.7). NOT in the API guide, but "
             "confirmed live to be mandatory for standard invoices (rule [ibr-191-ae]) unless the "
             "invoice type code is a credit note - defaults to 30 (Credit transfer).",
    )

    @api.depends('l10n_ae_aigentrix_document_ids')
    def _compute_l10n_ae_aigentrix_document_count(self):
        for move in self:
            move.l10n_ae_aigentrix_document_count = len(move.l10n_ae_aigentrix_document_ids)

    @api.depends('move_type')
    def _compute_l10n_ae_aigentrix_invoice_type_code(self):
        for move in self:
            if not move.l10n_ae_aigentrix_invoice_type_code:
                move.l10n_ae_aigentrix_invoice_type_code = '381' if move.move_type == 'out_refund' else '380'

    @api.depends('move_type')
    def _compute_l10n_ae_aigentrix_payment_means_code(self):
        for move in self:
            if not move.l10n_ae_aigentrix_payment_means_code and move.move_type == 'out_invoice':
                move.l10n_ae_aigentrix_payment_means_code = '30'

    @api.depends('partner_id')
    def _compute_l10n_ae_aigentrix_transaction_type(self):
        for move in self:
            if not move.l10n_ae_aigentrix_transaction_type:
                move.l10n_ae_aigentrix_transaction_type = (
                    'B2B' if move.partner_id.commercial_partner_id.is_company else 'B2C')

    @api.depends('reversed_entry_id')
    def _compute_l10n_ae_aigentrix_original_invoice_reference(self):
        for move in self:
            if not move.l10n_ae_aigentrix_original_invoice_reference and move.reversed_entry_id:
                move.l10n_ae_aigentrix_original_invoice_reference = move.reversed_entry_id.name
                move.l10n_ae_aigentrix_original_invoice_reference_date = move.reversed_entry_id.invoice_date

    @api.depends('invoice_origin')
    def _compute_l10n_ae_aigentrix_order_reference(self):
        for move in self:
            if not move.l10n_ae_aigentrix_order_reference and move.invoice_origin:
                move.l10n_ae_aigentrix_order_reference = move.invoice_origin

    # -------------------------------------------------------------------------
    # Document management
    # -------------------------------------------------------------------------

    def _l10n_ae_aigentrix_get_or_create_document(self):
        """Return this move's active Aigentrix document, creating one if none exists yet."""
        self.ensure_one()
        document = self.l10n_ae_aigentrix_document_ids[:1]
        if not document:
            document = self.env['l10n.ae.aigentrix.document'].create({
                'move_id': self.id,
                'company_id': self.company_id.id,
            })
        return document

    def _l10n_ae_aigentrix_check_can_submit(self):
        self.ensure_one()
        if self.state != 'posted':
            raise UserError(_("Only posted invoices/credit notes can be submitted to Aigentrix."))
        if self.move_type not in ('out_invoice', 'out_refund'):
            raise UserError(_(
                "Only customer invoices and credit notes can be submitted to Aigentrix - Aigentrix "
                "populates INBOUND (vendor) entries itself from documents received over the Peppol "
                "network."))
        if not (self.company_id.l10n_ae_aigentrix_api_key and self.company_id.l10n_ae_aigentrix_company_id):
            raise UserError(_(
                "No Aigentrix API Key/Company ID is configured for %(company)s. Please enter your "
                "credentials in Settings > Accounting > Aigentrix E-Invoice before submitting.",
                company=self.company_id.display_name,
            ))

    def action_l10n_ae_aigentrix_validate(self):
        """POST /eInvoiceEntry/validate (Section 4.12) - validate without persisting anything.

        The full result is posted to the chatter so every error stays visible/reviewable - the
        toast notification alone can get cut off or auto-dismiss before it can be read. Parses
        both the response shape Section 4.12 documents (results[].passed / results[].errors[],
        plain strings) and the shape the live API has actually been observed to return instead
        (results[].valid + results[].schematronDetail.failedRules[], objects with 'id'/'message')
        - whichever set of keys is present in the response is used.
        """
        self.ensure_one()
        self._l10n_ae_aigentrix_check_can_submit()
        client = self.company_id._l10n_ae_aigentrix_get_client()
        payload = self._l10n_ae_aigentrix_build_payload()
        response = client.validate([payload])
        result = (response.get('results') or [{}])[0]

        passed = result.get('passed')
        if passed is None:
            passed = result.get('valid')

        errors = result.get('errors') or []
        if not errors:
            for rule in (result.get('schematronDetail') or {}).get('failedRules') or []:
                rule_id, message = rule.get('id'), rule.get('message') or ''
                if rule_id and not message.startswith('[%s]' % rule_id):
                    message = '[%s] %s' % (rule_id, message)
                errors.append(message or str(rule))

        if passed:
            body = Markup('<p>%s</p>') % _("Aigentrix validation passed.")
        else:
            items = Markup('').join(Markup('<li>%s</li>') % error for error in errors) or (
                Markup('<li>%s</li>') % _("No error detail returned."))
            body = Markup('<p>%s</p><ul>%s</ul>') % (_("Aigentrix validation failed:"), items)
        self.message_post(body=body)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Aigentrix Validation"),
                'message': _("Passed.") if passed else _(
                    "Failed - see the logged note on this invoice for the full error list."),
                'type': 'success' if passed else 'danger',
                'sticky': False,
            }
        }

    def action_l10n_ae_aigentrix_submit(self):
        """POST /eInvoiceEntry/createFull (Section 4.1)."""
        for move in self:
            move._l10n_ae_aigentrix_check_can_submit()
            document = move._l10n_ae_aigentrix_get_or_create_document()
            document._action_submit()

    def action_l10n_ae_aigentrix_view_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Aigentrix Documents"),
            'res_model': 'l10n.ae.aigentrix.document',
            'view_mode': 'list,form',
            'domain': [('move_id', '=', self.id)],
        }

    # -------------------------------------------------------------------------
    # EInvoiceCreateRequestDTO payload builder (Section 5.1/5.2/5.3/5.4/5.5)
    # -------------------------------------------------------------------------

    def _l10n_ae_aigentrix_build_payload(self):
        """Build the JSON body for POST /eInvoiceEntry/createFull (and /validate) from this move,
        strictly following the documented EInvoiceCreateRequestDTO field list. Optional fields
        with no corresponding Odoo data are simply omitted (left to the API's own documented
        defaults) rather than guessed."""
        self.ensure_one()
        move = self
        company = move.company_id
        currency = move.currency_id

        def amt(value):
            return float(currency.round(value or 0.0))

        supplier = company.partner_id.commercial_partner_id
        customer = move.partner_id.commercial_partner_id
        contact = move.partner_id if move.partner_id != customer else False

        move._l10n_ae_aigentrix_check_required_party_fields(supplier, is_seller=True)
        move._l10n_ae_aigentrix_check_required_party_fields(customer, is_seller=False)
        if not company.l10n_ae_aigentrix_company_id:
            raise UserError(_(
                "No Aigentrix Company ID is configured for %(company)s.", company=company.display_name))
        if move.move_type == 'out_refund' and not move.l10n_ae_aigentrix_original_invoice_reference:
            raise UserError(_(
                "'Aigentrix Original Invoice Reference' is required for credit notes (Section 5.1) - "
                "please fill it in the Other Info tab before submitting."))

        lines = move._l10n_ae_aigentrix_build_lines(currency)
        payments = move._l10n_ae_aigentrix_build_payments()

        payload = {
            'companyId': company.l10n_ae_aigentrix_company_id,
            'invoiceRef': move.name,

            'documentId': move.name,
            'issueDate': move.invoice_date.isoformat() if move.invoice_date else None,
            'invoiceTypeCode': move.l10n_ae_aigentrix_invoice_type_code or ('381' if move.move_type == 'out_refund' else '380'),
            'invoiceTransactionType': move.l10n_ae_aigentrix_transaction_type or 'B2B',
            'documentCurrencyCode': currency.name,
            'noteEN': move._l10n_ae_aigentrix_get_note(),
            'taxPointDate': move.l10n_ae_aigentrix_tax_point_date.isoformat() if move.l10n_ae_aigentrix_tax_point_date else None,
            'invoiceSupplyDate': move.delivery_date.isoformat() if move.delivery_date else None,
            'paymentDueDate': move.invoice_date_due.isoformat() if move.invoice_date_due else None,
            'orderReference': move.l10n_ae_aigentrix_order_reference or None,
            'contractDocumentReference': move.l10n_ae_aigentrix_contract_document_reference or None,
            'originalInvoiceReference': move.l10n_ae_aigentrix_original_invoice_reference or None,
            'originalInvoiceReferenceDate': (
                move.l10n_ae_aigentrix_original_invoice_reference_date.isoformat()
                if move.l10n_ae_aigentrix_original_invoice_reference_date else None),
            'buyerReference': move.l10n_ae_aigentrix_buyer_reference or None,
            'invoicePeriodStartDate': move.l10n_ae_aigentrix_period_start_date.isoformat() if move.l10n_ae_aigentrix_period_start_date else None,
            'invoicePeriodEndDate': move.l10n_ae_aigentrix_period_end_date.isoformat() if move.l10n_ae_aigentrix_period_end_date else None,

            'sellerName': supplier.name,
            'sellerVatTrn': supplier.vat,
            'sellerRegisteredName': supplier.name,
            'sellerAddressLine1': supplier.street,
            'sellerAddressLine2': supplier.street2 or None,
            'sellerCity': supplier.city,
            'sellerPostalZone': supplier.zip or None,
            'sellerCountrySubdivision': _get_country_subdivision(supplier),
            'sellerCountryCode': supplier.country_id.code,
            'sellerTelephone': supplier.phone or None,
            'sellerEmail': supplier.email or None,

            'buyerName': customer.name,
            'buyerVatTrn': customer.vat,
            'buyerRegisteredName': customer.name,
            'buyerAddressLine1': customer.street,
            'buyerAddressLine2': customer.street2 or None,
            'buyerCity': customer.city,
            'buyerPostalZone': customer.zip or None,
            'buyerCountrySubdivision': _get_country_subdivision(customer),
            'buyerCountryCode': customer.country_id.code,
            'buyerTelephone': customer.phone or None,
            'buyerEmail': customer.email or None,
            'buyerContact': contact.name if contact else None,

            'lineExtensionTotal': amt(move.amount_untaxed),
            'taxAmount': amt(move.amount_tax),
            'totalIncludingTax': amt(move.amount_total),
            'payableAmount': amt(move.amount_total),

            'deliveryLocation': move.l10n_ae_aigentrix_delivery_location or None,
            'deliveryAddressLine1': move.l10n_ae_aigentrix_delivery_address_line1 or None,
            'deliveryCity': move.l10n_ae_aigentrix_delivery_city or None,
            'deliveryCountryCode': move.l10n_ae_aigentrix_delivery_country_id.code or None,
            'deliveryPartyName': move.l10n_ae_aigentrix_delivery_party_name or None,
            'deliveryIncoterms': move.l10n_ae_aigentrix_delivery_incoterms or None,

            'taxRepName': move.l10n_ae_aigentrix_tax_rep_name or None,
            'taxRepTaxId': move.l10n_ae_aigentrix_tax_rep_tax_id or None,

            'supplierParticipantId': company.l10n_ae_aigentrix_peppol_participant_id or None,
            'customerParticipantId': customer.l10n_ae_aigentrix_peppol_participant_id or None,

            'lines': lines,
        }
        if payments:
            payload['payments'] = payments
        # strip keys whose value is None so optional fields fall back to the API's own documented
        # defaults instead of sending an explicit null.
        return {key: value for key, value in payload.items() if value is not None}

    def _l10n_ae_aigentrix_get_note(self):
        """Section 5.1 'noteEN' - plain-text version of this move's own Terms & Conditions note."""
        self.ensure_one()
        if not self.narration:
            return None
        return html2plaintext(self.narration) or None

    @staticmethod
    def _l10n_ae_aigentrix_check_required_party_fields(partner, is_seller):
        role = _("Seller (your company)") if is_seller else _("Buyer (customer)")
        missing = []
        if not partner.name:
            missing.append(_("Name"))
        if not partner.vat:
            missing.append(_("VAT/TRN"))
        if not partner.street:
            missing.append(_("Street Address"))
        if not partner.city:
            missing.append(_("City"))
        if not partner.country_id:
            missing.append(_("Country"))
        if missing:
            raise UserError(_(
                "%(role)s (%(partner)s) is missing required Aigentrix fields: %(missing)s.",
                role=role, partner=partner.display_name, missing=', '.join(missing),
            ))

    def _l10n_ae_aigentrix_build_lines(self, currency):
        """Section 5.2 lines[]."""
        self.ensure_one()

        def amt(value):
            return float(currency.round(value or 0.0))

        lines = []
        # In Odoo 19 a genuine product line has display_type == 'product' - section/note/tax/
        # payment-term lines have their own distinct display_type and are excluded.
        invoice_lines = self.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
        for index, line in enumerate(invoice_lines, start=1):
            tax = line.tax_ids[:1]
            if not tax or not tax.l10n_ae_aigentrix_tax_category:
                raise UserError(_(
                    "Line %(index)s (%(name)s) has no tax with an Aigentrix VAT Category "
                    "configured - open the tax and set 'Aigentrix VAT Category' (Section 6.6) "
                    "before submitting.", index=index, name=line.name))
            tax_category = tax.l10n_ae_aigentrix_tax_category
            if tax_category == 'E' and not tax.l10n_ae_aigentrix_vat_exempt_reason_code:
                raise UserError(_(
                    "[ibr-167-ae] Line %(index)s (%(name)s): the tax '%(tax)s' has VAT Category "
                    "'E' (Exempt) but no Aigentrix VAT Exempt Reason Code configured.",
                    index=index, name=line.name, tax=tax.display_name))

            line_vals = {
                'lineNumber': index,
                'itemName': line.product_id.name or line.name,
                'itemDescription': line.name,
                'sellerItemId': line.product_id.default_code or None,
                'itemTypeGoodsServices': _get_item_type(line.product_id),
                'quantity': line.quantity,
                'quantityUom': _get_uom_code(line.product_uom_id),
                'unitPrice': amt(line.price_unit),
                'lineDiscountAmount': amt(line.price_unit * line.quantity * line.discount / 100) if line.discount else None,
                'lineDiscountPercent': line.discount or None,
                'lineNetAmount': amt(line.price_subtotal),
                'taxCategory': tax_category,
                'taxRatePercent': tax.amount if tax_category != 'O' else None,
                'lineTaxAmount': amt(line.price_total - line.price_subtotal),
                'inclVatAmount': amt(line.price_total),
            }
            if tax_category == 'E':
                line_vals['vatExemptReasonCode'] = tax.l10n_ae_aigentrix_vat_exempt_reason_code
                line_vals['vatExemptReasonText'] = tax.l10n_ae_aigentrix_vat_exempt_reason_text or None
            lines.append({key: value for key, value in line_vals.items() if value is not None})

        if not lines:
            raise UserError(_("This invoice has no product lines to submit to Aigentrix."))
        return lines

    def _l10n_ae_aigentrix_build_payments(self):
        """Section 5.4 payments[]. NOT documented in the API guide, but confirmed live: rule
        [ibr-191-ae] rejects a standard invoice with no 'paymentMeansCode' at all unless it is a
        credit note - so 'l10n_ae_aigentrix_payment_means_code' (defaulted to 30/Credit transfer
        for invoices, left blank for credit notes to match the rule's own exception) is always
        sent when set. Odoo has no dedicated field distinguishing cash/card/direct-debit, so the
        bank-account detail fields are only added when a recipient bank account is actually set
        on the invoice AND Odoo itself recognises its number as an IBAN (`acc_type == 'iban'`) -
        the API only documents a 'creditAccountIban' field, not a generic account-number one, so
        a non-IBAN account number is never guessed into it."""
        self.ensure_one()
        code = self.l10n_ae_aigentrix_payment_means_code
        if not code:
            return []
        payment = {'paymentMeansCode': code}
        bank = self.partner_bank_id
        if bank and bank.acc_type == 'iban':
            payment.update({
                'creditAccountIban': bank.acc_number or None,
                'creditAccountScheme': 'IBAN',
                'creditAccountName': bank.acc_holder_name or self.partner_id.name or None,
                'bankBicSwift': bank.bank_bic or None,
                'bankCountry': bank.bank_id.country.code if bank.bank_id and bank.bank_id.country else None,
            })
        return [{key: value for key, value in payment.items() if value is not None}]
