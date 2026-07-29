# Part of Odoo. See LICENSE file for full copyright and licensing details.
from .base import L10nOmEdiConnector, register_connector


@register_connector('edicom')
class EdicomConnector(L10nOmEdiConnector):
    """ Stub connector for EDICOM.

    Their iPaaS API documentation confirms Bearer token authentication (`Authorization: Bearer
    <token>`), obtainable via either an "EDICOM Accounts" token or an "EIPAAS API Key" - mapped here
    onto the generic `api_key` slot as the single credential this module tracks.

    NOT CONFIRMED: the exact provisioning steps/fields for either token type (e.g. whether it's a
    static key or a short-lived token requiring its own exchange step) - the accessible documentation
    only named the two options without detailing them.
    """
    display_name = "EDICOM"
    REQUIRED_CONFIG = ['api_key']
    CONFIG_STATUS = 'partial'
    CONFIG_SOURCE = "https://ipaas-docs.edicomgroup.com/docs/manual/"
    CONFIG_NOTES = ("Confirmed: Bearer token authentication, via either an 'EDICOM Accounts' token or "
                     "an 'EIPAAS API Key'. NOT confirmed: exact provisioning/exchange steps for either "
                     "option - verify with EDICOM before relying on this.")
