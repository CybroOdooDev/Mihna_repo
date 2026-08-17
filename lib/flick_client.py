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
import json
import logging

import requests

from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class FlickClient:
    """ Thin REST client for the Flick Network (flick.network) Oman e-invoicing API.

    Covers only the subset of Flick's documented API this module actually uses: static API-key
    auth, document submission, and status retrieval. Flick's own docs also document an OAuth2
    client_credentials flow (POST /v1/oauth/token) and a "Retry Document" operation - neither is
    implemented here.

    Before any document can be submitted, the company must already be registered as a
    "Participant" on Flick's Peppol network (POST /v1/participants, a one-time manual setup via
    their dashboard/API, not something this client does) - the resulting `participant_id` is
    required on every call below.
    """

    def __init__(self, base_url, api_key, participant_id, timeout=30):
        """ Store the credentials/config this client will use for every call - no request is made
        here.

        :param str base_url: Flick API base URL (e.g. "https://sb-om-api.flick.network").
        :param str api_key: Flick's static API key, sent as the 'X-Flick-Auth-Key' header.
        :param str participant_id: this company's Flick Peppol "Participant" id, obtained by
            registering as a Participant via the Flick dashboard/API beforehand.
        :param int timeout: request timeout in seconds.
        """
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.participant_id = participant_id
        self.timeout = timeout
        self._session = requests.Session()

    # -------------------------------------------------------------------------
    # Auth
    # -------------------------------------------------------------------------

    def test_connection(self):
        """ GET /v1/auth/verify - confirmed side-effect-free way to check the configured API key is
        valid, without touching document submission at all. """
        if not self.api_key:
            raise UserError(_(
                "No Flick Network API Key is configured. Go to Settings > Accounting > Flick "
                "Network to enter it."
            ))
        self._request('GET', '/auth/verify')
        return True

    # -------------------------------------------------------------------------
    # Documents
    # -------------------------------------------------------------------------

    def submit_document(self, document_payload):
        """ POST /v1/{participant_id}/documents - submit one invoice/credit note document.

        The request body must be wrapped in a top-level "document" key (required by Flick's API but
        not shown in their sample payload).

        :param dict document_payload: see Flick's documented JSON schema.
        :return: the ASP-assigned document id used to track this submission.
        :rtype: str
        """
        if not self.participant_id:
            raise UserError(_(
                "No Flick Network Participant ID is configured. Register your company as a "
                "Participant via the Flick dashboard first, then enter the resulting "
                "participant_id in Settings > Accounting > Flick Network before submitting."
            ))
        response = self._request(
            'POST', f'/{self.participant_id}/documents',
            json={'document': document_payload}, handle_response=False,
        )
        return self._handle_submit_response(response)

    def get_status(self, document_id):
        """ GET /v1/{participant_id}/documents/{document_id} - reuses the same
        status/exchange_status/reporting_status envelope as the Submit Document response.

        :return: the parsed response's "data" object (its "status" key is one of Flick's raw
            'processing'/'completed'/'failed' values - left for the caller to map, same as
            `l10n.om.flick.document._cron_poll_status` does).
        :rtype: dict
        """
        payload = self._request('GET', f'/{self.participant_id}/documents/{document_id}')
        return payload.get('data') or {}

    # -------------------------------------------------------------------------
    # Shared HTTP helper
    # -------------------------------------------------------------------------

    def _request(self, method, path, json=None, handle_response=True):
        """ Perform one HTTP call against ``self.base_url + '/v1' + path``, attaching the
        'X-Flick-Auth-Key' header, and either return the parsed/validated response
        (`handle_response=True`) or the raw `requests.Response` for a caller (submit_document) that
        needs custom business-validation handling. """
        headers = {'Content-Type': 'application/json', 'X-Flick-Auth-Key': self.api_key or ''}
        url = f"{self.base_url}/v1{path}"
        try:
            response = self._session.request(method, url, json=json, headers=headers, timeout=self.timeout)
        except requests.exceptions.RequestException as e:
            _logger.info("Network error calling Flick Network (%s %s): %s", method, path, e)
            raise UserError(_(
                "Network connectivity issue while contacting Flick Network. Please check your "
                "internet connection and try again."
            ))

        if response.status_code >= 400:
            _logger.info('"%s %s" %s - response body: %s', method, url, response.status_code, response.text[:2000])
        else:
            _logger.info('"%s %s" %s', method, url, response.status_code)

        if handle_response:
            return self._handle_response(response)
        return response

    @staticmethod
    def _handle_response(response):
        """ Raise a clear UserError for auth/transport/JSON failures, otherwise return the parsed
        JSON body - used by test_connection/get_status, which don't need submit_document's
        business-validation handling. """
        if response.status_code in (401, 403):
            raise UserError(_(
                "Authentication with Flick Network failed. Please check the API Key configured in "
                "Settings > Accounting > Flick Network."
            ))
        if response.status_code >= 400:
            raise UserError(_(
                "Flick Network could not process this request (%(status)s - %(reason)s). Please "
                "try again later.", status=response.status_code, reason=response.reason,
            ))
        try:
            return response.json()
        except ValueError:
            raise UserError(_(
                "An error occurred while reading the response from Flick Network. Please try again "
                "later."
            ))

    @staticmethod
    def _handle_submit_response(response):
        """ Flick reports both transport-level failures (4xx/5xx) and business-validation failures
        (a "failed" status in an otherwise-200 JSON body) - handled here rather than via
        `_handle_response()` so validation errors can be surfaced field-by-field instead of
        collapsing into a generic "could not process this request" message. """
        if response.status_code in (401, 403):
            raise UserError(_(
                "Authentication with Flick Network failed. Please check the API Key configured in "
                "Settings > Accounting > Flick Network."
            ))
        try:
            payload = response.json()
        except ValueError:
            raise UserError(_(
                "Flick Network returned an unexpected (non-JSON) response (%(status)s) while "
                "submitting this invoice:\n%(body)s",
                status=response.status_code, body=response.text[:2000],
            ))
        if payload.get('status') != 'success':
            # Errors can appear nested under "data" (documented) or at the top level (seen live).
            errors = (payload.get('data') or {}).get('errors') or payload.get('errors') or []
            if errors:
                details = '\n'.join('- %s' % FlickClient._format_error(error) for error in errors)
                raise UserError(_(
                    "Flick Network rejected this invoice:\n%(details)s", details=details,
                ))
            message = payload.get('message') or (payload.get('data') or {}).get('message') or payload.get('error')
            raise UserError(_(
                "Flick Network rejected this invoice submission (%(status)s):\n%(body)s",
                status=response.status_code, body=message or response.text[:2000],
            ))
        # A real submission confirmed the tracking identifier is returned as `data.id`, not the
        # documented `data.document_id` - kept as a fallback in case a future API revision changes
        # this.
        document_id = (payload.get('data') or {}).get('id') or (payload.get('data') or {}).get('document_id')
        if not document_id:
            raise UserError(_(
                "Flick Network accepted the submission but did not return a document_id to track it."
            ))
        return document_id

    @staticmethod
    def _format_error(error):
        """ Format one entry of Flick's error list without assuming their documented key names
        ('field_name'/'error_message') are exactly what the live sandbox actually returns - try the
        documented names and a couple of plausible alternates first, falling back to the raw error
        object as JSON so nothing is ever hidden behind a generic "Unknown error". """
        if not isinstance(error, dict):
            return str(error)
        field = error.get('field_name') or error.get('field') or error.get('path')
        message = error.get('error_message') or error.get('message') or error.get('description')
        if field or message:
            return "%s: %s" % (field or '?', message or json.dumps(error))
        return json.dumps(error)
