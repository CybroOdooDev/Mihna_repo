# -*- coding: utf-8 -*-
import base64
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Section 4.5/4.6 "fileName" query parameter values - identical list for both the PDF and the raw
# XML download endpoints.
DOWNLOAD_FILE_NAMES = [
    ('outbound_sent', "Outbound - Sent to Peppol Network"),
    ('outbound_ack', "Outbound - Acknowledgement"),
    ('outbound_report_fta', "Outbound - FTA Report"),
    ('outbound_confirm_fta', "Outbound - FTA Confirmation"),
    ('inbound_receive', "Inbound - Received from Network"),
    ('inbound_ack', "Inbound - Acknowledgement"),
    ('inbound_report_fta', "Inbound - FTA Report"),
    ('inbound_confirm_fta', "Inbound - FTA Confirmation"),
]

# Section 6.1 EInvoiceEntryStatus - the entry's lifecycle status, as literally returned by the
# Aigentrix API. Kept as the exact documented values (not remapped to a local vocabulary) so this
# field always shows what the API actually reports.
ENTRY_STATUS_SELECTION = [
    ('DRAFT', "Draft"),
    ('SUBMITTED', "Submitted"),
    ('VALIDATION_PASSED', "Validation Passed"),
    ('VALIDATION_FAILED', "Validation Failed"),
    ('DELIVERED', "Delivered"),
    ('ACKNOWLEDGED', "Acknowledged"),
    ('REJECTED', "Rejected"),
    ('CREDIT_NOTE_ISSUED', "Credit Note Issued"),
    ('RECEIVED', "Received"),
    ('ERROR', "Error"),
    ('SENDING', "Sending"),
    ('RESPONSE_GENERATED', "Response Generated"),
    ('PROCESSING', "Processing"),
    ('TRANSMISSION_FAILED', "Transmission Failed"),
]

# Section 6.2 EInvoiceEntryTaxStatus - the FTA reporting lifecycle status.
TAX_STATUS_SELECTION = [
    ('NOT_INITIATED', "Not Initiated"),
    ('REPORTING_INITIATED', "Reporting Initiated"),
    ('REPORTING_CONFIRMED', "Reporting Confirmed"),
    ('ACKNOWLEDGED', "Acknowledged"),
    ('REJECTED', "Rejected"),
    ('WITHDRAW_INITIATED', "Withdraw Initiated"),
    ('WITHDRAWN', "Withdrawn"),
    ('TDD_VALIDATION_PASSED', "TDD Validation Passed"),
    ('TDD_VALIDATION_FAILED', "TDD Validation Failed"),
    ('TDD_TRANSMISSION_FAILED', "TDD Transmission Failed"),
]


class L10nAeAigentrixDocument(models.Model):
    """Tracks the submission of one Odoo invoice/credit note to the Aigentrix E-Invoice External
    API, and mirrors the current state of the resulting eInvoiceEntry (Section 5.6
    EInvoiceEntryResponseDTO)."""
    _name = 'l10n.ae.aigentrix.document'
    _inherit = ['mail.thread']
    _description = "Aigentrix E-Invoice Document"
    _order = 'create_date desc, id desc'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True)
    company_id = fields.Many2one(comodel_name='res.company', required=True, readonly=True,
                                  default=lambda self: self.env.company)
    move_id = fields.Many2one(comodel_name='account.move', string="Invoice/Credit Note", required=True,
                               readonly=True, index=True, check_company=True)
    currency_id = fields.Many2one(related='move_id.currency_id')

    entry_id = fields.Integer(
        string="Aigentrix Entry ID", copy=False, readonly=True,
        help="The Aigentrix 'entryId' (Long) returned by POST /eInvoiceEntry/createFull.",
    )
    invoice_ref = fields.Char(
        string="Invoice Ref", copy=False, readonly=True,
        help="Client-side 'invoiceRef' sent on createFull and echoed back by the API.",
    )
    document_id_en = fields.Char(
        string="Aigentrix Document ID", copy=False, readonly=True,
        help="'documentIdEN'/'documentId' as stored by Aigentrix - the invoice number.",
    )
    state = fields.Selection(
        selection=ENTRY_STATUS_SELECTION, string="Status",
        copy=False, readonly=True, tracking=True,
        help="Section 6.1 EInvoiceEntryStatus, as last reported by the Aigentrix API.",
    )
    tax_status = fields.Selection(
        selection=TAX_STATUS_SELECTION, string="FTA Tax Status",
        copy=False, readonly=True, tracking=True,
        help="Section 6.2 EInvoiceEntryTaxStatus, as last reported by the Aigentrix API.",
    )
    type = fields.Selection(
        selection=[('OUTBOUND', "Outbound"), ('INBOUND', "Inbound")],
        string="Type", default='OUTBOUND', readonly=True, copy=False,
        help="Section 6.3 EInvoiceEntryTypeStatus. This module only ever creates OUTBOUND "
             "entries (invoices/credit notes Odoo sends); Aigentrix populates INBOUND entries "
             "itself from documents received over the Peppol network.",
    )
    environment = fields.Selection(
        selection=[('SANDBOX', "Sandbox"), ('LIVE', "Live")],
        string="Environment", copy=False, readonly=True,
        help="Section 6.4 EInvoiceEnvironment, as last reported by the Aigentrix API.",
    )
    legal_tax_inclusive_amount = fields.Monetary(
        string="Total Incl. Tax (Aigentrix)", copy=False, readonly=True,
        help="'legalTaxInclusiveAmountEN' as last reported by the Aigentrix API.",
    )
    legal_final_payable = fields.Monetary(
        string="Amount Payable (Aigentrix)", copy=False, readonly=True,
        help="'legalFinalPayableEN' as last reported by the Aigentrix API.",
    )
    tax_total_tax_amount = fields.Monetary(
        string="Total VAT (Aigentrix)", copy=False, readonly=True,
        help="'taxTotalTaxAmount' as last reported by the Aigentrix API.",
    )
    remote_created_at = fields.Datetime(
        string="Created At (Aigentrix)", copy=False, readonly=True,
        help="'createdAt' as last reported by the Aigentrix API.",
    )
    error_log = fields.Text(string="Error Log", copy=False, readonly=True)
    validation_errors = fields.Text(string="Validation Errors", copy=False, readonly=True)
    validation_warnings = fields.Text(string="Validation Warnings", copy=False, readonly=True)
    download_file_name = fields.Selection(
        selection=DOWNLOAD_FILE_NAMES, string="Document To Download",
        default='outbound_sent',
        help="Section 4.5/4.6 'fileName' query parameter - which stored document to download as "
             "PDF or XML.",
    )

    @api.depends('move_id.name')
    def _compute_name(self):
        for document in self:
            document.name = document.move_id.name or _("New")

    def _get_client(self):
        self.ensure_one()
        return self.company_id._l10n_ae_aigentrix_get_client()

    # -------------------------------------------------------------------------
    # 4.1 createFull / refresh from 4.2 get-by-id
    # -------------------------------------------------------------------------

    def _action_submit(self):
        """POST /eInvoiceEntry/createFull for this document's invoice, then immediately refresh
        from GET /eInvoiceEntry/{id} so the stored state reflects exactly what the API reports -
        the createFull response itself does not include a 'status'."""
        for document in self:
            payload = document.move_id._l10n_ae_aigentrix_build_payload()
            try:
                result = document._get_client().create_full(payload)
            except UserError as e:
                document.error_log = str(e)
                raise
            document.write({
                'entry_id': result.get('entryId'),
                'invoice_ref': result.get('invoiceRef'),
                'document_id_en': result.get('documentId'),
                'error_log': False,
            })
            document._action_refresh_status()

    def action_refresh_status(self):
        """Public wrapper around `_action_refresh_status`, callable from view buttons."""
        for document in self:
            document._action_refresh_status()

    def _action_refresh_status(self):
        """GET /eInvoiceEntry/{id} - refresh this document from the current EInvoiceEntryResponseDTO."""
        self.ensure_one()
        if not self.entry_id:
            raise UserError(_("This document has not been submitted to Aigentrix yet."))
        result = self._get_client().get_entry(self.entry_id)
        self.write({
            'document_id_en': result.get('documentIdEN') or self.document_id_en,
            'state': result.get('status') or self.state,
            'tax_status': result.get('taxStatus') or self.tax_status,
            'environment': result.get('environment') or self.environment,
            'legal_tax_inclusive_amount': result.get('legalTaxInclusiveAmountEN'),
            'legal_final_payable': result.get('legalFinalPayableEN'),
            'tax_total_tax_amount': result.get('taxTotalTaxAmount'),
            'remote_created_at': self._parse_remote_datetime(result.get('createdAt')),
            'error_log': result.get('errorLog') or False,
        })

    @staticmethod
    def _parse_remote_datetime(value):
        """Parse the ISO-8601 'createdAt' string documented in Section 5.6 into a naive UTC
        datetime Odoo's Datetime field accepts, without guessing a format that isn't documented."""
        if not value:
            return False
        try:
            return fields.Datetime.to_datetime(value.replace('T', ' ').split('+')[0].split('Z')[0])
        except (ValueError, TypeError):
            return False

    # -------------------------------------------------------------------------
    # 4.15 Validation errors
    # -------------------------------------------------------------------------

    def action_fetch_validation_errors(self):
        """GET /eInvoiceEntry/{id}/validationErrors."""
        for document in self:
            if not document.entry_id:
                raise UserError(_("This document has not been submitted to Aigentrix yet."))
            result = document._get_client().get_validation_errors(document.entry_id)
            document.write({
                'state': result.get('status') or document.state,
                'validation_errors': '\n'.join(result.get('errors') or []) or False,
                'validation_warnings': '\n'.join(result.get('warnings') or []) or False,
            })

    # -------------------------------------------------------------------------
    # 4.4 Status timeline
    # -------------------------------------------------------------------------

    def action_view_status_timeline(self):
        """GET /eInvoiceEntry/{id}/statusTimeline - posted to the chatter as a log message."""
        for document in self:
            if not document.entry_id:
                raise UserError(_("This document has not been submitted to Aigentrix yet."))
            result = document._get_client().get_status_timeline(document.entry_id, document.type)
            timeline = (result.get('statusTimeline') or {}).get('timeline') or []
            if timeline:
                lines = [
                    _("%(status)s - %(timestamp)s - %(updated_by)s",
                      status=entry.get('status'), timestamp=entry.get('timestamp'),
                      updated_by=entry.get('updatedBy'))
                    for entry in timeline
                ]
                body = _("Aigentrix status timeline:") + "<br/>" + "<br/>".join(lines)
            else:
                body = _("Aigentrix status timeline is empty.")
            document.message_post(body=body)

    # -------------------------------------------------------------------------
    # 4.7 Update / 4.8 Delete
    # -------------------------------------------------------------------------

    def action_advance_to_submitted(self):
        """PUT /eInvoiceEntry/{id} with {"status": "SUBMITTED"} (Section 4.7's own example).
        Only entries with status DRAFT or VALIDATION_FAILED may be updated - enforced by the API,
        not re-guessed here."""
        for document in self:
            if not document.entry_id:
                raise UserError(_("This document has not been submitted to Aigentrix yet."))
            result = document._get_client().update_entry(document.entry_id, {'status': 'SUBMITTED'})
            document.write({
                'document_id_en': result.get('documentIdEN') or document.document_id_en,
                'state': result.get('status') or document.state,
            })

    def action_delete_entry(self):
        """DELETE /eInvoiceEntry with this document's entry_id, then remove the local tracking
        record since the remote entry no longer exists."""
        for document in self:
            if not document.entry_id:
                document.unlink()
                continue
            document._get_client().delete_entries([document.entry_id])
            document.unlink()

    # -------------------------------------------------------------------------
    # 4.5 / 4.6 Downloads
    # -------------------------------------------------------------------------

    def action_download_pdf(self):
        """GET /print/xml/{id}?fileName=... - store the returned PDF as an ir.attachment on the
        invoice and open it."""
        self.ensure_one()
        return self._download_and_attach(
            self._get_client().download_pdf, extension='pdf', mimetype='application/pdf')

    def action_download_xml(self):
        """GET /print/orgxml/{id}?fileName=... - store the returned XML as an ir.attachment on
        the invoice and open it."""
        self.ensure_one()
        return self._download_and_attach(
            self._get_client().download_xml, extension='xml', mimetype='application/xml')

    def _download_and_attach(self, fetch_method, extension, mimetype):
        self.ensure_one()
        if not self.entry_id:
            raise UserError(_("This document has not been submitted to Aigentrix yet."))
        response = fetch_method(self.entry_id, self.download_file_name)
        attachment = self.env['ir.attachment'].create({
            'name': f"{self.download_file_name}_{self.entry_id}.{extension}",
            'type': 'binary',
            'datas': base64.b64encode(response.content),
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'mimetype': mimetype,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
