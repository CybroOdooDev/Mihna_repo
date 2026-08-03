# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Oman - E-invoicing (Fawtara)',
    'countries': ['om'],
    'version': '1.0',
    'category': 'Accounting/Localizations/EDI',
    'icon': '/account/static/description/l10n.png',
    'summary': "Submit PINT OM e-invoices to the Oman Tax Authority through an Accredited Service Provider (ASP)",
    'description': """
    Oman E-invoicing (Fawtara)
    ==========================

    Adds a submission layer on top of l10n_om_ubl_pint's PINT OM XML generation:

    * A per-company choice of Accredited Service Provider (ASP) - businesses in Oman's 5-corner Peppol
      model must route through one of several OTA-accredited providers, there is no direct connection
      and no Odoo-hosted access point for Oman.
    * A submission-tracking model (l10n.om.edi.document) recording the generated invoice XML, the
      separate Tax Data Document (TDD) sent to the Oman Tax Authority, and the ASP's acknowledgement.
    * A QR-code helper for B2C invoices.

    IMPORTANT: the ASP Provider list here is exactly the Oman Tax Authority's own published
    Accredited Service Provider list (verified 2026-07-30 - see
    https://fawtara.taxoman.gov.om/accredited-service-providers). All 12 connectors ship without a
    working submit_invoice/get_status/cancel implementation - this is deliberate, deferred work, not
    an oversight (no ASP account/production credentials were available at the time of writing). Flick
    Network's connector has confirmed, working authentication and a real connectivity check; ClearTax's
    auth is confirmed for their KSA product only; the other 10 have no located public API documentation
    at all. Each connector raises a clear error on submit/status/cancel until it is completed against
    that vendor's real API - see each connector's CONFIG_NOTES for their listed contact email.
    """,
    'depends': ['l10n_om', 'l10n_om_ubl_pint', 'certificate'],
    'data': [
        'security/ir.model.access.csv',
        'security/l10n_om_edi_security.xml',
        'data/ir_cron.xml',
        'views/l10n_om_edi_document_views.xml',
        'views/account_move_view.xml',
        'views/res_company_view.xml',
        'views/res_config_settings_view.xml',
        'views/report_invoice.xml',
        'wizard/l10n_om_edi_cancel_wizard_views.xml',
    ],
    'installable': True,
    'author': 'Cybrosys Techno Solutions',
    'license': 'LGPL-3',
}
