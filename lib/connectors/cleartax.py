# Part of Odoo. See LICENSE file for full copyright and licensing details.
from .base import L10nOmEdiConnector, register_connector


@register_connector('cleartax')
class ClearTaxConnector(L10nOmEdiConnector):
    """ Stub connector for ClearTax.

    Their published KSA (Saudi) e-invoicing API uses a single bearer-style API key sent as a custom
    header: `X-Cleartax-Auth-Token`, obtained by logging into the ClearTax account (no OAuth flow, no
    client_id/secret pair). Mapped here onto the generic `api_key` slot.

    NOT CONFIRMED: whether ClearTax has a separate Oman-specific API/product, or whether it uses this
    same auth scheme - only the KSA docs were locatable. Do not assume this applies to Oman without
    checking directly with ClearTax once a contract exists.
    """
    display_name = "ClearTax"
    REQUIRED_CONFIG = ['api_key']
    CONFIG_STATUS = 'partial'
    CONFIG_SOURCE = "https://docs.cleartax.in/cleartax-docs/e-invoicing-ksa-api/e-invoicing-ksa-api-reference/authentication"
    CONFIG_NOTES = ("Confirmed for ClearTax's KSA (Saudi) e-invoicing API: a single API key sent as the "
                     "'X-Cleartax-Auth-Token' header. An Oman-specific product/API was not found - "
                     "verify with ClearTax directly before relying on this.")
