#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2026-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
{
    'name': 'Oman E-Invoicing - Flick Network',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations/EDI',
    'summary': "Submit Oman e-invoices and credit notes to the Flick Network ASP platform, with "
               "status tracking",
    'description': """
    Oman E-Invoicing - Flick Network
    =================================

    A standalone connector to the Flick Network (flick.network) Accredited Service Provider
    platform for Oman's Fawtara e-invoicing mandate:

    * Submits customer invoices and credit notes to Flick Network's Document API, built directly
      from the invoice/credit note data already in Odoo, as their own flattened PINT-OM JSON schema.
    * Requires the company to already be registered as a "Participant" on Flick's Peppol network
      (a one-time manual setup via their dashboard) - the resulting participant_id is used on every
      submission/status call.
    * Tracks the submission status (To Send / Submitted / Acknowledged / Rejected / Error) and polls
      Flick Network for the latest status until acknowledged.

    SCOPE: this covers the core customer-invoice flow only (standard invoices and credit notes,
    Flick's documented "Submit Document" and "Get Document" operations). Flick Network's API also
    documents an OAuth2 client_credentials flow (not implemented, a static API key is used instead),
    recipient lookup and document validation (pre-submit) endpoints, and bulk submission - none of
    those are implemented here yet. No cancel/void endpoint is documented at all (only "Retry
    Document"), so cancellation is not implemented here either.

    NOTE ON QR CODES: this module does not generate or display a QR code anywhere. Neither Flick's
    PINT OM data dictionary nor their API reference documents a QR code requirement for Oman
    e-invoicing at all (unlike e.g. Saudi's ZATCA) - so none is fabricated here just to have one.
    """,
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': 'https://www.cybrosys.com',
    'depends': ['account', 'l10n_om', 'base_vat'],
    'data': [
        'security/ir.model.access.csv',
        'security/l10n_om_flick_security.xml',
        'data/ir_cron.xml',
        'views/l10n_om_flick_document_views.xml',
        'views/account_move_view.xml',
        'views/res_config_settings_view.xml',
    ],
    'images': ['static/description/banner.jpg'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
