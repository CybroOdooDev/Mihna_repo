# Part of Odoo. See LICENSE file for full copyright and licensing details.
from .base import L10nOmEdiConnector, register_connector


@register_connector('marminai')
class MarminAiConnector(L10nOmEdiConnector):
    """ Stub connector for Marmin AI.

    CONFIRMED OTA-ACCREDITED: listed on the Oman Tax Authority's official accredited-provider list
    (checked 2026-07-30, full list of 12): legal entity "Marminai Software", Solution Name "Marmin AI",
    Data Residency Oman, contact abhishek.jajoo@ajmsglobal.com -
    https://fawtara.taxoman.gov.om/accredited-service-providers

    No public API/authentication documentation has been located for this provider yet. Contact them
    directly at the email above to request developer docs/sandbox access.
    """
    display_name = "Marmin AI"
    OTA_ACCREDITED = True
    REQUIRED_CONFIG = []
    CONFIG_STATUS = 'unconfirmed'
    CONFIG_SOURCE = "https://fawtara.taxoman.gov.om/accredited-service-providers"
    CONFIG_NOTES = ("Officially OTA-accredited for Oman (Data Residency: Oman; contact "
                     "abhishek.jajoo@ajmsglobal.com). No public API/authentication documentation has "
                     "been located yet - contact them directly to request developer docs/sandbox "
                     "access.")
