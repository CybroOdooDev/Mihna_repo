# Part of Odoo. See LICENSE file for full copyright and licensing details.
from .base import L10nOmEdiConnector, register_connector


@register_connector('opentext')
class OpenTextConnector(L10nOmEdiConnector):
    """ Stub connector for OpenText.

    OpenText publishes OAuth2/OIDC docs for its Directory Services (OTDS) and a ticket-based
    (OTCSTICKET) scheme for Content Server - but no locatable authentication documentation for
    Trading Grid e-Invoicing / B2B Integration specifically, which is the actual relevant product line
    for e-invoice submission. Those other product lines' auth schemes are not assumed to carry over.
    """
    display_name = "OpenText"
    REQUIRED_CONFIG = []
    CONFIG_STATUS = 'unconfirmed'
    CONFIG_SOURCE = None
    CONFIG_NOTES = ("No authentication documentation found for OpenText's Trading Grid e-Invoicing / "
                     "B2B Integration product specifically (other OpenText product lines use OAuth2/"
                     "OIDC or ticket-based auth, but that isn't confirmed to apply here). Contact "
                     "OpenText directly before configuring.")
