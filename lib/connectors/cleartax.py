# Part of Odoo. See LICENSE file for full copyright and licensing details.
from .base import L10nOmEdiConnector, register_connector


@register_connector('cleartax')
class ClearTaxConnector(L10nOmEdiConnector):
    """ Stub connector for ClearTax.

    CONFIRMED OTA-ACCREDITED: ClearTax is genuinely, officially on the Oman Tax Authority's published
    accredited-provider list (checked 2026-07-30, full list of 12: registered there under its legal
    parent entity "Defmacro Software", Solution Name "Cleartax", contact gcc-einvoicing@cleartax.com -
    https://fawtara.taxoman.gov.om/accredited-service-providers). This is the only connector in this
    module with that level of confirmation - everything else here was built from general research
    before that official list was checked, and is not confirmed to be a legally usable ASP for Oman.

    Their published KSA (Saudi) e-invoicing API uses a single bearer-style API key sent as a custom
    header: `X-Cleartax-Auth-Token`, obtained by logging into the ClearTax account (no OAuth flow, no
    client_id/secret pair). Mapped here onto the generic `api_key` slot.

    NOT CONFIRMED: whether their Oman/GCC product (the one actually accredited above) uses this exact
    same auth scheme, or something specific to that product - only the KSA docs were locatable. The
    contact email above (gcc-einvoicing@cleartax.com) is the right channel to confirm this directly and
    request real API/sandbox documentation for Oman specifically.
    """
    display_name = "ClearTax"
    OTA_ACCREDITED = True
    REQUIRED_CONFIG = ['api_key']
    CONFIG_STATUS = 'partial'
    CONFIG_SOURCE = "https://docs.cleartax.in/cleartax-docs/e-invoicing-ksa-api/e-invoicing-ksa-api-reference/authentication"
    CONFIG_NOTES = ("Officially OTA-accredited for Oman (verified against the government's own list - "
                     "registered as 'Defmacro Software', contact gcc-einvoicing@cleartax.com). Auth "
                     "mechanism confirmed only for their KSA (Saudi) product: a single API key sent as "
                     "the 'X-Cleartax-Auth-Token' header. Whether their Oman product uses the same "
                     "scheme is not yet confirmed - contact them directly at the email above for real "
                     "Oman-specific API/sandbox documentation.")
