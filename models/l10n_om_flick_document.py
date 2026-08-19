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
import logging
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from odoo import api, fields, models, _
from odoo.exceptions import UserError

# Oman never observes daylight saving, so this fixed UTC+4 offset never changes.
_OMAN_TZ = ZoneInfo('Asia/Muscat')

_logger = logging.getLogger(__name__)

# UN/ECE Rec 20 unit codes (https://docs.peppol.eu/poacc/billing/3.0/codelist/UNECERec20/),
# replicated here since this module doesn't depend on 'account_edi_ubl_cii'. Only common units
# are covered; anything else falls back to 'C62' (unit/piece).
UOM_TO_UNECE_CODE = {
    'uom.product_uom_unit': 'C62',
    'uom.product_uom_dozen': 'DZN',
    'uom.product_uom_kgm': 'KGM',
    'uom.product_uom_gram': 'GRM',
    'uom.product_uom_day': 'DAY',
    'uom.product_uom_hour': 'HUR',
    'uom.product_uom_ton': 'TNE',
    'uom.product_uom_meter': 'MTR',
    'uom.product_uom_km': 'KMT',
    'uom.product_uom_litre': 'LTR',
    'uom.product_uom_cubic_meter': 'MTQ',
}


def _get_uom_unece_code(uom):
    """ Map a product UoM to its UN/ECE Rec 20 code, defaulting to 'C62' (unit/piece) - see the
    module-level comment on UOM_TO_UNECE_CODE. """
    xmlid = uom.get_external_id()
    if xmlid and uom.id in xmlid:
        return UOM_TO_UNECE_CODE.get(xmlid[uom.id], 'C62')
    return 'C62'


def _get_tax_category_code(tax):
    """ VAT category code (IBT-151: S/E/O/Z). Only 'S' and 'E' are produced - 'O'/'Z' need a
    business classification Odoo's tax record doesn't carry, so any non-zero tax is 'S', anything
    else is 'E' (same simplification as 'l10n_om_convergex'). """
    return 'S' if tax and tax.amount else 'E'


def _get_item_type(product):
    """ BTOM-013: item_type is documented as "GS" (goods) or "SV" (services), mandatory. """
    return 'SV' if product and product.type == 'service' else 'GS'


def _get_transaction_type_code(buyer):
    """ BTOM-001: 20-char string of '0'/'1', at least one of positions 1-15 must be '1'. Position
    1 = FullTax, position 2 = Simplified - the only two relevant here; all others stay '0'. """
    bits = ['0'] * 20
    bits[0 if buyer.is_company else 1] = '1'
    return ''.join(bits)


def _fmt_amount(currency, amount):
    """ Format an amount using the currency's own decimal precision - OMR needs 3 decimals (Baisa),
    not the 2 most currencies use, so this must not be hardcoded. """
    return ("%.{}f".format(currency.decimal_places)) % amount


class L10nOmFlickDocument(models.Model):
    """ Tracks the submission of one invoice/credit note to Flick Network's Document API.

    Flick's API takes its own flattened PINT-OM JSON schema (not a PINT OM XML file), so this
    module never builds/sends XML - Flick performs Corner-5/OTA reporting itself once the document
    is submitted.
    """
    _name = 'l10n.om.flick.document'
    _inherit = ['mail.thread']
    _description = "Flick Network Oman E-Invoicing Document"
    _order = 'create_date desc, id desc'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True)
    company_id = fields.Many2one(comodel_name='res.company', required=True, readonly=True,
                                  default=lambda self: self.env.company)
    move_id = fields.Many2one(comodel_name='account.move', string="Invoice/Credit Note", required=True,
                               readonly=True, index=True, check_company=True)

    state = fields.Selection(
        string="Status",
        selection=[
            ('to_send', "To Send"),
            ('submitted', "Submitted"),
            ('accepted', "Acknowledged"),
            ('rejected', "Rejected"),
            ('error', "Error"),
        ],
        default='to_send',
        copy=False,
        readonly=True,
        tracking=True,
    )
    flick_uuid = fields.Char(
        string="UUID", copy=False, readonly=True,
        help="Supplier-generated UUID identifying this document, sent to Flick as the document's "
             "own 'uuid' field (BTOM-002). Generated locally so it is available even before Flick "
             "acknowledges the submission.",
    )
    flick_document_id = fields.Char(string="Flick Document ID", copy=False, readonly=True)
    flick_status = fields.Char(string="Raw Flick Status", copy=False, readonly=True,
                                help="The literal status string last reported by Flick Network "
                                     "(e.g. 'processing', 'completed') - kept alongside the mapped "
                                     "'Status' selection above for transparency.")
    error_message = fields.Text(string="Error Message", copy=False, readonly=True)
    retry_count = fields.Integer(default=0, copy=False, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        """ Generate the supplier-side UUID locally at creation time, not deferred to submission. """
        for vals in vals_list:
            vals.setdefault('flick_uuid', str(uuid.uuid4()))
        return super().create(vals_list)

    @api.depends('move_id.name')
    def _compute_name(self):
        """ Use the invoice/credit note's own name as this document's display name. """
        for document in self:
            document.name = document.move_id.name or _("New")

    # -------------------------------------------------------------------------
    # Submission
    # -------------------------------------------------------------------------

    def action_retry_submission(self):
        """ Public wrapper around `_action_submit`, callable from view buttons. """
        self._action_submit()

    def _action_submit(self):
        """ Submit the invoice/credit note to Flick Network. """
        for document in self:
            company = document.company_id
            if not (company.l10n_om_flick_api_key and company.l10n_om_flick_participant_id):
                # Same check as account_move.py's action_l10n_om_flick_submit - repeated here so
                # "Retry Submission" (which bypasses that one) also fails clearly, not deep in the API call.
                document.write({
                    'state': 'error',
                    'error_message': _(
                        "No Flick Network API Key/Participant ID is configured for %(company)s. "
                        "Please enter your credentials in Settings > Accounting > Flick Network "
                        "before submitting.", company=company.display_name,
                    ),
                })
                continue
            try:
                client = company._l10n_om_flick_get_client()
                document_id = client.submit_document(document._build_document_payload())
            except UserError as e:
                document.write({'state': 'error', 'error_message': str(e), 'retry_count': document.retry_count + 1})
                continue

            document.write({
                'state': 'submitted',
                'flick_document_id': document_id,
                'error_message': False,
            })

    def _build_document_payload(self):
        """ Build the JSON body for POST /v1/{participant_id}/documents from `self.move_id`, per
        Flick Network's documented schema.

        Only the standard-invoice and credit-note profiles are covered - debit notes, self-billing,
        multi-currency (currency_exchange_rate, BTOM-004) and most optional/conditional fields
        (note, invoice_period, order_reference, payment_means, allowance_charge, ...) are not built
        here yet.
        """
        self.ensure_one()
        move = self.move_id
        currency = move.currency_id
        supplier = move.company_id.partner_id.commercial_partner_id
        customer = move.partner_id.commercial_partner_id
        is_credit_note = move.move_type == 'out_refund'
        # In Odoo 19, a genuine product line has display_type == 'product' (not a falsy value as in
        # older versions) - section/note/tax/payment-term lines have their own distinct display_type.
        lines = move.invoice_line_ids.filtered(lambda l: l.display_type == 'product')

        # Document-level VAT breakdown at "vat_totals" - required, but undocumented anywhere
        # available to us; confirmed live against Flick's sandbox /documents/validate endpoint.
        # IMPORTANT: despite invoice_lines using "vat_category"/"vat_percentage", these bucket keys
        # are "tax_category"/"tax_percentage"/etc - NOT the same prefix. Don't "fix" this to match;
        # the vat_-prefixed version was tried first and rejected.
        vat_buckets = {}

        def _invoice_line(index, line):
            """ Build one `invoice_lines[]` entry for `line`, and fold its VAT into `vat_buckets`
            (closure over the outer scope) for the `vat_totals` breakdown built after this loop. """
            tax = line.tax_ids[:1]
            vat_category = _get_tax_category_code(tax)
            rate = tax.amount if tax else 0.0
            line_vals = {
                'id': str(index),
                'name': line.product_id.name or line.name,
                'description': line.name,
                'quantity': str(line.quantity),
                'uom': _get_uom_unece_code(line.product_uom_id),
                'unit_price': _fmt_amount(currency, line.price_unit),
                'base_quantity': "1",
                'line_extension_amount': _fmt_amount(currency, line.price_subtotal),
                'vat_category': vat_category,
                'vat_percentage': "%.2f" % rate,
                'item_type': _get_item_type(line.product_id),
                'line_total_including_vat': _fmt_amount(currency, line.price_total),
            }
            if vat_category == 'E':
                # IBT-186, mandatory when category is 'E'. Odoo has no field for *which* of Flick's
                # 12 exemption reasons applies, so 'VATEX-OM-12' ("Other exempt supply") is a generic fallback.
                line_vals['vat_exemption_reason_code'] = 'VATEX-OM-12'

            bucket = vat_buckets.setdefault((vat_category, "%.2f" % rate), {
                'vat_category': vat_category, 'vat_percentage': "%.2f" % rate,
                'taxable_amount': 0.0, 'vat_amount': 0.0,
            })
            bucket['taxable_amount'] += line.price_subtotal
            bucket['vat_amount'] += (line.price_total - line.price_subtotal)

            return line_vals

        invoice_lines = [_invoice_line(index, line) for index, line in enumerate(lines, start=1)]

        vat_totals = []
        for bucket in vat_buckets.values():
            entry = {
                'tax_category': bucket['vat_category'],
                'tax_percentage': bucket['vat_percentage'],
                'taxable_amount': _fmt_amount(currency, bucket['taxable_amount']),
                'tax_amount': _fmt_amount(currency, bucket['vat_amount']),
            }
            if bucket['vat_category'] == 'E':
                entry['tax_exemption_reason_code'] = 'VATEX-OM-12'
            vat_totals.append(entry)

        # IBT-168: "represents the local time of invoice issuance" - Oman local time, not UTC.
        issue_time = datetime.now(timezone.utc).astimezone(_OMAN_TZ)
        payload = {
            'uuid': self.flick_uuid,
            'document_identifier': move.name,
            'issue_date': move.invoice_date.isoformat() if move.invoice_date else None,
            'issue_time': issue_time.strftime('%H:%M:%S'),
            'due_date': move.invoice_date_due.isoformat() if move.invoice_date_due else None,
            'document_type': '381' if is_credit_note else '380',
            'document_currency': currency.name,
            'transaction_type_code': _get_transaction_type_code(customer),
            # Docs call this "sending_party", but the live validator only accepts "issuing_party" -
            # confirmed against Flick's sandbox (a real submission was acknowledged using it).
            'issuing_party': supplier._l10n_om_flick_get_party_payload(),
            'receiving_party': customer._l10n_om_flick_get_party_payload(),
            'invoice_lines': invoice_lines,
            'vat_totals': vat_totals,
            'invoice_totals': {
                'line_extension_amount': _fmt_amount(currency, move.amount_untaxed),
                'tax_exclusive_amount': _fmt_amount(currency, move.amount_untaxed),
                'tax_inclusive_amount': _fmt_amount(currency, move.amount_total),
                'payable_amount': _fmt_amount(currency, move.amount_total),
            },
        }

        if is_credit_note:
            # BTOM-003, mandatory for credit notes. Odoo has no field mapping to Flick's 5-value
            # reason list, so 'OTH' ("Other reason") is a generic fallback.
            payload['credit_note_reason_code'] = 'OTH'
            preceding = move.reversed_entry_id
            if preceding:
                # IBG-03, mandatory for credit notes - only buildable when Odoo's Credit Note flow
                # linked this back to the original invoice; left out otherwise.
                payload['document_references'] = [{
                    'id': preceding.name,
                    'issue_date': preceding.invoice_date.isoformat() if preceding.invoice_date else None,
                }]

        return payload

    # -------------------------------------------------------------------------
    # Status polling
    # -------------------------------------------------------------------------

    def _cron_poll_status(self):
        """ Poll Flick Network for the latest status of documents still 'submitted'. Degrades to a
        no-op for companies without Flick credentials configured. """
        documents = self.search([('state', '=', 'submitted'), ('flick_document_id', '!=', False)])
        for company, company_documents in documents.grouped('company_id').items():
            if not (company.l10n_om_flick_api_key and company.l10n_om_flick_participant_id):
                continue
            client = company._l10n_om_flick_get_client()
            for document in company_documents:
                try:
                    status_data = client.get_status(document.flick_document_id)
                except UserError as e:
                    _logger.warning("Error polling Flick Network status for %s: %s", document.name, e)
                    continue
                raw_status = status_data.get('status')
                mapped_state = {
                    'processing': 'submitted',
                    'completed': 'accepted',
                    'failed': 'rejected',
                }.get(raw_status)
                document.write({
                    'state': mapped_state or document.state,
                    'flick_status': raw_status or document.flick_status,
                })
