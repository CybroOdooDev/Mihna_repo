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
import base64
import logging
import time

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.l10n_om_convergex.lib.convergex_client import (
    BUSINESS_PROCESS_TYPE, SPECIFICATION_IDENTIFIER, TRANSACTION_TYPE_B2B, TRANSACTION_TYPE_B2C,
)

_logger = logging.getLogger(__name__)

# ConvergeX's own sandbox has been observed responding anywhere from a few seconds to over 40s,
# and occasionally drops a connection outright on a request it still processes successfully. These
# control how many times the whole sync+create(+recover) sequence is retried within a single
# _action_submit() call before actually giving up - so a transient blip resolves itself
# automatically instead of requiring a manual "Retry Submission" click every time.
MAX_SUBMIT_ATTEMPTS = 3
SUBMIT_RETRY_DELAY = 5  # seconds between attempts


def _convergex_invoice_number(move):
    """ The invoice_number actually sent to ConvergeX for `move`.

    ConvergeX's own URL routing 404s on a literal "/" in an invoice-number path segment (used by
    both the fast by-number lookup and the compliance/TDD-report endpoints) - and Odoo's default
    sequence format always contains one (e.g. "INV/2026/00011"). Replacing it with "-" here avoids
    that bug entirely, at the cost of ConvergeX showing a slightly different-looking reference than
    Odoo's own invoice number; Odoo's own name/display is completely unaffected either way.
    """
    return (move.name or '').replace('/', '-')


class L10nOmConvergexDocument(models.Model):
    """ Tracks the submission of one invoice/credit note to ConvergeX's Customer Invoice API.

    Unlike Flick Network's connector (see `l10n_om_edi`), ConvergeX's API takes structured JSON
    fields directly rather than a PINT OM XML file - ConvergeX generates the e-invoice, QR code, and
    OTA submission itself from that JSON, so this module never builds/sends XML.
    """
    _name = 'l10n.om.convergex.document'
    _inherit = ['mail.thread']
    _description = "ConvergeX Oman E-Invoicing Document"
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
            ('ota_accepted', "Acknowledged"),
            ('rejected', "Rejected"),
            ('error', "Error"),
        ],
        default='to_send',
        copy=False,
        readonly=True,
        tracking=True,
    )
    convergex_invoice_id = fields.Char(string="ConvergeX Invoice ID", copy=False, readonly=True)
    tracking_number = fields.Char(string="Tracking Number", copy=False, readonly=True)
    processed_reference_number = fields.Char(string="Processed Reference", copy=False, readonly=True,
                                               help="The Oman Tax Authority's own reference for this "
                                                    "submission, once acknowledged.")
    convergex_status = fields.Char(string="Raw ConvergeX Status", copy=False, readonly=True,
                                    help="The literal status string last reported by ConvergeX (e.g. "
                                         "'submitted', 'ota_accepted') - kept alongside the mapped "
                                         "'Status' selection above for transparency.")
    qr_code = fields.Image(string="QR Code", copy=False, readonly=True, max_width=256, max_height=256)
    error_message = fields.Text(string="Error Message", copy=False, readonly=True)
    retry_count = fields.Integer(default=0, copy=False, readonly=True)

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
        """ Sync the buyer to ConvergeX's Customer Master, then submit the invoice/credit note.

        Retries the whole sequence up to MAX_SUBMIT_ATTEMPTS times on failure (see the module-level
        comment on that constant) - a genuinely persistent problem (e.g. ConvergeX's Peppol network
        config not being active, or a real "already exists" name collision with no recoverable
        record) still ends in 'error' with a clear message; only transient blips self-heal here.
        """
        for document in self:
            move = document.move_id
            company = document.company_id
            if not (company.l10n_om_convergex_client_id and company.l10n_om_convergex_client_secret):
                # Same check as account_move.py's action_l10n_om_convergex_submit, repeated here so
                # the "Retry Submission" button on this document (which calls _action_submit
                # directly, bypassing that one) also fails immediately and clearly rather than deep
                # inside the first API call.
                raise UserError(_(
                    "No ConvergeX Client ID/Client Secret is configured for %(company)s. Please "
                    "enter your credentials in Settings > Accounting > ConvergeX before submitting.",
                    company=company.display_name,
                ))
            client = company._l10n_om_convergex_get_client()
            last_error = None
            response = None

            for attempt in range(1, MAX_SUBMIT_ATTEMPTS + 1):
                try:
                    buyer = move.partner_id.commercial_partner_id
                    try:
                        sync_response = client.sync_customer(move.partner_id._l10n_om_convergex_get_customer_payload())
                    except UserError as sync_error:
                        # ConvergeX enforces customer_name uniqueness account-wide, not per
                        # erp_uuid - a rename, or a leftover record from earlier testing sharing
                        # the same name, can collide even on a partner never synced before. Try to
                        # recover the real erp_uuid behind that name and retry once before giving
                        # up on this attempt.
                        if not buyer._l10n_om_convergex_recover_erp_uuid(client):
                            raise
                        sync_response = client.sync_customer(move.partner_id._l10n_om_convergex_get_customer_payload())
                    customer = sync_response.get('customer') or {}
                    if customer.get('erp_uuid'):
                        buyer.l10n_om_convergex_erp_uuid = customer['erp_uuid']

                    try:
                        response = client.create_invoice(document._build_invoice_payload())
                    except UserError as create_error:
                        # Whether ConvergeX explicitly said "already exists", or this was a
                        # network/timeout error reading the response - either way the invoice may
                        # already have been created there (observed live: a transient blip on the
                        # way back can lose a response for a request ConvergeX already processed).
                        # Try to recover its tracking details before treating this as a real
                        # failure; if that also comes up empty, surface the original error.
                        try:
                            response = document._recover_existing_invoice(client)
                        except UserError:
                            raise create_error
                    last_error = None
                    break
                except UserError as e:
                    last_error = e
                    if attempt < MAX_SUBMIT_ATTEMPTS:
                        _logger.info(
                            "ConvergeX submission attempt %s/%s failed for %s, retrying: %s",
                            attempt, MAX_SUBMIT_ATTEMPTS, move.name, e,
                        )
                        time.sleep(SUBMIT_RETRY_DELAY)

            if last_error:
                document.write({'state': 'error', 'error_message': str(last_error), 'retry_count': document.retry_count + 1})
                continue

            document._write_response(response)

    def _recover_existing_invoice(self, client):
        """ Recover this document's tracking details from ConvergeX directly by invoice number,
        since `create_invoice` reported it as already existing there. Uses the fast by-number
        lookup (includes qr_code) rather than scanning the summary-by-date endpoint, which was
        observed live taking 40-60+ seconds and degrading further as more invoices accumulate for
        the same day - a real scalability problem on ConvergeX's side, not just a slow one-off. """
        self.ensure_one()
        move = self.move_id
        try:
            return client.get_references_by_number(_convergex_invoice_number(move))
        except UserError:
            # Fall back to the slow date-range scan only if the fast lookup itself comes up empty -
            # keeps the door open for a real answer rather than surfacing the original error right
            # away, while no longer relying on it as the primary path.
            date_str = fields.Date.to_string(move.invoice_date)
            summary = client.get_summary_by_date_range(date_str, date_str)
            for result in summary.get('results') or []:
                if result.get('invoice_number') == _convergex_invoice_number(move):
                    return result
            raise UserError(_(
                "ConvergeX reports invoice number '%(number)s' already exists, but it could not be "
                "recovered by either the by-number lookup or a search of its issue date "
                "(%(date)s).",
                number=_convergex_invoice_number(move), date=date_str,
            ))

    def _build_invoice_payload(self):
        """ Build the JSON body for POST /api/invoices/create/ from `self.move_id`.

        Only the standard-invoice and credit-note profiles are covered - debit notes, self-billing,
        exempt/reverse-charge, and multi-currency are not built here yet.
        """
        self.ensure_one()
        move = self.move_id
        is_credit_note = move.move_type == 'out_refund'
        buyer = move.partner_id.commercial_partner_id
        is_b2b = bool(buyer.is_company)

        lines = move.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
        line_items = []
        tax_totals = {}
        for index, line in enumerate(lines, start=1):
            tax = line.tax_ids[:1]
            tax_rate = tax.amount if tax else 0.0
            line_items.append({
                'line_number': index,
                'item_description': line.name or line.product_id.name or '/',
                'quantity': "%.3f" % line.quantity,
                'unit_price': "%.3f" % line.price_unit,
                'tax_rate': "%.2f" % tax_rate,
                'tax_amount': "%.3f" % (line.price_total - line.price_subtotal),
                'line_total': "%.3f" % line.price_total,
                'invoice_line_identifier': str(index),
                'item_net_amount': "%.3f" % line.price_subtotal,
                'item_vat_category_code': 'S' if tax_rate else 'Z',
            })
            key = "%.2f" % tax_rate
            bucket = tax_totals.setdefault(key, {'tax_category_code': 'S' if tax_rate else 'Z',
                                                  'tax_rate': key, 'taxable_amount': 0.0, 'tax_amount': 0.0})
            bucket['taxable_amount'] += line.price_subtotal
            bucket['tax_amount'] += (line.price_total - line.price_subtotal)

        company = self.company_id
        payload = {
            # ConvergeX treats invoice_type as mandatory in practice (their own Postman examples
            # claim it can be omitted - that is not true against the live API; see the Settings
            # help text for l10n_om_convergex_invoice_type_uuid).
            'invoice_type': (
                company.l10n_om_convergex_credit_note_type_uuid if is_credit_note
                else company.l10n_om_convergex_invoice_type_uuid
            ),
            # Seller fields are documented as "Optional" (auto-populated from your ConvergeX
            # Company Profile) - sent explicitly here instead, from Odoo's own company record, so
            # invoice creation doesn't depend on that separate ConvergeX-side profile being complete
            # (Admin > Companies > PEPPOL Network Setup there is a different place to configure it
            # and easy to leave incomplete).
            'seller_trading_name': company.name,
            'seller_identifier': company.vat or company.partner_id.vat or '',
            'seller_vat_identifier': company.vat or company.partner_id.vat or '',
            'seller_address_line_1': company.street or '',
            'seller_address_line_2': company.street2 or '',
            'seller_city': company.city or '',
            'seller_postal_code': company.zip or '',
            'seller_country_code': company.country_id.code or '',
            'invoice_number': _convergex_invoice_number(move),
            'invoice_date': "%s 09:00" % fields.Date.to_string(move.invoice_date),
            'currency': move.currency_id.name,
            # Guaranteed set by _l10n_om_convergex_get_customer_payload(), called on `buyer` just
            # before this in _action_submit() - never fall back to the partner's own database id
            # here, since that isn't UUID-shaped and ConvergeX's create-invoice validator rejects it.
            'customer_erp_uuid': buyer.l10n_om_convergex_erp_uuid,
            'subtotal': "%.3f" % move.amount_untaxed,
            'tax_amount': "%.3f" % move.amount_tax,
            'total_amount': "%.3f" % move.amount_total,
            'compliance_profile': 'credit_note' if is_credit_note else 'standard',
            'document_side': 'customer',
            'invoice_type_code': '381' if is_credit_note else '380',
            'invoice_transaction_type': TRANSACTION_TYPE_B2B if is_b2b else TRANSACTION_TYPE_B2C,
            'specification_identifier': SPECIFICATION_IDENTIFIER,
            'business_process_type': BUSINESS_PROCESS_TYPE,
            # Without this, ConvergeX leaves the invoice sitting at "Received" indefinitely, only
            # forwarding it to PEPPOL/the Oman Tax Authority once someone manually clicks "Submit
            # to Government" in their own portal - confirmed live, not documented as the default
            # behaviour anywhere in their API docs.
            'send_to_government': True,
            'line_items': line_items,
            'tax_details': [
                {
                    'tax_category_code': bucket['tax_category_code'],
                    'tax_rate': bucket['tax_rate'],
                    'taxable_amount': "%.3f" % bucket['taxable_amount'],
                    'tax_amount': "%.3f" % bucket['tax_amount'],
                }
                for bucket in tax_totals.values()
            ],
        }

        if is_credit_note and move.reversed_entry_id:
            preceding = move.reversed_entry_id
            preceding_document = preceding.l10n_om_convergex_document_ids[:1]
            payload.update({
                'preceding_invoice_number': _convergex_invoice_number(preceding),
                'preceding_invoice_issue_date': fields.Date.to_string(preceding.invoice_date),
                # BTOM-031 is required by ConvergeX; only available once the original invoice has
                # itself been submitted through this same connector and returned an invoice id.
                'preceding_invoice_uuid': preceding_document.convergex_invoice_id or '',
                'credit_debit_note_reason_code': 'Correction',
            })

        return payload

    def _write_response(self, response):
        """ Store a successful create-invoice response on `self`. """
        self.ensure_one()
        qr = response.get('qr_code') or response.get('oman_qr') or {}
        image_data_url = qr.get('image_data_url') or ''
        qr_binary = False
        if image_data_url.startswith('data:image'):
            try:
                qr_binary = base64.b64encode(base64.b64decode(image_data_url.split(',', 1)[1]))
            except (IndexError, ValueError):
                _logger.warning("Could not decode ConvergeX qr_code.image_data_url for %s", self.name)

        raw_status = response.get('status') or 'submitted'
        self.write({
            'state': 'ota_accepted' if raw_status == 'ota_accepted' else 'submitted',
            'convergex_status': raw_status,
            'convergex_invoice_id': response.get('id') or self.convergex_invoice_id,
            'tracking_number': response.get('tracking_number') or self.tracking_number,
            'processed_reference_number': response.get('processed_reference_number') or self.processed_reference_number,
            'qr_code': qr_binary or self.qr_code,
            'error_message': False,
        })

    # -------------------------------------------------------------------------
    # Status polling
    # -------------------------------------------------------------------------

    def _cron_poll_status(self):
        """ Poll ConvergeX for the latest status of documents still 'submitted'. Degrades to a
        no-op for companies without ConvergeX credentials configured. """
        documents = self.search([('state', '=', 'submitted'), ('tracking_number', '!=', False)])
        for company, company_documents in documents.grouped('company_id').items():
            if not (company.l10n_om_convergex_client_id and company.l10n_om_convergex_client_secret):
                continue
            client = company._l10n_om_convergex_get_client()
            for document in company_documents:
                try:
                    summary = client.get_summary_by_tracking(document.tracking_number)
                except UserError as e:
                    _logger.warning("Error polling ConvergeX status for %s: %s", document.name, e)
                    continue
                status = summary.get('status')
                if status:
                    document.write({
                        'convergex_status': status,
                        'state': 'ota_accepted' if status == 'ota_accepted' else document.state,
                        'processed_reference_number': summary.get('processed_reference_number') or document.processed_reference_number,
                    })
