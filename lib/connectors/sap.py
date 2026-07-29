# Part of Odoo. See LICENSE file for full copyright and licensing details.
from .base import L10nOmEdiConnector, register_connector


@register_connector('sap')
class SapConnector(L10nOmEdiConnector):
    """ Stub connector for SAP (SAP Document and Reporting Compliance, Cloud Edition).

    Their official Help Portal confirms OAuth 2.0 Client authentication (clientId, clientSecret, plus
    a service-binding URL - already covered by the generic `base_url` field) for SAP_BASIS 750 SP23+.
    Older SAP_BASIS versions may instead use X.509 Certificate authentication - mapped here onto the
    generic `certificate_id` slot, though this module does not attempt to detect which SAP_BASIS
    version a given customer runs.
    """
    display_name = "SAP"
    REQUIRED_CONFIG = ['client_id', 'client_secret']
    CONFIG_STATUS = 'confirmed'
    CONFIG_SOURCE = "https://help.sap.com/docs/cloud-edition/sap-document-and-reporting-compliance-cloud-edition/oauth-2-0-client-authentication"
    CONFIG_NOTES = ("Confirmed: OAuth 2.0 Client authentication (clientId/clientSecret) for "
                     "SAP_BASIS 750 SP23 or higher. Older systems may use X.509 Certificate "
                     "authentication instead - not auto-detected here, switch REQUIRED_CONFIG to "
                     "['certificate_id'] if that applies to your SAP system version.")
