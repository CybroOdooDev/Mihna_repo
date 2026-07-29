# Part of Odoo. See LICENSE file for full copyright and licensing details.
from .base import L10nOmEdiConnector, register_connector


@register_connector('pagero')
class PageroConnector(L10nOmEdiConnector):
    """ Stub connector for Pagero (a Peppol Access Point / Service Metadata Provider).

    Their public partner integration guidelines describe OAuth2 with the Authorization Code grant:
    a client_id + client_secret pair, a redirect URL that must be pre-registered with Pagero, and a
    per-account `companyId` needed on API calls.

    CAVEAT: Authorization Code is an interactively-consented flow (a user logs in and approves access),
    which is unusual for unattended, scheduled invoice submission. It's not confirmed from the
    documentation read here whether Pagero also offers a pure machine-to-machine (client_credentials)
    option for this kind of integration - that should be confirmed with Pagero directly, since it
    affects whether this can run as a background/cron process at all without a stored user session.
    """
    display_name = "Pagero"
    REQUIRED_CONFIG = ['client_id', 'client_secret', 'redirect_url', 'account_id']
    CONFIG_STATUS = 'partial'
    CONFIG_SOURCE = "https://pagero.github.io/partners/partner-integration-guidelines/"
    CONFIG_NOTES = ("Confirmed: OAuth2 Authorization Code grant, client_id/client_secret, a "
                     "pre-registered redirect URL, and a per-account 'companyId'. NOT confirmed: "
                     "whether an unattended/server-to-server (client_credentials) option also exists - "
                     "the Authorization Code flow implies an interactive login step.")
