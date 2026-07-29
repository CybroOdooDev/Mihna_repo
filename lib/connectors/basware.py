# Part of Odoo. See LICENSE file for full copyright and licensing details.
from .base import L10nOmEdiConnector, register_connector


@register_connector('basware')
class BaswareConnector(L10nOmEdiConnector):
    """ Stub connector for Basware.

    Their developer site confirms OAuth2 client_credentials for the AP Automation/P2P APIs:
    client_id + client_secret sent as a Basic Auth header to POST /v1/tokens, returning a JWT
    access_token (default 1h validity, configurable 5min-24h). Their separate SmartPDF API product
    also supports plain Basic Authentication as an alternative, but that's a different, smaller
    product line, not assumed to apply to invoice submission.
    """
    display_name = "Basware"
    REQUIRED_CONFIG = ['client_id', 'client_secret']
    CONFIG_STATUS = 'confirmed'
    CONFIG_SOURCE = "https://developer.basware.com/en/api/basware/api-reference"
    CONFIG_NOTES = ("Confirmed: OAuth2 client_credentials grant via POST /v1/tokens, credentials sent "
                     "as a Basic Auth header.")
