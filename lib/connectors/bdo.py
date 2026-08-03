# Part of Odoo. See LICENSE file for full copyright and licensing details.
from .base import L10nOmEdiConnector, register_connector


@register_connector('bdo')
class BdoConnector(L10nOmEdiConnector):
    """ Stub connector for BDO.

    CONFIRMED OTA-ACCREDITED: listed on the Oman Tax Authority's official accredited-provider list
    (checked 2026-07-30, full list of 12): legal entity "BDO", Solution Name "BDO LLC", Data Residency
    Oman, contact bipin.kapur@bdo.com.om - https://fawtara.taxoman.gov.om/accredited-service-providers

    BDO is one of the world's largest accounting/advisory networks, giving this entry more general
    corporate credibility than most others on this list - but no public e-invoicing API documentation
    specific to their Oman Fawtara solution has been located. Contact them directly at the email above
    to request developer docs/sandbox access.
    """
    display_name = "BDO"
    OTA_ACCREDITED = True
    REQUIRED_CONFIG = []
    CONFIG_STATUS = 'unconfirmed'
    CONFIG_SOURCE = "https://fawtara.taxoman.gov.om/accredited-service-providers"
    CONFIG_NOTES = ("Officially OTA-accredited for Oman (Data Residency: Oman; contact "
                     "bipin.kapur@bdo.com.om). No public API/authentication documentation has been "
                     "located yet for their Fawtara solution - contact them directly to request "
                     "developer docs/sandbox access.")
