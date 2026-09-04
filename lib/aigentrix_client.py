# -*- coding: utf-8 -*-
"""Thin REST client for the Aigentrix E-Invoice External Gateway.

Every method below maps 1:1 to one endpoint documented in the "Aigentrix E-Invoice External API"
reference guide (External Gateway, X-API-KEY auth, base port 8095, all paths prefixed
'/external/api/v1'). Only the endpoints this module's account.move/document flow actually uses
are implemented:

  - POST   /eInvoiceEntry/createFull            (4.1)
  - GET    /eInvoiceEntry/{id}                  (4.2)
  - GET    /eInvoiceEntry                       (4.3, used only for the settings "Test Connection")
  - GET    /eInvoiceEntry/{id}/statusTimeline    (4.4)
  - GET    /print/xml/{id}                       (4.5, PDF)
  - GET    /print/orgxml/{id}                    (4.6, raw XML)
  - PUT    /eInvoiceEntry/{id}                   (4.7)
  - DELETE /eInvoiceEntry                        (4.8)
  - POST   /eInvoiceEntry/validate               (4.12)
  - GET    /eInvoiceEntry/{id}/validationErrors  (4.15)

The bulk Excel upload/template/error-log endpoints (4.9-4.11, 4.13-4.14) and the Peppol
raw/multipart-XML endpoints (4.16-4.17) are not implemented: this module submits invoices that
already exist in Odoo one at a time via the JSON endpoints above, so those endpoints (aimed at
Excel-based bulk import or posting a UBL XML built outside Odoo) are out of scope here.
"""
import logging

import requests

from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AigentrixClient:
    """REST client for the Aigentrix E-Invoice External Gateway."""

    def __init__(self, base_url, api_key, timeout=30):
        """Store the credentials/config this client will use for every call - no request is made
        here.

        :param str base_url: External Gateway base URL (e.g. "http://localhost:8095").
        :param str api_key: sent as the 'X-API-KEY' header on every call.
        :param int timeout: request timeout in seconds.
        """
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._session = requests.Session()

    # -------------------------------------------------------------------------
    # 4.1 / 4.2 / 4.3 / 4.7 / 4.8 - E-Invoice Entry CRUD
    # -------------------------------------------------------------------------

    def create_full(self, payload):
        """POST /eInvoiceEntry/createFull - create a complete e-invoice entry.

        :param dict payload: EInvoiceCreateRequestDTO body (Section 5.1).
        :return: the parsed JSON body, e.g.
            {"success": true, "invoiceRef": "...", "entryId": 1042, "documentId": "...",
             "linesCreated": 2, "allowancesCreated": 1, "paymentsCreated": 1, "termsCreated": 1}
        :rtype: dict
        """
        return self._request('POST', '/eInvoiceEntry/createFull', json=payload)

    def get_entry(self, entry_id):
        """GET /eInvoiceEntry/{id} - fetch the EInvoiceEntryResponseDTO for one entry."""
        return self._request('GET', f'/eInvoiceEntry/{entry_id}')

    def list_entries(self, params):
        """GET /eInvoiceEntry - paginated list. `params` must at least carry the two required
        query parameters, startDate and endDate (Section 4.3)."""
        return self._request('GET', '/eInvoiceEntry', params=params)

    def update_entry(self, entry_id, vals):
        """PUT /eInvoiceEntry/{id} - update header fields of a DRAFT/VALIDATION_FAILED entry.

        :param dict vals: only the fields to change, e.g. {"status": "SUBMITTED"}.
        :return: e.g. {"id": 1042, "documentIdEN": "INV-2024-001", "status": "DRAFT"}
        """
        return self._request('PUT', f'/eInvoiceEntry/{entry_id}', json=vals)

    def delete_entries(self, entry_ids):
        """DELETE /eInvoiceEntry - delete one or more entries.

        :param list entry_ids: JSON array of entry IDs, sent as the request body.
        :return: e.g. {"deleted": 1, "success": true}
        """
        return self._request('DELETE', '/eInvoiceEntry', json=list(entry_ids))

    # -------------------------------------------------------------------------
    # 4.4 - Status Timeline
    # -------------------------------------------------------------------------

    def get_status_timeline(self, entry_id, doc_type):
        """GET /eInvoiceEntry/{id}/statusTimeline?type=OUTBOUND|INBOUND."""
        return self._request(
            'GET', f'/eInvoiceEntry/{entry_id}/statusTimeline', params={'type': doc_type})

    # -------------------------------------------------------------------------
    # 4.5 / 4.6 - Document downloads (binary)
    # -------------------------------------------------------------------------

    def download_pdf(self, entry_id, file_name):
        """GET /print/xml/{id}?fileName=... - Peppol Jasper PDF. Returns the raw response so the
        caller can read .content/.headers (binary, not JSON on success)."""
        return self._request(
            'GET', f'/print/xml/{entry_id}', params={'fileName': file_name}, raw=True)

    def download_xml(self, entry_id, file_name):
        """GET /print/orgxml/{id}?fileName=... - pretty-printed Peppol UBL XML from OCI. Returns
        the raw response (binary/text, not JSON on success)."""
        return self._request(
            'GET', f'/print/orgxml/{entry_id}', params={'fileName': file_name}, raw=True)

    # -------------------------------------------------------------------------
    # 4.12 - Validate (no DB write)
    # -------------------------------------------------------------------------

    def validate(self, payloads, include_xml=False):
        """POST /eInvoiceEntry/validate - validate one or more invoices against Peppol schematron
        rules without persisting anything.

        :param list payloads: JSON array of EInvoiceCreateRequestDTO-shaped objects.
        :param bool include_xml: adds ?includeXml=true to receive the generated UBL XML per result.
        :return: e.g. {"validatedAt": "...", "totalInvoices": 1, "passedCount": 1, "failedCount": 0,
            "results": [{"invoiceRef": "...", "documentId": "...", "passed": true,
                         "errors": [], "warnings": []}]}
        """
        params = {'includeXml': 'true'} if include_xml else None
        return self._request('POST', '/eInvoiceEntry/validate', json=payloads, params=params)

    # -------------------------------------------------------------------------
    # 4.15 - Validation errors for a stored entry
    # -------------------------------------------------------------------------

    def get_validation_errors(self, entry_id):
        """GET /eInvoiceEntry/{id}/validationErrors - stored Peppol schematron validation errors
        for a (typically VALIDATION_FAILED) entry."""
        return self._request('GET', f'/eInvoiceEntry/{entry_id}/validationErrors')

    # -------------------------------------------------------------------------
    # Shared HTTP helper
    # -------------------------------------------------------------------------

    def _request(self, method, path, json=None, params=None, raw=False):
        """Perform one HTTP call against ``self.base_url + '/external/api/v1' + path``, attaching
        the 'X-API-KEY' header.

        :param bool raw: when True, return the raw `requests.Response` (for binary PDF/XML
            downloads) after only checking for the documented auth/not-found error shapes -
            the caller reads .content/.headers itself. When False (default), return the parsed
            JSON body, raising a UserError built from the documented error shapes (Section 7.1)
            on any failure.
        """
        if not self.api_key:
            raise UserError(_(
                "No Aigentrix API Key is configured. Go to Settings > Accounting > Aigentrix "
                "E-Invoice to enter it."
            ))
        url = f"{self.base_url}/external/api/v1{path}"
        headers = {'X-API-KEY': self.api_key}
        if json is not None:
            headers['Content-Type'] = 'application/json'
        try:
            response = self._session.request(
                method, url, json=json, params=params, headers=headers, timeout=self.timeout)
        except requests.exceptions.RequestException as e:
            _logger.info("Network error calling Aigentrix (%s %s): %s", method, path, e)
            raise UserError(_(
                "Network connectivity issue while contacting the Aigentrix E-Invoice API. Please "
                "check the Base URL configured in Settings > Accounting > Aigentrix E-Invoice and "
                "your internet connection, then try again."
            ))

        if response.status_code >= 400:
            _logger.info('"%s %s" %s - response body: %s', method, url, response.status_code, response.text[:2000])
        else:
            _logger.info('"%s %s" %s', method, url, response.status_code)

        if raw:
            self._raise_for_error_status(response)
            return response
        return self._handle_response(response)

    @staticmethod
    def _raise_for_error_status(response):
        """Raise a UserError for the documented 401/404/500 error shapes (Section 7.1), used by
        the binary download calls (which don't have a JSON success body to also parse)."""
        if response.status_code < 400:
            return
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        message = payload.get('errorKey') or payload.get('error') or response.text[:2000]
        raise UserError(_(
            "Aigentrix E-Invoice API request failed (%(status)s): %(message)s",
            status=response.status_code, message=message,
        ))

    @staticmethod
    def _handle_response(response):
        """Parse a JSON response body, raising a UserError built from the documented error shapes
        (Section 7.1) on any failure:
          - 401: {"errorKey": "API key missing" | "Invalid API key"}
          - 400: {"success": false, "error": "<rule message>"}
          - 404: {"errorKey": "<description>"}
          - 500: {"errorKey": "Forwarding failed", "details": "..."} or
                 {"success": false, "error": "<message>"}
        """
        try:
            payload = response.json()
        except ValueError:
            if response.status_code >= 400:
                raise UserError(_(
                    "Aigentrix E-Invoice API request failed (%(status)s): %(body)s",
                    status=response.status_code, body=response.text[:2000],
                ))
            raise UserError(_(
                "An error occurred while reading the response from the Aigentrix E-Invoice API. "
                "Please try again later."
            ))

        if response.status_code >= 400 or (isinstance(payload, dict) and payload.get('errorKey')):
            message = (
                payload.get('errorKey')
                or payload.get('error')
                or payload.get('details')
                or response.text[:2000]
            ) if isinstance(payload, dict) else response.text[:2000]
            raise UserError(_(
                "Aigentrix E-Invoice API request failed (%(status)s): %(message)s",
                status=response.status_code, message=message,
            ))

        # createFull/peppol-style endpoints can also report a business failure with an
        # otherwise-200 "success": false body (Section 7.1, "Validation (business rule)").
        if isinstance(payload, dict) and payload.get('success') is False:
            raise UserError(_(
                "Aigentrix E-Invoice API rejected this request: %(message)s",
                message=payload.get('error') or payload.get('errorKey') or _("Unknown error"),
            ))

        return payload
