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
    'name': 'Oman E-Invoicing - ConvergeX',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations/EDI',
    'summary': "Submit Oman e-invoices and credit notes to the ConvergeX ASP platform, with status "
               "tracking and QR code retrieval",
    'description': """
    Oman E-Invoicing - ConvergeX
    =============================

    A standalone connector to the ConvergeX (convergex.biz) Accredited Service Provider platform for
    Oman's Fawtara e-invoicing mandate:

    * Submits customer invoices and credit notes to ConvergeX's Customer Invoice API, built directly
      from the invoice/credit note data already in Odoo.
    * Syncs the buyer as a ConvergeX Customer Master record before submission (required for their
      PEPPOL network checks).
    * Retrieves and stores the OTA QR code, tracking number, and processed reference on each
      submission.
    * Polls ConvergeX for the latest status until an invoice is acknowledged by the Oman Tax
      Authority.

    SCOPE: this covers the core customer-invoice flow only (standard invoices and credit notes).
    ConvergeX's API also documents supplier invoices, offline/POS QR reservation, Excel bulk upload,
    and dedicated compliance/TDD-evidence endpoints - none of those are implemented here yet.
    """,
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': 'https://www.cybrosys.com',
    'depends': ['account', 'l10n_om', 'base_vat'],
    'data': [
        'security/ir.model.access.csv',
        'security/l10n_om_convergex_security.xml',
        'data/ir_cron.xml',
        'views/l10n_om_convergex_document_views.xml',
        'views/account_move_view.xml',
        'views/res_config_settings_view.xml',
    ],
    'images': ['static/description/banner.jpg'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
