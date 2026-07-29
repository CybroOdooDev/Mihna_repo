# Part of Odoo. See LICENSE file for full copyright and licensing details.
from .base import L10nOmEdiConnector, register_connector


@register_connector('fawtarax')
class FawtaraXConnector(L10nOmEdiConnector):
    """ Stub connector for FawtaraX (fawtarax.com).

    IMPORTANT - this is a different situation from the other connectors in this module. For vendors
    like Pagero, Sovos, SAP, etc., the *company* is independently verifiable (a known, established
    business); what's unconfirmed is only their API's technical details. For FawtaraX, research at the
    time this was added found no verifiable legal entity name, business registration number, physical
    address, or phone number, and no independent coverage/reviews anywhere outside the site itself. Its
    "OTA Accredited Service Provider" and ISO 27001 certification claims are self-reported and were not
    checked against OTA's actual published accredited-provider list or the certifying body's registry.

    The site exposes a "Settings > API Keys" page, which is why `api_key` is used as the credential
    slot here - but this is inferred from the page's naming, not from published API documentation.

    Do not treat this connector as vetted. Before entering real credentials or submitting real invoice/
    tax data through it, independently confirm FawtaraX's accreditation directly with the Oman Tax
    Authority / Fawtara Portal - not from the vendor's own claims.
    """
    display_name = "FawtaraX"
    REQUIRED_CONFIG = ['api_key']
    CONFIG_STATUS = 'unconfirmed'
    CONFIG_SOURCE = "https://fawtarax.com/settings/api-keys"
    CONFIG_NOTES = ("Unlike the other providers listed here, FawtaraX's legitimacy as a company - not "
                     "just its API details - is unverified: no legal entity, registration number, "
                     "address, or phone number was found, and its accreditation claims are "
                     "self-reported. Confirm directly with the Oman Tax Authority before using this.")
