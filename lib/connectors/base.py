# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from datetime import datetime
from json import JSONDecodeError

import requests

from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Registered by each odoo/addons/l10n_ae_edi/lib/connectors/<vendor>.py module via @register_connector.
# Keyed by the same string used in res.company.l10n_ae_edi_asp_provider's Selection value.
#
# This module deliberately ships with only ONE entry here ('reference', see reference.py) - no named
# UAE Accredited Service Provider is hardcoded. The UAE Ministry of Finance's own published materials
# (the eInvoicing Programme deck) mention counts ("41 Pre-Approved Service Providers", "another 40 in
# Application Review") but do not name any of them, and this module is required to work with any
# current or future MoF-accredited provider without a core-code change - see the module description.
# Add a real provider by creating one file here + a matching Selection option on
# res.company.l10n_ae_edi_asp_provider (see models/res_company.py); nothing else needs to change.
CONNECTOR_REGISTRY = {}

# Generic credential "slots" a connector's REQUIRED_CONFIG can reference. The Settings UI shows only
# the fields a given connector actually lists - this is deliberately NOT a single auth_type toggle,
# since different ASPs can genuinely require different things (OAuth2 client credentials, a bearer API
# key, HTTP basic auth, mutual TLS via a client certificate, ...).
CONFIG_FIELD_LABELS = {
    'client_id': "Client ID",
    'client_secret': "Client Secret",
    'api_key': "API Key",
    'username': "Username",
    'password': "Password",
    'certificate_id': "Client Certificate",
    'account_id': "Account / Tenant / Company ID",
    'redirect_url': "OAuth Redirect URL",
}

# Which of CONFIG_FIELD_LABELS above are secret and therefore encrypted at rest (see ../crypto.py) -
# rather than every provider's connector re-declaring this, it is fixed once here since it is a
# property of what the field *is* (a client secret is always secret), not of which vendor uses it.
SECRET_CONFIG_FIELDS = {'client_secret', 'api_key', 'password'}

CONFIG_STATUS_SELECTION = [
    ('confirmed', "Confirmed from vendor documentation"),
    ('partial', "Partially confirmed - some details unverified"),
    ('unconfirmed', "Unknown / To Be Confirmed"),
]


def register_connector(provider_code):
    """ Class decorator registering a connector implementation for a given ASP provider code. """
    def decorator(cls):
        CONNECTOR_REGISTRY[provider_code] = cls
        return cls
    return decorator


class L10nAeEdiConnector:
    """ Abstract base class for a UAE e-invoicing Accredited Service Provider (ASP) connector.

    The UAE's Electronic Invoicing System requires routing every Electronic Invoice through one of
    several Ministry of Finance-accredited service providers (there is no direct network connection,
    and no Odoo-hosted access point for the UAE - Ministerial Decision No. 243 of 2025, Article 5). A
    concrete subclass implements the methods below against one specific vendor's API.

    This is the single seam a real ASP integration is wired in through: once a provider's connector
    implements `submit_invoice`/`get_status` for real, no other code in this module needs to change.
    """

    # Human-readable vendor name, overridden by each subclass.
    display_name = "Unconfigured"

    # Whether this connector represents a Person confirmed, by whoever built it, to actually appear on
    # the UAE Ministry of Finance's published list of Accredited Service Providers - the real, legal
    # answer to "can a business actually use this ASP for UAE e-invoicing", independent of how
    # well-documented its API happens to be (that's what CONFIG_STATUS tracks). Defaults to False.
    MOF_ACCREDITED = False

    # List of keys from CONFIG_FIELD_LABELS that this provider's Settings block should show. Populated
    # per-connector from that vendor's own public documentation.
    REQUIRED_CONFIG = []

    # 'confirmed' / 'partial' / 'unconfirmed' - see CONFIG_STATUS_SELECTION.
    CONFIG_STATUS = 'unconfirmed'

    # URL of the official vendor documentation page(s) actually read to determine REQUIRED_CONFIG.
    CONFIG_SOURCE = None

    # {'sandbox': url, 'production': url} - only set on a connector when its vendor's API is reached at
    # a fixed, documented host. Used purely to pre-fill the Settings "API Base URL" field as a
    # convenience default - left {} when no such fixed host is known/confirmed.
    DEFAULT_BASE_URL = {}

    # Short human-readable caveat shown alongside the Settings block for this provider.
    CONFIG_NOTES = ("No official API authentication documentation could be located for this provider. "
                     "Confirm directly with the vendor before configuring credentials.")

    def __init__(self, base_url=None, client_id=None, client_secret=None, api_key=None,
                 username=None, password=None, certificate_id=None, account_id=None,
                 redirect_url=None, environment='sandbox', timeout_limit=None):
        """ Store the connection details for one ASP and open the underlying HTTP session.

        All credential arguments are accepted as plain values - decryption already happened by the
        time this constructor is called (see the note on `client_secret` below).
        """
        self.base_url = base_url
        self.client_id = client_id
        # client_secret/api_key/password arrive here already DECRYPTED (see
        # models/res_company.py::_l10n_ae_edi_get_connector) - this class and its subclasses only ever
        # hold the plaintext transiently, for the duration of one request.
        self.client_secret = client_secret
        self.api_key = api_key
        self.username = username
        self.password = password
        # a certificate.certificate record, or None
        self.certificate_id = certificate_id
        # e.g. a sub-account/tenant identifier some ASPs require alongside client_id/client_secret
        self.account_id = account_id
        # required by OAuth2 authorization_code-style flows
        self.redirect_url = redirect_url
        self.environment = environment
        self.timeout_limit = min(timeout_limit or 10, 30)
        self._session = requests.Session()
        self._session.headers.update({'Accept': 'application/json'})

    def __enter__(self):
        """ Support `with connector as c: ...` - returns the connector itself. """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """ Close the underlying HTTP session when leaving a `with` block. """
        self._session.close()

    # -------------------------------------------------------------------------
    # Interface - implement in a concrete vendor subclass
    # -------------------------------------------------------------------------

    def submit_invoice(self, invoice_xml):
        """ Submit a PINT AE Invoice/CreditNote XML to this ASP.

        :param bytes invoice_xml: the PINT AE Invoice/CreditNote XML (Corners 1-4, Peppol network).
            The ASP itself is responsible for Tax Data reporting to the Federal Tax Authority
            (Corner 5) and for generating the document's UUID - see UAE Electronic Invoicing
            Guidelines s5.1-5.2.
        :return: an ASP-assigned reference string identifying this submission.
        :rtype: str
        """
        raise self._not_configured_error()

    def get_status(self, asp_reference):
        """ Poll the ASP for the current status of a previously submitted document.

        :param str asp_reference: the reference returned by a prior `submit_invoice` call.
        :return: one of 'in_progress', 'accepted', 'rejected', 'error'.
        :rtype: str
        """
        raise self._not_configured_error()

    def test_connection(self, country_code):
        """ Optional: verify the configured credentials actually authenticate against the ASP, without
        submitting any invoice data. The base implementation is intentionally unimplemented rather
        than a copy of `_not_configured_error`, so callers can tell "no ASP selected" apart from "this
        ASP's connector doesn't offer a test connection method yet".

        :param str country_code: ISO country code to check, e.g. 'AE'.
        :rtype: dict
        """
        raise NotImplementedError(f"{self.display_name} connector does not implement test_connection().")

    # -------------------------------------------------------------------------
    # Shared HTTP helpers, available to concrete subclasses
    # -------------------------------------------------------------------------

    def _not_configured_error(self):
        """ Build the standard "no working ASP integration yet" error, naming this connector. """
        return UserError(_(
            "No working Accredited Service Provider (ASP) integration is configured for %(provider)s "
            "yet. Select and contract a Ministry of Finance-accredited ASP, then complete this "
            "connector's API integration once that provider's API documentation/sandbox is available. "
            "In the meantime, the generated PINT AE invoice XML can be submitted to your ASP manually "
            "(see Settings > Accounting > UAE E-Invoicing).",
            provider=self.display_name,
        ))

    def _request(self, method, endpoint, params=None, json=None, data=None, headers=None,
                 files=None, handle_response=True):
        """ Make one HTTP call to `self.base_url + endpoint`, logging duration/status, and either
        return the parsed response (via `_handle_response`) or the raw `requests.Response`.

        :param str method: HTTP verb, e.g. 'GET' / 'POST'.
        :param str endpoint: path appended to `self.base_url`.
        :param bool handle_response: if True (default), run the response through
            `_handle_response` and return its result; if False, return the raw response object.
        :raises UserError: on a transport-level failure (DNS/timeout/connection refused/...).
        """
        start = datetime.utcnow()
        url = f"{self.base_url}{endpoint}"

        try:
            response = self._session.request(
                method, url,
                timeout=self.timeout_limit,
                params=params,
                json=json,
                data=data,
                headers=headers,
                files=files,
            )
        except requests.exceptions.RequestException as e:
            _logger.info("Network error calling %s: %s", self.display_name, e)
            raise UserError(_("Network connectivity issue while contacting %(provider)s. Please check your "
                               "internet connection and try again.", provider=self.display_name))

        duration = (datetime.utcnow() - start).total_seconds()
        # Response body is logged on failure to help debug real-world auth/schema mismatches - safe to
        # log since it's the ASP's own response, not anything we sent (credentials aren't in it).
        if response.status_code >= 400:
            _logger.info('"%s %s" %s %.3fs - response body: %s', method, url, response.status_code,
                         duration, response.text[:2000])
        else:
            _logger.info('"%s %s" %s %.3fs', method, url, response.status_code, duration)

        if handle_response:
            return self._handle_response(response)
        return response

    def _handle_response(self, response):
        """ Turn an HTTP response into either its parsed JSON body or a clear `UserError`,
        distinguishing auth failures (401/403), other 4xx/5xx errors, and invalid JSON bodies. """
        if response.status_code in (401, 403):
            raise UserError(_("Authentication with %(provider)s failed. Please check the API credentials "
                               "configured in Settings > Accounting > UAE E-Invoicing.", provider=self.display_name))
        if 403 < response.status_code < 600:
            raise UserError(_("%(provider)s could not process this request (%(status)s - %(reason)s). "
                               "Please try again later.", provider=self.display_name,
                               status=response.status_code, reason=response.reason))
        try:
            return response.json()
        except JSONDecodeError:
            _logger.exception("Invalid JSON response from %s: %s", self.display_name, response.text)
            raise UserError(_("An error occurred while reading the response from %(provider)s. Please try "
                               "again later.", provider=self.display_name))
