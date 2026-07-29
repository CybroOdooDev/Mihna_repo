# Part of Odoo. See LICENSE file for full copyright and licensing details.
from .base import L10nOmEdiConnector, register_connector


@register_connector('unifiedpost')
class UnifiedpostConnector(L10nOmEdiConnector):
    """ Stub connector for Unifiedpost (Banqup).

    Their own API documentation confirms OAuth2, offering both an Authorization Code flow
    (user-facing/interactive) and a Client Credentials flow (service-to-service) - the latter is the
    relevant one for unattended invoice submission, mapped here onto client_id/client_secret.

    NOT CONFIRMED: the exact field names used to request/configure Client Credentials access - the
    documentation pointed to a developer portal (developerportal.unifiedpost.com) and a support
    mailbox for the specifics, which weren't independently verified here.
    """
    display_name = "Unifiedpost"
    REQUIRED_CONFIG = ['client_id', 'client_secret']
    CONFIG_STATUS = 'partial'
    CONFIG_SOURCE = "https://v4-api.unifiedpost.fr/"
    CONFIG_NOTES = ("Confirmed: OAuth2, with a Client Credentials grant available for service-to-"
                     "service integration (also offers an Authorization Code flow for interactive "
                     "use, not relevant here). NOT confirmed: exact credential field names - obtain "
                     "these via developerportal.unifiedpost.com.")
