# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64

from odoo import _
from odoo.exceptions import UserError

from .base import L10nOmEdiConnector, register_connector


@register_connector('sovos')
class SovosConnector(L10nOmEdiConnector):
    """ Sovos connector.

    Confirmed from Sovos's own public API reference:
    - Auth: OAuth2 client_credentials. Base64-encode "API Key:Secret" (Sovos's own terminology for what
      this module tracks as client_id/client_secret), send as a Basic Auth header to POST /oauth/token
      with grant_type=client_credentials (form-encoded body), receive a bearer access_token (~1h
      validity). https://docs.sovos.com/en/indirect-tax/indirect-tax-products/einvoicing/indirect-tax-api/api-authentication
    - Connectivity check: GET /v1/status - returns backend system health for a given country, no
      invoice data involved. https://docs.sovos.com/en/indirect-tax/indirect-tax-products/einvoicing/indirect-tax-api/e-invoicing/check-connectivity-endpoints
      The exact query parameter name for the country code was not shown on the accessible page (it's
      behind a downloadable OpenAPI spec) - `countryCode` is inferred from the documented endpoints
      below using the same name, not independently verified for /v1/status specifically.
    - Document endpoints (paths and purposes confirmed, request/response BODY schema not):
        POST /v1/documents                                    - submit a document
        POST /v1/documents/{countryCode}/action                - cancel/correct/distribute
        GET  /v1/documents/{countryCode}/{documentId}/notifications - status/notifications
      https://docs.sovos.com/en/indirect-tax/indirect-tax-products/einvoicing/indirect-tax-api/e-invoicing/documents-endpoints
      The actual submission format is a Standard Business Document (SBD) wrapping a "Sovos Canonical
      Invoice" (SCI) - Sovos's own proprietary schema, not raw UBL/PINT-OM XML. That schema is gated
      behind Sovos's downloadable OpenAPI spec, which could not be retrieved by automated research
      (the page only exposes a "Download" button, not the file content itself). Whether Sovos also
      accepts UBL/PINT-OM XML directly (bypassing SCI conversion) is unconfirmed either way.
    - Host: their docs mention an "alternate URL api-test-tls.sovos.com ... for TLS-required
      functionalities", which implies a general sandbox host of api-test.sovos.com (and, by the same
      pattern, api.sovos.com for production). This is an INFERENCE from one incidental mention, not an
      independently confirmed canonical base URL for every endpoint - used below only as a pre-filled
      Settings default, not asserted as certain. Verify against whatever host your own Sovos account/
      dashboard actually references before relying on it.

    NOT CONFIRMED: this is Sovos's generic Indirect Tax API doc, not an Oman/Fawtara-specific product -
    verify the same mechanism applies once an actual Oman contract exists.
    """
    display_name = "Sovos"
    REQUIRED_CONFIG = ['client_id', 'client_secret']
    CONFIG_STATUS = 'confirmed'
    DEFAULT_BASE_URL = {
        'test': 'https://api-test.sovos.com',
        'production': 'https://api.sovos.com',
    }
    CONFIG_SOURCE = "https://docs.sovos.com/en/indirect-tax/indirect-tax-products/einvoicing/indirect-tax-api/api-authentication"
    CONFIG_NOTES = ("Confirmed: OAuth2 client_credentials grant. Sovos calls the two credentials 'API "
                     "Key' and 'Secret' rather than 'Client ID'/'Client Secret', mapped 1:1 here. The "
                     "API Base URL is pre-filled from an inference (not an independently confirmed "
                     "canonical host) - verify it against your own Sovos account before relying on it. "
                     "Not confirmed against an Oman-specific product line. Authentication and a "
                     "connectivity check are really implemented; invoice submission is not (see "
                     "submit_invoice).")

    # -------------------------------------------------------------------------
    # Real, confirmed calls
    # -------------------------------------------------------------------------

    def _get_access_token(self):
        """ POST /oauth/token, form-encoded, Basic-auth header of base64("client_id:client_secret").
        Routed through the shared `_request()` helper so this call is logged (method/URL/status/
        duration, plus the response body on failure) the same as every other call this module makes -
        essential for debugging real-world auth failures against a live ASP. """
        if not (self.client_id and self.client_secret):
            raise self._not_configured_error()

        credentials = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        token_data = self._request(
            'POST', '/oauth/token',
            data={'grant_type': 'client_credentials'},
            headers={'Authorization': f'Basic {credentials}'},
        )
        access_token = token_data.get('access_token')
        if not access_token:
            raise UserError(_("Sovos did not return an access token. Check the API Key/Secret configured "
                               "in Settings > Accounting > Oman E-Invoicing."))
        return access_token

    def test_connection(self, country_code):
        """ GET /v1/status - a real, side-effect-free way to confirm the configured Sovos credentials
        actually authenticate, without touching invoice submission at all. """
        access_token = self._get_access_token()
        return self._request(
            'GET', '/v1/status',
            params={'countryCode': country_code},
            headers={'Authorization': f'Bearer {access_token}'},
        )

    # -------------------------------------------------------------------------
    # Not yet implementable - the endpoints are known, the body schema is not
    # -------------------------------------------------------------------------

    def submit_invoice(self, invoice_xml, tdd_xml):
        raise UserError(_(
            "Sovos's submission endpoint (POST /v1/documents) and OAuth2 authentication are confirmed "
            "from their public API documentation, but the exact request body format - a Standard "
            "Business Document wrapping Sovos's proprietary 'Sovos Canonical Invoice' (SCI) format - "
            "requires their downloadable OpenAPI specification, which could not be retrieved "
            "automatically. Credentials can already be verified via test_connection(); obtain that "
            "OpenAPI spec from Sovos (support or your account contact) to complete this method."
        ))

    def get_status(self, asp_reference):
        raise UserError(_(
            "Sovos's status endpoint (GET /v1/documents/{countryCode}/{documentId}/notifications) is "
            "confirmed to exist, but this connector does not yet track the countryCode/documentId pair "
            "that endpoint requires as separate path segments (asp_reference alone isn't confirmed to "
            "be sufficient), and the notification response schema wasn't available. Complete once "
            "submit_invoice is implemented and the response schema is confirmed."
        ))

    def cancel(self, asp_reference, reason):
        raise UserError(_(
            "Sovos's action endpoint (POST /v1/documents/{countryCode}/action, with 'cancel' as one of "
            "the available actions) is confirmed to exist, but the exact request body schema for "
            "triggering it was not available. Complete once that schema is confirmed."
        ))
