# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'United Arab Emirates - E-invoicing',
    'countries': ['ae'],
    'version': '1.0',
    'category': 'Accounting/Localizations/EDI',
    'icon': '/account/static/description/l10n.png',
    'summary': "Submit PINT AE e-invoices to the UAE Federal Tax Authority through any "
               "MoF-Accredited Service Provider (ASP)",
    'description': """
    UAE E-invoicing
    ===============

    Covers both halves of UAE Electronic Invoicing end to end - generating the PINT AE XML and
    submitting it through an Accredited Service Provider (ASP):

    * The UBL PINT e-invoicing format for the United Arab Emirates, based on the Peppol International
      (PINT) model for Billing, as required by the UAE Ministry of Finance's Electronic Invoicing
      System (Ministerial Decision No. 243 of 2025 and No. 244 of 2025). This part only generates the
      PINT AE XML (5-corner model, Corners 1-4) - it does not by itself submit anything over the
      network.
    * A generic, provider-agnostic Accredited Service Provider (ASP) integration framework. The UAE's
      5-corner Peppol model requires routing every Electronic Invoice through a Ministry of
      Finance-accredited ASP - there is no direct connection and no Odoo-hosted access point for the
      UAE (Ministerial Decision No. 243 of 2025, Article 5). This module deliberately does NOT
      hardcode any specific ASP: it ships a single, documentation-only reference connector, and adding
      a real provider is a matter of dropping in one new connector file (see lib/connectors/) plus a
      Selection option - no change to this module's core models, views, or state machine.
    * A submission-tracking model (l10n.ae.edi.document) recording the generated PINT AE invoice XML,
      the submission state, and the ASP's acknowledgement.
    * Symmetric (Fernet) encryption at rest for every secret ASP credential (API keys, client secrets,
      passwords), decrypted only transiently in memory at the point of an outbound API call - see
      lib/crypto.py.
    * Sandbox/Production selectable per company, independent of which ASP is configured.

    XML generation scope, notably:

    * Electronic Invoice categories: electronic Tax Invoice, electronic Tax Credit Note, Commercial
      Invoice, Electronic Credit Note, and their self-billed variants (UAE Electronic Invoicing
      Guidelines v1.1, s10.1).
    * The 8 special-scenario flags from Guidelines s10.4 (Free Zone, Deemed Supply, Margin Scheme,
      Summary Invoice, Continuous Supply, Disclosed Agent Billing, Supply through e-Commerce, Exports),
      assembled into the "Invoice transaction type code" bitstring required by the UAE Electronic
      Invoice Mandatory Fields spec (s4.1, field 5).
    * No QR code or barcode: unlike some other Peppol PINT specializations, PINT AE invoices are XML
      only (Guidelines s5.3) - this module does not add one.

    OUT OF SCOPE, deliberately:

    * FTA/EmaraTax registration itself - this module assumes a valid Tax Identification Number (TIN)
      already exists and only stores identifiers, never drives registration.
    * Inbound (Corner 4, receiving a supplier's Electronic Invoice back into Odoo) - this module is
      Outbound (Corner 1) only. The transmission log's `direction` field already distinguishes
      outbound/inbound so a future module can add inbound support without touching this one.
    * Rollout-deadline tracking and penalty-risk monitoring (Cabinet Decision No. 106 of 2025) - left
      for a later, separate compliance module; nothing here computes a mandatory-implementation date.

    NOT YET CONFIRMED against an official PINT-AE XSD/schematron (not published at the time this
    module was written, only the Ministry's "Mandatory Fields" data-dictionary style document was
    available): the exact XML element/path for the "Invoice transaction type code" bitstring. It is
    represented here as a structured, prefixed `cbc:Note` entry - see
    `account_edi_xml_pint_ae.py::_ubl_add_notes_nodes_all_invoices` - and must be corrected once the
    real schema location is published.
    """,
    'depends': ['l10n_ae', 'account_edi_ubl_cii', 'base_vat', 'certificate'],
    'data': [
        'security/ir.model.access.csv',
        'security/l10n_ae_edi_security.xml',
        'data/ir_cron.xml',
        'views/res_company_view.xml',
        'views/res_company_asp_view.xml',
        'views/res_partner_view.xml',
        'views/account_move_view.xml',
        'views/account_move_edi_view.xml',
        'views/res_config_settings_view.xml',
        'views/l10n_ae_edi_document_views.xml',
    ],
    'installable': True,
    'author': 'Cybrosys Techno Solutions',
    'license': 'LGPL-3',
}
