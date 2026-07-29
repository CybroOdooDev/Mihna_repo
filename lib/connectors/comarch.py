# Part of Odoo. See LICENSE file for full copyright and licensing details.
from .base import L10nOmEdiConnector, register_connector


@register_connector('comarch')
class ComarchConnector(L10nOmEdiConnector):
    """ Stub connector for Comarch.

    No official Comarch API authentication documentation could be located. Searches only surfaced
    third-party aggregator sites (not Comarch's own docs) making unverifiable claims about supported
    auth methods - those were not treated as a source. Left unconfigured rather than guessing.
    """
    display_name = "Comarch"
    REQUIRED_CONFIG = []
    CONFIG_STATUS = 'unconfirmed'
    CONFIG_SOURCE = None
    CONFIG_NOTES = ("No official Comarch API authentication documentation was found. Contact Comarch "
                     "directly for their developer portal/API auth requirements before configuring.")
