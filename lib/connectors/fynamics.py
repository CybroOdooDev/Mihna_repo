# Part of Odoo. See LICENSE file for full copyright and licensing details.
from .base import L10nOmEdiConnector, register_connector


@register_connector('fynamics')
class FynamicsConnector(L10nOmEdiConnector):
    """ Stub connector for Fynamics.

    CONFIRMED OTA-ACCREDITED: listed on the Oman Tax Authority's official accredited-provider list
    (checked 2026-07-30, full list of 12): legal entity "Fynamics Techno Solutions", Solution Name
    "Fynamics", Data Residency **United Arab Emirates** (the only one of the 12 not hosted in Oman),
    contact mohan.mb@fynamics.tech - https://fawtara.taxoman.gov.om/accredited-service-providers

    This name also turned up independently in general web research (branded "OTA Pre-Approved ASP" on
    their own marketing) before the official list was checked - the official list now confirms that
    claim was accurate. No public API/authentication documentation has been located yet. Contact them
    directly at the email above to request developer docs/sandbox access.
    """
    display_name = "Fynamics"
    OTA_ACCREDITED = True
    REQUIRED_CONFIG = []
    CONFIG_STATUS = 'unconfirmed'
    CONFIG_SOURCE = "https://fawtara.taxoman.gov.om/accredited-service-providers"
    CONFIG_NOTES = ("Officially OTA-accredited for Oman (Data Residency: United Arab Emirates - the "
                     "only one of the 12 accredited providers not hosted in Oman itself; contact "
                     "mohan.mb@fynamics.tech). No public API/authentication documentation has been "
                     "located yet - contact them directly to request developer docs/sandbox access.")
